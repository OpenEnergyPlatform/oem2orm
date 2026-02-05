import logging
from pathlib import Path
from oem2orm import oep_oedialect_oem2orm as oem2orm
from oem2orm import settings
import pathlib


logging.basicConfig()
logging.getLogger().setLevel(logging.INFO)


def create_tables_on_oedb(metadata_folder_name: Path):
    """
    Create tables on the OEP database based on metadata files.

    :param metadata_folder_name: Path to the folder containing metadata files.
                                    must be part of the current directory.
    """
    db = oem2orm.setup_db_connection(
        host=settings.OEP_URL,
        user=settings.OEP_USER,
        token=settings.OEP_API_TOKEN,
    )
    folder = pathlib.Path.cwd() / metadata_folder_name
    tables = oem2orm.collect_tables_from_oem_files(db, folder)
    oem2orm.create_tables(db, tables)

    # Upload metadata for single table
    # metadata = oem2orm.mdToDict(metadata_folder_name, "datapackage.json")
    # if metadata:
    #     oem2orm.api_updateMdOnTable(metadata)


if __name__ == "__main__":
    path = Path("metadata/")
    create_tables_on_oedb(path)
