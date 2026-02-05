__copyright__ = "Reiner Lemoine Institut"
__license__ = "GNU Affero General Public License Version 3 (AGPL-3.0)"
__url__ = "https://github.com/openego/data_processing/blob/master/LICENSE"
__author__ = "henhuy, jh-RLI"

import os
from collections import namedtuple
from typing import List, Union, Tuple
import json
from urllib.parse import urljoin
from oem2orm import logs
import pathlib
import jmespath
import getpass
import sqlalchemy as sa
import re
import requests
from omi.base import get_metadata_specification
from omi.validation import validate_metadata

import oedialect

from copy import deepcopy

from oem2orm.normalizer import (
    TABLE_NORMALIZER,
    COLUMN_NORMALIZER,
    normalize_resource_inplace,
    strip_blank_fk_and_keys,
    split_schema_table,
)
from oem2orm.postgresql_types import TYPES
from oem2orm.settings import get_oep_api_url, get_oep_host, get_oep_token, get_oep_user

MAX_TABLE_LEN = 50
MAX_COLUMN_LEN = 50
DEFAULT_SCHEMA = "data"

# prepare connection string to connect via oep API
CONNECTION_STRING = "{engine}://{user}:{token}@{host}"
#
DB = namedtuple("Database", ["engine", "metadata"])

logger = logs.setup_logging()


class CredentialError(Exception):
    pass


class DatabaseError(Exception):
    pass


class MetadataError(Exception):
    pass


def setup_logger(logger_level: str = "Yes"):
    """
    Easy logging setup depending on user input. Provides a logger for
    INFO level logging.

    :return: logging.INFO or none
    """

    if re.fullmatch("[Yy]es", logger_level):
        print("Logging activated")
        return logger
    elif re.fullmatch("[Nn]o", logger_level):
        pass


def setup_db_connection(
    engine="postgresql+oedialect", host=None, token=None, user=None
):
    user = user or get_oep_user() or input("Enter OEP-username:")
    token = token or get_oep_token() or setUserToken()
    host = host or get_oep_host()

    # Don't print the token
    safe_conn_str = f"{engine}://{user}:***@{host}"
    print(f"Connecting to OEP API with connection string: {safe_conn_str}")

    sa_engine = sa.create_engine(f"{engine}://{user}:{token}@{host}")
    metadata = sa.MetaData(bind=sa_engine)
    return DB(sa_engine, metadata)


def setupApiAction(schema, table, token=None):
    base = get_oep_api_url()
    dest_url = urljoin(base, f"schema/{schema}/tables/{table}/meta/")
    token = token or get_oep_token() or setUserToken()
    headers = {
        "Authorization": f"Token {token}",
        "Accept": "application/json",
        "Content-Type": "application/json",
    }
    API_ACTION = namedtuple("API_Action", ["dest_url", "headers"])
    return API_ACTION(dest_url, headers)


def create_tables(db: DB, tables: List[sa.Table]):
    """
    Creates a SQLAlchemy create ORM table-objects via API connection on a Database.
    The tables can be a list of ORM.

    :param db: API
    :param tables: SQLAlchemy ORM objects (automatically retrieved from OEM json strings)
    :return: none
    """
    for table in tables:
        logger.info(f"Working on table: {table}")
        logger.info(f"Using connection: {db.engine}")
        if not db.engine.dialect.has_schema(db.engine, table.schema):
            error_msg = (
                f'The provided database schema: "{table.schema}" does not exist. Please use an existing '
                f"schema from the `name` column from: {get_oep_host}/dataedit/schemas"
            )
            logger.info(error_msg)
            raise DatabaseError(error_msg)
        else:
            if not db.engine.dialect.has_table(db.engine, table.name, table.schema):
                try:
                    table.create(checkfirst=True)
                    logger.info(f"Created table {table.name}")
                except oedialect.engine.ConnectionException as ce:
                    error_msg = (
                        f'Error when uploading table "{table.name}". Reason: {ce}.'
                    )
                    logger.error(error_msg)
                    raise DatabaseError(error_msg) from ce
                except sa.exc.ProgrammingError as pe:
                    error_msg = f'Table "{table.name}" already exists.'
                    logger.error(error_msg)
                    raise DatabaseError(error_msg) from pe


def delete_tables(db: DB, tables: List[sa.Table]):
    """
    Drop all tables stored in the sqlalchemy metadata object. The tables are sorted by
    foreign key and dropped one by one. Each drop interaction requires the user to
    confirm the action.

    :param db: sqla engine and metadata object
    :param tables:
    :return: none
    """

    ordered_tables = order_tables_by_foreign_keys(tables)
    reversed_tables = reversed(ordered_tables)

    confirmation = None
    while confirmation not in ("y", "n"):
        confirmation = input(
            f"Do you want to drop following tables ({', '.join(map(str, tables))})? [y/n]"
        )
    if confirmation == "y":
        for table in reversed_tables:
            table.drop(db.engine, checkfirst=True)


