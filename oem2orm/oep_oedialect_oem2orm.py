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
            error_msg = f'The provided database schema: "{table.schema}" does not exist. Please use an existing ' \
                        f'schema from the `name` column from: {OEP_URL}/dataedit/schemas'
            logging.info(error_msg)
            raise DatabaseError(error_msg)
        else:
            if not db.engine.dialect.has_table(db.engine, table.name, table.schema):
                try:
                    table.create(checkfirst=True)
                    logging.info(f"Created table {table.name}")
                except oedialect.engine.ConnectionException as ce:
                    error_msg = f'Error when uploading table "{table.name}". Reason: {ce}.'
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
    """
    Takes a metadata file in oem format (tested with oem v1.4.0) and
    generates a sqlalchemy ORM Table representation. The oem can contain
    multiple Tables, this function will return one or multiple sa table objects.

    :param db: API
    :param metadata_file: json/json file (oem 1.4.0)
    :return: collection of sqlalchemy table objects
    """
    if isinstance(metadata_file, str):
        with open(metadata_file, "r") as metadata_json:
            metadata = json.loads(metadata_json.read())
    else:
        metadata = metadata_file
    tables_raw = jmespath.search("resources", metadata)

    tables = []
    for table in tables_raw:
        # Get (schema) and table name:
        schema_table_str = table["name"].split(".")
        if len(schema_table_str) == 1:
            schema = "model_draft"
            table_name = schema_table_str[0]
        elif len(schema_table_str) == 2:
            schema, table_name = schema_table_str
        else:
            raise MetadataError("Cannot read table name (and schema)", table["name"])

        # Get primary keys:
        primary_keys = jmespath.search("schema.primaryKey[*]", table)
        # Get foreign_keys:
        foreign_keys = {
            fk["fields"][0]: fk["reference"]
            for fk in jmespath.search("schema.foreignKeys", table)
        }
        # Create columns:
        columns = []
        for field in jmespath.search("schema.fields[*]", table):
            # Get column type:
            try:
                column_type = TYPES[field["type"]]
            except (KeyError, ValueError):
                raise MetadataError(
                    "Unknown column type", field, field["type"], metadata_file
                )

            if field["name"] in foreign_keys:
                foreign_key = foreign_keys[field["name"]]
                column = sa.Column(
                    field["name"],
                    column_type,
                    sa.ForeignKey(
                        f'{foreign_key["resource"]}.{foreign_key["fields"][0]}'
                    ),
                    primary_key=field["name"] in primary_keys,
                    comment=field["description"],
                )
            else:
                column = sa.Column(
                    field["name"],
                    column_type,
                    primary_key=field["name"] in primary_keys,
                    comment=field["description"],
                )
            columns.append(column)

        if check_oep_api_schema_whitelist(schema):
            tables.append(
                sa.Table(
                    table_name,
                    db.metadata,
                    *columns,
                    schema=schema,
                    extend_existing=True,
                )
            )
        else:
            logging.info(
                "The current schema:'" + schema + "' is changed to 'model_draft'"
            )
            schema = "model_draft"
            tables.append(
                sa.Table(
                    table_name,
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
