# oem 2 orm

Create database tables (and schema) from oemetadata json file(s). This tool is part of the open-energy-metadata (OEM) integration into the [OEP](https://openenergyplatform.org/).

## Installation

You can install pacakge using standard python installation:
`
pip install oem2orm
`

or if you interested in CLI-version only you can install it using pipx (pipx must be installed):
`
pipx install oem2orm
`
see [Pipx-Documentation](https://pypa.github.io/pipx/) for further information.

## Usage

Read the Restrictions section and have a look at our [tutorial](./tutorial/USAGE.md) section to get more information about the usage of oem2orm either as code module or CLI tool. The tutorials also provide information how to validate your oemetadata files.

### Restrictions

To use this tool with the OEP API you need to be signed up to the OEP since
you need to provide an API-Token.

For security reasons, tables can only be created in existing
schemas and just in the schemas "model_draft" and "sandbox".

Keep in mind that f.e. the postgres types (column datatype) are not fully
supported by the [oedialct](https://pypi.org/project/oedialect/) - work in progress.

## Docs

### Database connection

We use a global namedtuple called "DB" To store the sqlalchemy connection objects engine and metadata.
The namedtuple is available wen import oem2orm in a script. To establish the namedtuple use the function
setup_db_connection(). Now you can use DB.engine or DB.metadata. In the background the connection is established
using oedialect and the http API of the oeplatform website.

### oem2orm generator

The table objects (ORM) are generated on the fly from an oemetadata.json file. [oemetadata](https://github.com/OpenEnergyPlatform/oemetadata) is a metadata specification of the Open Energy Family. It includes about 50 fields that can be used to provide metadata for tabular data resources.
A subset of these fields are grouped in the key "resources" ([see out example](https://github.com/OpenEnergyPlatform/oemetadata/blob/develop/metadata/v160/example.json#L237-L388)) in the metadata. These fields describe the schema of
the data table (like table name, columns,  data types & table relations).

The method oem2orm provides to create data tables on the OEP. It is especially useful if you attempt to automate the table creation and already use python or already have a oemetadata file available. The alternatives are:

1. [manually describing](https://openenergyplatform.github.io/academy/tutorials/01_api/02_api_upload/#create-table) the table object in JSON and then use the oep HTTP API directly to create a table.  
2. Use the [User Interface of the oeplatform website](https://openenergyplatform.org/dataedit/wizard/) to create a table and upload data.

### Oemetadata format

[Specification for the oemetadata](https://github.com/OpenEnergyPlatform/oemetadata)

#### Oemetadata validation

The oemetadata specification is integrated into the open energy platform using a tool called [omi (metadata integration)](https://github.com/OpenEnergyPlatform/omi). OMI provides functionality to run validation checks on the metadata up to the oemetadata version 1.6.0. oem2orm also provides a minimal oep compliance check that mocks the checks that are run on the oep website once the metadata is uploaded to a table.

#### Supported column data types

Currently oem2orm supports

        "bigint"
        "int":
        "integer"
        "varchar"
        "json"
        "text"
        "timestamp"
        "interval"
        "string"
        "float"
        "boolean"
        "date"
        "hstore"
        "decimal"
        "numeric"
        "double precision"

#### Spatial Types

    "geometry point": Geometry("POINT",  spatial_index=False),
    "geom": Geometry("GEOMETRY",  spatial_index=False),
    "geometry": Geometry("GEOMETRY",  spatial_index=False),

We create columns with spatial datatypes using Geoalchemy2.

## Database support

We only tested this tool with PostgreSQL & sqlalchemy version 1.3
