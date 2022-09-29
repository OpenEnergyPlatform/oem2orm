# Changelog

All notable changes to this project will be documented in this file.

The format is inpired from [Keep a Changelog](http://keepachangelog.com/en/1.0.0/)
and the versiong aim to respect [Semantic Versioning](http://semver.org/spec/v2.0.0.html).

Here is a template for new release sections

```
Template:

## Current
### Added
- basic description
### Changed
- basic description
### Removed
- basic description

## [_._._] - 20XX-MM-DD

### Added
- basic description [#PR/#Issue/#Commit]
### Changed
- basic description [#PR/#Issue/#Commit]
### Removed
- basic description [#PR/#Issue/#Commit]
```

## [Unreleased] - 20XX-MM-DD

### Added
- Metadata upload in case of single table in OEM

-

### Changed

-

### Removed

______________________________________________________________________

## [v0.3.3] - 2024-04-15

### Added

- New settings module [#44](https://github.com/OpenEnergyPlatform/oem2orm/pull/44)

### Changed

- Improve logging and error messages [table creation, data upload, metadata registration](#38)
- Fix error if field type is None
- Update oep host url [#44](https://github.com/OpenEnergyPlatform/oem2orm/pull/44)

______________________________________________________________________

## [0.3.2] - 2022-11-29

### Added

- token can be passed as parameter (to support usage in APIs)

### Changed

- Error is raised if schema does not exist
- Metadata compilance checks now inculue optinal jsonschema validation for metadata (PR#32)
- MetadataError is thrown if uploading metadata to OEP fails

______________________________________________________________________

## [0.3.1] - 2022-10-24

### Changed

- fix module not installed error after pip install and import of oem2orm PR(#26)

______________________________________________________________________

## [0.3.0] - 2022-10-24

### Added

- Option to create tables from OEM JSON instead of file
- New module to check if metadata is oep compliant. Can check (omi's 1 parse 2 compile) oemetadata v1.5 and v1.4 (PR#23)
- Add PYPI release workflow to automate python package releases for pypi test and pypi official (PR#22)

### Changed

- omi_validateMD was outdated and now runs the new oep compliance checks.  

______________________________________________________________________

## [0.2.7] - 2021-03-11

### Added

- enable console usage [PR#8]
- new package requirement "omi"
- support for sqlachemy "numeric" data type

### Changed

- fix missing dependency that made pip install fail [ISSUE#1;PR#8]

### Removed

- console script, remove table delete

______________________________________________________________________

## [0.2.6] - 2020-09-23

### Added

- support for datatypes "hstore" and "decimal"
- provide new example files that work with oem2orm

______________________________________________________________________

## [0.2.5] - 2020-08-06

### Changed

- fix installation error caused by jmespath package dependency

______________________________________________________________________

## [0.2.4] - 2020-07-20

### Added

- Support to setup the OEP API-URL
- Metadata Up- and download are supported
- Save downloaded metadata to file
- Validate metadata using OMI parser v1.4.0

### Changed

- change functions names

______________________________________________________________________

## [0.2.3] - 2020-06-02

### Added

- provide a minimal working example as jupyter notebook tutorial
- New OEP-API related functions: Prepare the oemetadata string to send to api
- Simple User Input function to set the OEP-API-Token

### Changed

- Update README
- include OEP public schema (whitelist) check
- Spatial types from Geoalchemy2 do not set a spatial_index anymore

______________________________________________________________________

## [0.2.2] - 2020-06-02

### Added

- new function: setting up a logger

### Changed

- add missing input parameter
- extended description in changelog
- Fix logging

______________________________________________________________________

## [0.2.0] - 2020-05-27

### Added

- new function: delete tables from DB now possible
- new function: select the oem data folder
- new function: tables are collected and ordered by fk (increase usability)

### Changed

- added docstrings

### Removed

- the user is no longer required to use a for loop in the main function to collect tables