def order_tables_by_foreign_keys(tables: List[sa.Table]):
    """
    This function tries to order tables to avoid missing foreign key errors.

    By now, ordering is simply done by counting of foreign keys.
    """
    return sorted(tables, key=lambda x: len(x.foreign_keys))


def create_tables_from_metadata_file(
    db: DB, metadata_file: Union[str, dict]
) -> List[sa.Table]:
    # --- load metadata (path or dict) ---
    if isinstance(metadata_file, str):
        with open(metadata_file, "r") as metadata_json:
            metadata = json.loads(metadata_json.read())
    else:
        metadata = metadata_file

    resources = jmespath.search("resources", metadata) or []
    tables: List[sa.Table] = []

    # Track UNIQUE needs for referenced tables in this batch
    # Key: "schema.table" -> set of tuples of column names (supports composite)
    unique_needed: dict[str, set[tuple[str, ...]]] = {}

    # FK specs we will attach in pass 2
    pending_fks: list[dict] = []

    # ---- PASS 1: build all tables, add id-PK, collect uniques & FK specs (no FKs yet) ----
    built: dict[str, sa.Table] = {}

    for res in resources:
        strip_blank_fk_and_keys(res)

        # normalize table + columns + key names in place
        norm_table_name, _ = normalize_resource_inplace(res)
        if not norm_table_name:
            raise MetadataError("Cannot read table name (and schema)", res.get("name"))

        schema = DEFAULT_SCHEMA  # creation target schema (your existing constant)

        # fields (already normalized)
        fields = jmespath.search("schema.fields[*]", res) or []
        field_names = {f["name"] for f in fields}
        has_id = "id" in field_names

        columns: list[sa.Column] = []

        # Ensure a single PK named 'id'
        if not has_id:
            columns.append(
                sa.Column(
                    "id",
                    sa.Integer,
                    primary_key=True,
                    autoincrement=True,
                    comment="Surrogate primary key",
                )
            )

        # Build columns WITHOUT column-level FKs for now
        for field in fields:
            fname = field["name"]
            try:
                column_type = TYPES[field["type"]]
            except (KeyError, ValueError):
                raise MetadataError(
                    "Unknown column type", field, field.get("type"), metadata_file
                )
            comment = field.get("description")
            pk_flag = fname == "id"  # only 'id' may be PK
            columns.append(
                sa.Column(fname, column_type, primary_key=pk_flag, comment=comment)
            )

        # Create the Table object
        tbl = sa.Table(
            norm_table_name,
            db.metadata,
            *columns,
            schema=schema,
            extend_existing=True,
        )
        tables.append(tbl)
        built[f"{schema}.{norm_table_name}"] = tbl

        # Honor the metadata’s intended primaryKey by adding UNIQUE (if not 'id')
        intended_pk = (res.get("schema", {}) or {}).get("primaryKey")
        if intended_pk:
            if isinstance(intended_pk, str):
                intended_cols = (intended_pk,)
            else:
                intended_cols = tuple(intended_pk)
            intended_cols = tuple(intended_cols)  # already normalized
            if not (len(intended_cols) == 1 and intended_cols[0] == "id"):
                uc_name = f"uq_{norm_table_name}_" + "_".join(intended_cols)
                if not (
                    len(intended_cols) == 1
                    and getattr(tbl.c.get(intended_cols[0]), "unique", False)
                ):
                    tbl.append_constraint(
                        sa.UniqueConstraint(*intended_cols, name=uc_name)
                    )

        # Collect FK specs and record UNIQUE needs for any non-id target in this batch
        for fk in res.get("schema", {}).get("foreignKeys") or []:
            local_fields = fk.get("fields")
            if isinstance(local_fields, str):
                local_fields = [local_fields]
            reference = fk.get("reference") or {}

            # NOTE: preserve old behavior:
            # - extract only table from reference.resource
            # - FORCE the FK schema to the creation schema
            _ref_schema_ignored, ref_table_raw = split_schema_table(
                reference.get("resource", ""), default_schema=None
            )
            ref_schema = schema  # force to current schema (matches old nested function)

            ref_table_norm = TABLE_NORMALIZER(ref_table_raw)

            ref_fields = reference.get("fields")
            if isinstance(ref_fields, list) and ref_fields:
                remote_cols = tuple(COLUMN_NORMALIZER(rf) for rf in ref_fields)
            else:
                remote_cols = (COLUMN_NORMALIZER(ref_fields or "id"),)

            # remember FK spec for pass 2
            pending_fks.append(
                {
                    "this_schema": schema,
                    "this_table": norm_table_name,
                    "local_cols": [COLUMN_NORMALIZER(c) for c in (local_fields or [])],
                    "ref_schema": ref_schema,
                    "ref_table": ref_table_norm,
                    "ref_cols": remote_cols,
                }
            )

            # If target isn’t just ('id',) and the target table is in this batch,
            # we’ll need a UNIQUE on that target to satisfy FK requirement.
            key = f"{ref_schema}.{ref_table_norm}"
            if not (len(remote_cols) == 1 and remote_cols[0] == "id"):
                unique_needed.setdefault(key, set()).add(remote_cols)

    # ---- PASS 2A: add UNIQUE constraints required by in-batch FK targets ----
    for key, uniq_sets in unique_needed.items():
        tbl = built.get(key)
        if tbl is None:
            # referenced table not being created now; cannot add UNIQUE here
            continue
        existing = {
            tuple(col.name for col in uc.columns)
            for uc in tbl.constraints
            if isinstance(uc, sa.UniqueConstraint)
        }
        for cols in uniq_sets:
            if cols in existing:
                continue
            if len(cols) == 1:
                col = tbl.c.get(cols[0])
                if col is not None and (
                    col.primary_key or getattr(col, "unique", False)
                ):
                    continue
            uc_name = f"uq_{tbl.name}_" + "_".join(cols)
            tbl.append_constraint(sa.UniqueConstraint(*cols, name=uc_name))

    # ---- PASS 2B: attach FK constraints when safe ----
    for spec in pending_fks:
        this_key = f"{spec['this_schema']}.{spec['this_table']}"
        this_tbl = built.get(this_key)
        if this_tbl is None:
            continue

        ref_key = f"{spec['ref_schema']}.{spec['ref_table']}"
        local_cols = spec["local_cols"]
        ref_cols = spec["ref_cols"]

        # Safe to attach FK?
        safe = False
        if len(ref_cols) == 1 and ref_cols[0] == "id":
            safe = True  # PK is always unique
        elif ref_key in built:
            safe = True  # we just added UNIQUE on target in this batch

        if not safe:
            logger.warning(
                "Skipping FK on %s(%s) -> %s(%s): referenced table not in this batch and "
                "target column(s) are not the PK. Add a UNIQUE on the target table or include it in the same batch.",
                this_key,
                ",".join(local_cols),
                ref_key,
                ",".join(ref_cols),
            )
            continue

        # Attach table-level FK constraint (supports composite)
        this_tbl.append_constraint(
            sa.ForeignKeyConstraint(local_cols, [f"{ref_key}.{c}" for c in ref_cols])
        )

    return tables


