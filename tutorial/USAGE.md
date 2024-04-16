# Usage

This section gets you started with using the oem2orm tool.

## oemetadata compliance check

It is mandatory for oem2orm that you provide a valid oemetadata as input. Otherwise the functionality can not be granted. To provide some tooling within oem2orm that helps you check your metadata JSON files you can use the module `oep_compliance.py`.

Run the oemetadata check (currently only for oemetadata version up to 1.5.2):

    from oem2orm.oep_compliance import run_metadata_checks
    # assuming your oemetadata file is in a directory called "data" 
    run_metadata_checks(oemetadata = None, oemetadata_path = "data/oemetadata.json", check_jsonschema = False)

## Terminal/CLI-Application

Step-by-Step:
0. pip and python have to be installed and setup on your machine

1. Create env from requirements.txt, and activate
2. Put the metadata file in the folder metadata or put your own folder in this
    directory
3. execute the following in a terminal:

```
pipx install oem2orm
oem2orm
Enter metadata folder name:
...
```

4. Provide credentials and folder name in prompt
5. The table will be created

## Import as Module

You can simply import this module in your Python script.py like this:

```python
from oem2orm import oep_oedialect_oem2orm as oem2orm
```

Now just call the functions provided in oem2orm like this:

Recommended execution order:

- Setup the logger

```python
oem2orm.setup_logger()
```

- Setup the Database API connection as Namedtuple storing the SQLAlchemy engine and metadata:

```python
db = oem2orm.setup_db_connection()
```

- Provide the oem files in a folder (in the current directory).
- Pass the folder name to the function:

```python
metadata_folder = oem2orm.select_oem_dir(oem_folder_name="folder_name")
```

- Setup a SQLAlchemy ORM including all data-model in the provided oem files:

```python
orm = oem2orm.collect_ordered_tables_from_oem(db, metadata_folder)
```

- Create the tables on the Database:

```python
oem2orm.create_tables(db, orm)
```

- Delete all tables that have been created (all tables available in sa.metadata)

```python
oem2orm.delete_tables(db, orm)
```
