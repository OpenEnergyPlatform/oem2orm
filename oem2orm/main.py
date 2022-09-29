
import click
import pathlib

from oem2orm import oep_oedialect_oem2orm


@click.group()
def cli():
    pass


@cli.command()
@click.argument('metadata-folder', type=click.Path(exists=True))
def create_tables(metadata_folder):
    db = oep_oedialect_oem2orm.setup_db_connection()
    folder = pathlib.Path.cwd() / metadata_folder
    tables = oep_oedialect_oem2orm.collect_tables_from_oem(db, folder)
    oep_oedialect_oem2orm.create_tables(db, tables)


@cli.command()
@click.argument('metadata-folder', type=click.Path(exists=True))
def delete_tables(metadata_folder):
    db = oep_oedialect_oem2orm.setup_db_connection()
    folder = pathlib.Path.cwd() / metadata_folder
    tables = oep_oedialect_oem2orm.collect_tables_from_oem(db, folder)
    oep_oedialect_oem2orm.delete_tables(db, tables)


if __name__ == '__main__':
    cli()
