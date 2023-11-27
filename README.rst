
.. figure:: https://user-images.githubusercontent.com/14353512/185425447-85dbcde9-f3a2-4f06-a2db-0dee43af2f5f.png
    :align: left
    :target: https://github.com/rl-institut/super-repo/
    :alt: Repo logo

==========
OEM to ORM
==========

Create database tables (and schema) from oemetadata JSON file(s).

.. list-table::
   :widths: auto

   * - License
     - |badge_license|
   * - Documentation
     - |badge_documentation|
   * - Publication
     -
   * - Development
     - |badge_issue_open| |badge_issue_closes| |badge_pr_open| |badge_pr_closes|
   * - Community
     - |badge_contributing| |badge_contributors| |badge_repo_counts|

.. contents::
    :depth: 2
    :local:
    :backlinks: top

Installation
================

You can install the package using standard Python installation:

.. code-block:: shell

   pip install oem2orm

Or, for CLI-version only, install using pipx (pipx must be installed):

.. code-block:: shell

   pipx install oem2orm

Refer to the `Pipx Documentation <https://pypa.github.io/pipx/>`_ for more information.

Usage
================

This tool is part of the open-energy-metadata (OEM) integration into the `Open Energy Platform (OEP) <https://openenergy-platform.org/>`_. To use this tool with the OEP API, you need to be signed up to the OEP and provide an API-Token.

For uploading officially reviewed OEM, clone the `OEP data-preprocessing repository <https://github.com/OpenEnergyPlatform/data-preprocessing>`_ from GitHub. The data-review folder contains all successfully reviewed OEM files.

For security reasons, tables can only be created in existing schemas and just in the "model_draft" and "sandbox" schemas.

Keep in mind, the current state is not fully tested. The code is still error-prone, e.g., the PostgreSQL types (column datatype) are not fully supported by the `oedialect <https://pypi.org/project/oedialect/>`_ - work in progress.

Terminal/CLI Application
--------------------------

Step-by-Step:

0. pip and Python must be installed and set up on your machine.
1. Create an environment from requirements.txt, and activate it.
2. Put the metadata file in the folder "metadata" or place your folder in this directory.
3. Execute the following in a terminal:

   .. code-block:: shell

      pipx install oem2orm
      oem2orm
      Enter metadata folder name:
      ...

4. Provide credentials and folder name in the prompt.
5. The table will be created.

Import as Module
-------------------

Import the module in your Python script like this:

.. code-block:: python

   from oem2orm import oep_oedialect_oem2orm as oem2orm

Then, call the functions provided in oem2orm:

- Set up the logger:

  .. code-block:: python

     oem2orm.setup_logger()

- Set up the Database API connection as a namedtuple storing the SQLAlchemy engine and metadata:

  .. code-block:: python

     db = oem2orm.setup_db_connection()

- Provide the OEM files in a folder (in the current directory). Pass the folder name to the function:

  .. code-block:: python

     metadata_folder = oem2orm.select_oem_dir(oem_folder_name="folder_name")

- Set up a SQLAlchemy ORM including all data-model in the provided OEM files:

  .. code-block:: python

     orm = oem2orm.collect_ordered_tables_from_oem(db, metadata_folder)

- Create the tables on the Database:

  .. code-block:: python

     oem2orm.create_tables(db, orm)

- Delete all tables that have been created (all tables available in sa.metadata):

  .. code-block:: python

     oem2orm.delete_tables(db, orm)

Docs
================

Database Connection
--------------------

We use a global namedtuple called "DB" to store the SQLAlchemy connection objects engine and metadata. The namedtuple is available when importing oem2orm in a script. Establish the namedtuple using the function `setup_db_connection()`. Then, you can use `DB.engine` or `DB.metadata`.

oem2orm Generator
------------------

Supported Datatypes
================

Spatial Types
================

Columns with spatial datatypes are created using GeoAlchemy2.

Database Support
================



.. |badge_license| image:: https://img.shields.io/github/license/OpenEnergyPlatform/oem2orm
    :target: LICENSE.txt
    :alt: License

.. |badge_documentation| image:: https://img.shields.io/github/actions/workflow/status/OpenEnergyPlatform/oem2orm/gh-pages.yml?branch=production
    :target: https://rl-institut.github.io/oem2orm/
    :alt: Documentation

.. |badge_contributing| image:: https://img.shields.io/badge/contributions-welcome-brightgreen.svg?style=flat
    :alt: contributions

.. |badge_repo_counts| image:: http://hits.dwyl.com/OpenEnergyPlatform/oem2orm.svg
    :alt: counter

.. |badge_contributors| image:: https://img.shields.io/badge/all_contributors-1-orange.svg?style=flat-square
    :alt: contributors

.. |badge_issue_open| image:: https://img.shields.io/github/issues-raw/OpenEnergyPlatform/oem2orm
    :alt: open issues

.. |badge_issue_closes| image:: https://img.shields.io/github/issues-closed-raw/OpenEnergyPlatform/oem2orm
    :alt: closes issues

.. |badge_pr_open| image:: https://img.shields.io/github/issues-pr-raw/OpenEnergyPlatform/oem2orm
    :alt: closes issues

.. |badge_pr_closes| image:: https://img.shields.io/github/issues-pr-closed-raw/OpenEnergyPlatform/oem2orm
    :alt: closes issues