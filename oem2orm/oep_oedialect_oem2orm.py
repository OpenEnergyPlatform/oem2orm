__copyright__ = "Reiner Lemoine Institut"
__license__ = "GNU Affero General Public License Version 3 (AGPL-3.0)"
__url__ = "https://github.com/openego/data_processing/blob/master/LICENSE"
__author__ = "henhuy, jh-RLI"

import os
from collections import namedtuple
from typing import List, Union
import json
import logging
import pathlib
import jmespath
import getpass
import sqlalchemy as sa
import re
import requests

import oedialect

from oem2orm.postgresql_types import TYPES
from oem2orm.oep_compliance import run_metadata_checks
from oem2orm.settings import OEP_URL, OEP_API_URL

# prepare connection string to connect via oep API
CONNECTION_STRING = "{engine}://{user}:{token}@{host}"
#
DB = namedtuple("Database", ["engine", "metadata"])


class CredentialError(Exception):
    pass


class DatabaseError(Exception):
    pass


class MetadataError(Exception):
    pass


def setup_logger(logger_level: str = "Yes"):
    """
    Easy logging setup depending on user input. Provides a logger for INFO level logging.
    :return: logging.INFO or none
    """

    if re.fullmatch("[Yy]es", logger_level):
        print("Logging activated")
        return logging.basicConfig(
            format="%(levelname)s:%(message)s", level=logging.INFO
        )
    elif re.fullmatch("[Nn]o", logger_level):
        pass


def setup_db_connection(engine="postgresql+oedialect", host=OEP_URL):
    """
    Create SQLAlchemy connection to Database API with Username and Token.
    Default is the OEP RESTful-API.

    :param engine: Database engine, default is postgresql
    :param host: API provider
    :return: DB(sa.engine, sa.metadata) namedtuple
    """

    try:
        user = os.environ["OEP_USER"]
    except KeyError:
        user = input("Enter OEP-username:")

    token = setUserToken()

    # Generate connection string:
    conn_str = CONNECTION_STRING
    conn_str = conn_str.format(engine=engine, user=user, token=token, host=host)

    engine = sa.create_engine(conn_str)
    metadata = sa.MetaData(bind=engine)
    return DB(engine, metadata)


def setupApiAction(schema, table, token=None):
    API_ACTION = namedtuple("API_Action", ["dest_url", "headers"])

    url = OEP_API_URL + "schema/{schema}/tables/{table}/meta/".format(
        schema=schema, table=table
    )

    token = token if token else setUserToken()
    headers = {
        "Authorization": "Token %s" % token,
        "Accept": "application/json",
        "Content-Type": "application/json",
    }

    return API_ACTION(url, headers)