def check_oep_api_schema_whitelist(oem_schema):
    """
    Check if the used schema is supported by the oep-api. Implementing api restrictions.

    :param oem_schema:string
    :return: bool
    """
    api_open_schema = ["model_draft", "sandbox"]

    if oem_schema in api_open_schema:
        return True
    else:
        logger.info(
            "The OEP-API does not allow to write un-reviewed data to another schema then 'model_draft' or 'sandbox'"
        )
        return False


def select_oem_dir(oem_folder_name=None, filename=None):
    """
    Select the metadata directory or file that is used to generate the tables.
    The default is the current directory (where you execute the script from)
    inside a folder called oem_folder.

    :param oem_folder_name:
    :param filename:
    :return: string (path to current directory + folder name) or none
    """
    if oem_folder_name is not None:
        oem_path = pathlib.Path.cwd() / oem_folder_name
        return oem_path
    elif oem_folder_name == "default":
        pass
        # default_oem_path =
    else:
        raise FileNotFoundError


def collect_tables_from_oem_files(db: DB, oem_folder_path):
    tables = []

    metadata_files = [
        str(file) for file in oem_folder_path.iterdir() if file.suffix == ".json"
    ]

    for metadata_file in metadata_files:
        try:
            md_tables = create_tables_from_metadata_file(db, metadata_file)
            logger.info(md_tables)
        except Exception:
            logger.error(
                f'Could not generate tables from metadatafile: "{metadata_file}"'
            )
            raise
        tables.extend(md_tables)

    return order_tables_by_foreign_keys(tables)


def collect_tables_from_oem_object(db: DB, oems: list):
    tables = []

    for metadata in oems:
        try:
            md_tables = create_tables_from_metadata_file(db, metadata)
            logger.info(md_tables)
        except Exception:
            logger.error(
                "Could not generate tables from metadata object: "
                f'{metadata.get("name", "unknown")}'
            )
            raise
        tables.extend(md_tables)

    return order_tables_by_foreign_keys(tables)


