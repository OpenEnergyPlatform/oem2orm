# OEM to ORM

Create database tables (and schema) from oemetadata json file(s)

## Installation:

You can install pacakge using standard python installation:
`
pip install oem2orm
`

or if you interested in CLI-version only you can install it using pipx (pipx must be installed):
`
pipx install oem2orm
`
see [Pipx-Documentation](https://pypa.github.io/pipx/) for further information.


## Usage:

This tool is part of the open-energy-metadata (OEM) integration into the [OEP](https://openenergy-platform.org/).
To use this tool with the OEP API you need to be signed up to the OEP since
you need to provide an API-Token. 

If you want to upload OEM that was officially reviewed you must clone the
OEP data-preprocessing repository on [GitHub](https://github.com/OpenEnergyPlatform/data-preprocessing).
The data-review folder contains all of the successfully reviewed OEM files.

For security reasons, tables can only be created in existing 
schemas and just in the schemas "model_draft" and "sandbox".

Keep in mind the current state is not fully tested. The code is
still quit error prone f.e. the postgres types (column datatype) are not fully 
supported by the [oedialct](https://pypi.org/project/oedialect/) - work in progress.

### Terminal/CLI-Application
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

### Import as Module

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

## Docs:

### Database connection
We use a global namedtuple called "DB" To store the sqlalchemy connection objects engine and metadata.
The namedtuple is available wen import oem2orm in a script. To establish the namedtuple use the function
setup_db_connection(). Now you can use DB.engine or DB.metadata.

### oem2orm generator

#### Supported datatypes

#### Spatial Types
We create columns with spatial datatypes using Geoalchemy2. 

## Database support