def create_tables(db: DB, tables: List[sa.Table]):
    """
    Creates a SQLAlchemy create ORM table-objects via API connection on a Database.
    The tables can be a list of ORM.

    :param db: API
    :param tables: SQLAlchemy ORM objects (automatically retrieved from OEM json strings)
    :return: none
    """
    for table in tables:
        logging.info(f"Working on table: {table}")
        if not db.engine.dialect.has_schema(db.engine, table.schema):
            error_msg = (
                f'The provided database schema: "{table.schema}" does not exist. Please use an existing '
                f"schema from the `name` column from: {OEP_URL}/dataedit/schemas"
            )
            logging.info(error_msg)
            raise DatabaseError(error_msg)
        else:
            if not db.engine.dialect.has_table(db.engine, table.name, table.schema):
                try:
                    table.create(checkfirst=True)
                    logging.info(f"Created table {table.name}")
                except oedialect.engine.ConnectionException as ce:
                    error_msg = (
                        f'Error when uploading table "{table.name}". Reason: {ce}.'
                    )
                    logging.error(error_msg)
                    raise DatabaseError(error_msg) from ce
                except sa.exc.ProgrammingError as pe:
                    error_msg = f'Table "{table.name}" already exists.'
                    logging.error(error_msg)
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

    tables_raw = jmespath.search("resources", metadata) or []
    tables: List[sa.Table] = []

    # keep for later if you push updated metadata elsewhere
    normalized_resources: list[dict] = []

    for res in tables_raw:
        # normalize table + columns + PK/FK names in place
        norm_table_name, _ = normalize_resource_inplace(res)
        normalized_resources.append(res)

        if not norm_table_name:
            raise MetadataError("Cannot read table name (and schema)", res.get("name"))

        schema = "model_draft"  # OEP creation always in draft/sandbox

        # ---- build FK map once (post-normalization) ----
        foreign_keys: dict[str, dict] = {}
        for fk in res.get("schema", {}).get("foreignKeys") or []:
            local_fields = fk.get("fields")
            if isinstance(local_fields, str):
                local_fields = [local_fields]
            reference = fk.get("reference") or {}
            for lf in local_fields or []:
                foreign_keys[lf] = reference

        # ---- fields (already normalized by normalize_resource_inplace) ----
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

        # Helper to build schema-qualified FK target
        def _fk_target(resource: str, ref_field_raw) -> str:
            # preserve schema.table if provided
            schema_part, table_part = ("model_draft", resource or "")
            if resource and "." in resource:
                schema_part, table_part = resource.split(".", 1)
            # normalize each piece with your existing normalizers
            norm_table = TABLE_NORMALIZER(table_part)
            # default remote field to 'id', then normalize as column
            if isinstance(ref_field_raw, list) and ref_field_raw:
                ref_field = COLUMN_NORMALIZER(ref_field_raw[0])
            else:
                ref_field = COLUMN_NORMALIZER(ref_field_raw or "id")
            # schema.table.column (or table.column if no schema)
            return (
                f"{schema_part}.{norm_table}.{ref_field}"
                if schema_part
                else f"{norm_table}.{ref_field}"
            )

        # Add remaining columns
        for field in fields:
            fname = field["name"]  # ≤ MAX_COLUMN_LEN, normalized
            try:
                column_type = TYPES[field["type"]]
            except (KeyError, ValueError):
                raise MetadataError(
                    "Unknown column type", field, field.get("type"), metadata_file
                )

            comment = field.get("description")
            pk_flag = fname == "id"  # only 'id' may be PK

            if fname in foreign_keys:
                ref = foreign_keys[fname] or {}
                target = _fk_target(ref.get("resource", ""), ref.get("fields"))
                column = sa.Column(
                    fname,
                    column_type,
                    sa.ForeignKey(target),
                    primary_key=pk_flag,
                    comment=comment,
                )
            else:
                column = sa.Column(
                    fname,
                    column_type,
                    primary_key=pk_flag,
                    comment=comment,
                )

            columns.append(column)

        # enforce allowed schema; create Table
        if not check_oep_api_schema_whitelist(schema):
            logging.info("The current schema:'%s' is changed to 'model_draft'", schema)
            schema = "model_draft"

        tables.append(
            sa.Table(
                norm_table_name,
                db.metadata,
                *columns,
                schema=schema,
                extend_existing=True,
            )
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
        logging.info(
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


def collect_tables_from_oem(db: DB, oem_folder_path):
    tables = []
    metadata_files = [
        str(file) for file in oem_folder_path.iterdir() if file.suffix == ".json"
    ]

    for metadata_file in metadata_files:
        try:
            md_tables = create_tables_from_metadata_file(db, metadata_file)
            logging.info(md_tables)
        except:
            logging.error(
                f'Could not generate tables from metadatafile: "{metadata_file}"'
            )
            raise
        tables.extend(md_tables)

    return order_tables_by_foreign_keys(tables)


def load_json(filepath):
    logging.info("Reading metadata: %s" % filepath)
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
                    logging.error("Unable to load the file: " + json_file)
    else:
        logging.error("Please provide the name of the metadata file")


def parseDatapackageToString(oem_folder_path, datapackage_name=None, table_name=None):
    """
    Implement automation to upload metadata to all tables of a single datapackage.json file.
    :param oem_folder_path:
    :param datapackage_name:
    :param table_name:
    :return:
    """
    raise NotImplemented


def api_updateMdOnTable(metadata, token=None):
    """ """
    schema = getTableSchemaNameFromOEM(metadata)[0]
    table = getTableSchemaNameFromOEM(metadata)[1]

    logging.info(f"Update metadata on table: {table}")
    api_action = setupApiAction(schema, table, token)
    resp = requests.post(api_action.dest_url, json=metadata, headers=api_action.headers)
    if resp.status_code == 200:
        logging.info(f"METADATA SUCCESSFULLY UPDATED: {table}")
        logging.info(f"Link to updated metadata on OEP: {api_action.dest_url}")
    else:
        oep_err_msg_header = re.search("<h3>(.*)</h3>", resp.text).group(1)
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


def api_downloadMd(schema, table, token=None):
    """ """
    logging.info("DOWNLOAD_METADATA")
    api_action = setupApiAction(schema, table, token)
    res = requests.get(api_action.dest_url)
    res = res.json()
    logging.info("   ok.")
    return res


def saveMdToJson(data, filepath, encoding="utf-8"):
    logging.info("saving %s" % filepath)
    with open(filepath, "w", encoding=encoding) as f:
        return json.dump(data, f, sort_keys=True, indent=2)


def moveTableToSchema(engine, destination_schema):
    raise NotImplemented


# TODO: rename or remove this function - functionality moved to oep_complicance module, keep to avoide 3. party implementation errors
def omi_validateMd(data: dict, jsonschema_validation=False):
    run_metadata_checks(oemetadata=data, check_jsonschema=jsonschema_validation)


def getTableSchemaNameFromOEM(metadata):
    try:
        schema_name = metadata["resources"][0]["name"]
        if "." in schema_name:
            schema, tablename = schema_name.split(".")
            return schema, tablename
    except:
        raise Exception("table name not found in metadata (name in resource[0])")


def setUserToken():
    # Simple user input.
    # This function is implemented as helper

    try:
        token = os.environ["OEP_TOKEN"]
    except KeyError:
        token = getpass.getpass("OEP-Token:")

    if token is not None:
        return token
    else:
        print("Please provide your OEP-API token.")