def load_json(filepath):
    logger.info("Reading metadata: %s" % filepath)
    with open(filepath, "rb") as f:
        return json.load(f)


def mdToDict(oem_folder_path, file_name=None):
    """
    Prepares the JSON String for the sql comment on table
    Required: The .json file names must contain the file name parameter.
    Instruction: Check the SQL "comment on table" for each table
                (e.g. use pgAdmin, OEP-API or OEP/dataedit)
    Parameters
    ----------
    oem_folder_path:
            path to metadata directory
    file_name:  str
            metadata file name
    Returns
    -------
    data:str
            Contains the .json file as dict
    """

    if oem_folder_path is not None:
        metadata_files = [str(file) for file in oem_folder_path.iterdir()]
    else:
        metadata_files = None
        print("Please provide a path to the metadata folder")
        pass

    if file_name is not None:
        for json_file in metadata_files:
            if file_name in json_file:
                try:
                    data = load_json(json_file)
                    return data

                except FileNotFoundError:
                    logger.error("Unable to load the file: " + json_file)
    else:
        logger.error("Please provide the name of the metadata file")


def parseDatapackageToString(oem_folder_path, datapackage_name=None, table_name=None):
    """
    Implement automation to upload metadata to all tables of a single datapackage.json file.
    :param oem_folder_path:
    :param datapackage_name:
    :param table_name:
    :return:
    """
    raise NotImplemented


def api_updateMdOnTable(metadata, table: str, token=None):
    """ """
    schema = "data"
    # table = getTableSchemaNameFromOEM(metadata)[1]

    logger.info(f"Update metadata on table: {table}")
    api_action = setupApiAction(schema, table, token)
    resp = requests.post(
        api_action.dest_url,
        json=metadata,
        headers=api_action.headers,
    )
    if resp.status_code == 200:
        logger.info(f"METADATA SUCCESSFULLY UPDATED: {table}")
        logger.info(f"Link to updated metadata on OEP: {api_action.dest_url}")
    else:
        oep_err_msg_header = re.search("<h3>(.*)</h3>", resp.text)
        err_message = (
            f"Uploading of metadata failed. HTTPS response from OEP: {resp.status_code}, Message: {oep_err_msg_header}, URL: {resp.url}"
            ""
        )
        if not resp.text.startswith("{"):
            raise MetadataError(
                f"The response text doesn't seem to be a json: {resp.text[:40]}..... \n\n Please check "
                f"that the table is already created on the OEP! \n {err_message}"
            )
        else:
            # in case a json is returned and there is a json error
            raise MetadataError(err_message, resp.json())


def push_resource_meta(
    resource: dict, *, table: str, version: str = "2.0", token=None
) -> None:
    """
    Build a minimal OEM v2 doc using omi's template, drop in the single resource,
    validate, then POST to /meta.
    """
    spec = get_metadata_specification(version)
    base = deepcopy(spec.template) if spec.template else {"resources": [{}]}
    # keep optional helpful parts from example
    if spec.example and "@context" in spec.example:
        base["@context"] = deepcopy(spec.example["@context"])
    if spec.example and "metaMetadata" in spec.example:
        base["metaMetadata"] = deepcopy(spec.example["metaMetadata"])

    base["resources"] = [resource]
    validate_metadata(base, check_license=False)

    if not token:
        token = setUserToken()

    api_updateMdOnTable(base, table, token)


def api_downloadMd(schema, table, token=None):
    """ """
    logger.info("DOWNLOAD_METADATA")
    api_action = setupApiAction(schema, table, token)
    res = requests.get(api_action.dest_url)
    res = res.json()
    logger.info("   ok.")
    return res


def saveMdToJson(data, filepath, encoding="utf-8"):
    logger.info("saving %s" % filepath)
    with open(filepath, "w", encoding=encoding) as f:
        return json.dump(data, f, sort_keys=True, indent=2)


def getTableSchemaNameFromOEM(metadata):
    try:
        schema_name = metadata["resources"][0]["name"]
        if "." in schema_name:
            schema, tablename = schema_name.split(".")
            return schema, tablename
        else:
            return None, metadata["resources"][0]["name"]
    except Exception:
        raise Exception("table name not found in metadata (name in resource[0])")


def setUserToken(token=None):
    # Simple user input.
    # This function is implemented as helper

    if token:
        return token

    try:
        token = os.environ["OEP_TOKEN"]
    except KeyError:
        token = getpass.getpass("OEP-Token:")

    if token is not None:
        return token
    else:
        print("Please provide your OEP-API token.")
