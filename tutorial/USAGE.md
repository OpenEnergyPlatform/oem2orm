# Usage

This section gets you started with using the oem2orm tool.

## oemetadata compliance check

OMI provides the full validation functionality for the oemetadata. It is implemented in the OEP and will make sure your metadata is compliant with the oeplatform requirements.

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

## Common usage

!!! Note

    This approach works out smoother if you use a IDE like pycharm or VScode.

The approach we use is based on 1. a "prepare phase" to provide the tool setup and datapackage artifacts. This includes OEP-API credentials, dataset using the frictionless datapackage style with oemetadata to describe the dataset and other optional developer settings. 2. is the "action phase" which involves setting up date artifacts so the tool can find it which includes setting the dataset name and some general metadata fields like dataset description. Furthermore installing and running the tool source must be 

### The setup

## Internal API for Module access

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
