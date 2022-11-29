"""
Module for all functionality regarding the compliance of the integrated standards and 
requirments from other oefamily software modules like omi.

- check if the metadata will pass oep's metadata check that is performed before the saves the metadata.


"""
import logging
import pathlib
import json

from omi.dialects.oep.parser import ParserException
from omi.structure import Compilable

from omi.dialects.oep import OEP_V_1_4_Dialect, OEP_V_1_5_Dialect
from omi.dialects.oep.compiler import JSONCompiler

from omi.dialects.oep.parser import JSONParser

# instances of metadata parsers / compilers, order of priority
METADATA_PARSERS = [OEP_V_1_5_Dialect(), OEP_V_1_4_Dialect()]
METADATA_COMPILERS = [OEP_V_1_5_Dialect(), OEP_V_1_4_Dialect(), JSONCompiler()]

logger = logging.getLogger()

def read_input_json(file_path: pathlib.Path = "tests/data/metadata_v15.json"):
    with open(file_path, "r", encoding="utf-8") as f:
        jsn = json.load(f)

    return jsn


def try_parse_metadata(inp):
    """
    Args:
        inp: string or dict or OEPMetadata
    Returns:
        Tuple[OEPMetadata or None, string or None]:
        The first component is the result of the parsing procedure or `None` if
        the parsing failed. The second component is None, if the parsing failed,
        otherwise an error message.
    """

    if isinstance(inp, Compilable):
        # already parsed
        return inp, None
    elif not isinstance(inp, (str, bytes)):
        # in order to use the omi parsers, input needs to be str (or bytes)
        try:
            inp = json.dumps(inp)
        except Exception:
            return None, "Could not serialize json"

    last_err = None
    # try all the dialects
    for parser in METADATA_PARSERS:
        try:
            return parser.parse(inp), None
        except ParserException as e:
            return None, str(e)
        except Exception as e:
            last_err = e
            # APIError(f"Metadata could not be parsed: {last_err}")
            # try next dialect

    raise Exception(f"Metadata could not be parsed: {last_err}")


def try_compile_metadata(inp):
    """
    Args:
        inp: OEPMetadata
    Returns:
        Tuple[str or None, str or None]:
        The first component is the result of the compiling procedure or `None` if
        the compiling failed. The second component is None if the compiling failed,
        otherwise an error message.
    """
    last_err = None
    # try all the dialects
    for compiler in METADATA_COMPILERS:
        try:
            return compiler.compile(inp), None
        except Exception as e:
            last_err = e
            # APIError(f"Metadata could not be compiled: {last_err}")
            # try next dialect

    raise Exception(f"Metadata could not be compiled: {last_err}")


def check_oemetadata_is_oep_compatible(metadata):
    """Check if metadata is oep compliant. Metadata can be oemetadata version 1.4 or 1.5.
    Args:
        metadata: OEPMetadata or metadata object (dict) or metadata str
    """

    # ---------------------------------------
    # metadata parsing
    # ---------------------------------------

    # parse the metadata object (various types) into proper OEPMetadata instance
    metadata_oep, err = try_parse_metadata(metadata)
    if err:
        raise ValueError(err)
    # compile OEPMetadata instance back into native python object (dict)
    # TODO: we should try to convert to the latest standard in this step?
    metadata_obj, err = try_compile_metadata(metadata_oep)
    if err:
        raise ValueError(err)
    # dump the metadata dict into json string
    try:
        metadata_str = json.dumps(metadata_obj, ensure_ascii=False)
    except Exception:
        raise TypeError("Cannot serialize metadata")


# ----------- USE Cecks and Validation ------
# Make use of omis validation to mock the
# oemetadata check that is performed on the
# OEP for ech metadata upload
# -------------------------------------------


def run_metadata_checks(oemetadata: dict = None, oemetadata_path: str = None,  check_jsonschema: bool = False):
    """
    Runs metadata checks includes:
        - basic oep compliant check - tested by using omi's parsing and compiling

        Optional - included:
        - jsonschema valdiation

    Args:
        oemetadata (dict, optional): OEPMetadata or metadata object (dict) or metadata str. Defaults to None.
        oemetadata_path (str, optional): Relative path to file as string. Defaults to None.

    Raises:
        Exception: _description_
        Exception: _description_
    """

    if oemetadata and oemetadata_path:
        raise Exception(
            "Providing both parmaters at the same time is not permitted. Please provide a oemetadata dict or a oemetadata json file path"
        )

    if oemetadata is None and oemetadata_path is None:
        raise Exception(
            "Please provide a parsed oemetadata dict or a path to the oemetadata json file"
        )

    if oemetadata_path is not None and oemetadata is None:
        metadata = read_input_json(oemetadata_path)

    if oemetadata is not None and oemetadata_path is None:
        metadata = oemetadata

    logger.info("Check if metadata is parsable and compileable by omi.")
    check_oemetadata_is_oep_compatible(metadata=metadata)

    if check_jsonschema:
        logger.info("Check if metadata is valid against the jsonschema.")
        parser_validation = JSONParser()
        schema = parser_validation.get_schema_by_metadata_version(metadata=metadata)
        result = parser_validation.is_valid(inp=metadata, schema=schema)
        if result is False:
            result = result, parser_validation.validate(metadata=metadata, save_report=True)
        
        return result
            

if __name__ == "__main__":
    correct_v15_test_data = "tests/data/metadata_v15.json"
    false_v15_test_data = "tests/data/bad_metadata_v15.json"
    v14_test_data = "tests/data/metadata_v14.json"

    meta = read_input_json(file_path=correct_v15_test_data)
    print("Check v15 metadata from file!")
    result = run_metadata_checks(oemetadata_path=correct_v15_test_data, check_jsonschema=True)
    print("Check v15 metadata from object!")
    run_metadata_checks(oemetadata=meta)

    print("Check v14 metadata!")
    meta = read_input_json(file_path=correct_v15_test_data)

    # print("test expected error case: false usage")
    # run_metadata_checks(oemetadata=meta, oemetadata_path=correct_test_data)
    # print("test expected error case: bad data")
    # run_metadata_checks(oemetadata_path=false_v15_test_data)
