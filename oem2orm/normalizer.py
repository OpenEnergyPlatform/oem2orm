__copyright__ = "Reiner Lemoine Institut"
__license__ = "GNU Affero General Public License Version 3 (AGPL-3.0)"
__url__ = "https://github.com/openego/data_processing/blob/master/LICENSE"
__author__ = "jh-RLI"

from typing import Tuple, List, Optional
import re

from oem2orm import logs

logger = logs.setup_logging()

MAX_TABLE_LEN = 49
MAX_COLUMN_LEN = 50
DEFAULT_SCHEMA = "model_draft"


def compose_normalizers(*funcs):
    """Compose multiple 'str -> str' transformers into one normalizer."""

    def _inner(s: str) -> str:
        for f in funcs:
            s = f(s)
        return s

    return _inner


def de_umlaut(s: str) -> str:
    if not s:
        return s
    return (
        s.replace("Ä", "Ae")
        .replace("Ö", "Oe")
        .replace("Ü", "Ue")
        .replace("ä", "ae")
        .replace("ö", "oe")
        .replace("ü", "ue")
        .replace("ß", "ss")
    )


def _pg_sanitize_base(name: str) -> str:
    """Lowercase, [a-z0-9_], starts with [a-z_]."""
    if not isinstance(name, str):
        name = str(name or "")
    s = name.strip().lower()
    s = re.sub(r"[\s\-]+", "_", s)
    s = re.sub(r"[^a-z0-9_]", "", s)
    return s


def normalize_table_identifier(name: str) -> str:
    """Sanitize and then truncate to MAX_TABLE_LEN (no hash)."""
    raw = str(name or "")
    s = _pg_sanitize_base(raw)
    out = s[:MAX_TABLE_LEN]

    # log on any change: case-fold, char strip, dash->underscore, or truncation
    if out != raw:
        truncated_note = " (truncated)" if len(s) > MAX_TABLE_LEN else ""
        logger.info(f'Normalized table name "{raw}" -> "{out}"{truncated_note}')

    return out


def normalize_column_identifier(name: str) -> str:
    """Sanitize and then truncate to MAX_COLUMN_LEN (no hash)."""
    raw = str(name or "")
    s = _pg_sanitize_base(raw)
    out = s[:MAX_COLUMN_LEN]

    # log on any change: case, chars removed, dash->underscore, truncation
    if out != raw:
        truncated_note = " (truncated)" if len(s) > MAX_COLUMN_LEN else ""
        logger.info(f'Normalized column name "{raw}" -> "{out}"{truncated_note}')

    return out


def _split_schema_table(resource: str) -> Tuple[Optional[str], str]:
    """Split 'schema.table' => ('schema','table'); 'table' => (None,'table')."""
    if not resource:
        return None, ""
    parts = str(resource).split(".", 1)
    return (parts[0], parts[1]) if len(parts) == 2 else (None, parts[0])


def split_schema_table(
    resource: str, default_schema: Optional[str] = None
) -> Tuple[Optional[str], str]:
    """
    'schema.table' -> ('schema','table')
    'table'        -> (default_schema or None, 'table')
    """
    schema, table = _split_schema_table(resource)
    return (schema or default_schema, table)


def normalize_resource_ref(resource: str) -> str:
    """
    Normalize a FK reference 'resource' while preserving schema.
    Example: 'model_draft.Bus' -> 'model_draft.bus'
    """
    schema, table = _split_schema_table(resource)
    norm_table = normalize_table_identifier(table)
    return f"{schema}.{norm_table}" if schema else norm_table


# Two distinct pipelines (add/remove steps like de_umlaut as you like)
TABLE_NORMALIZER = compose_normalizers(de_umlaut, normalize_table_identifier)
COLUMN_NORMALIZER = compose_normalizers(de_umlaut, normalize_column_identifier)


def build_unique_column_map(
    orig_names: List[str], *, normalizer=COLUMN_NORMALIZER
) -> dict[str, str]:
    """Original -> unique normalized names (no collisions after normalize/trim)."""
    used: set[str] = set()
    mapping: dict[str, str] = {}
    for orig in orig_names:
        base = normalizer(orig)
        cand = base
        i = 1
        while cand in used:
            suffix = f"_{i}"
            lim = MAX_COLUMN_LEN - len(suffix)
            cand = base[:lim] + suffix
            i += 1
        used.add(cand)
        mapping[orig] = cand
    return mapping


def _map_key_names(
    names, cmap: dict[str, str], *, normalizer=COLUMN_NORMALIZER
) -> list[str]:
    """Map primaryKey/foreignKey 'fields' to normalized column names."""
    if not names:
        return []
    if isinstance(names, str):
        return [cmap.get(names, normalizer(names))]
    if isinstance(names, list):
        return [cmap.get(n, normalizer(n)) for n in names]
    return [normalizer(str(names))]


def normalize_resource_inplace(
    res: dict, *, table_norm=TABLE_NORMALIZER, col_norm=COLUMN_NORMALIZER
) -> Tuple[str, dict[str, str]]:
    """
    Mutate resource in place:
      - normalize resource['name'] (table) with table_norm
      - normalize fields[*].name with col_norm
      - remap schema.primaryKey and schema.foreignKeys using col_norm
      - normalize reference.resource with table_norm, reference.fields with col_norm
    Returns (normalized_table_name, column_map)
    """
    norm_table = table_norm(res.get("name") or "")
    res["name"] = norm_table

    schema = res.setdefault("schema", {})
    fields = schema.get("fields") or []
    orig_field_names = [f.get("name", "") for f in fields]
    col_map = build_unique_column_map(orig_field_names, normalizer=col_norm)

    # normalize field names in-place
    for f in fields:
        o = f.get("name", "")
        f["name"] = col_map[o]

    # primary key(s)
    pk = schema.get("primaryKey")
    if pk:
        mapped = _map_key_names(pk, col_map, normalizer=col_norm)
        schema["primaryKey"] = mapped if len(mapped) > 1 else mapped[0]

    # foreign keys
    for fk in schema.get("foreignKeys") or []:
        # local fields (columns on this table)
        mapped_local = _map_key_names(fk.get("fields"), col_map, normalizer=col_norm)
        fk["fields"] = mapped_local if len(mapped_local) > 1 else mapped_local[0]

        # reference
        ref = fk.setdefault("reference", {})
        if "resource" in ref:
            ref["resource"] = normalize_resource_ref(ref["resource"])
        if "fields" in ref:
            mapped_ref = _map_key_names(ref["fields"], {}, normalizer=col_norm)
            ref["fields"] = mapped_ref if len(mapped_ref) > 1 else mapped_ref[0]

    return norm_table, col_map


def strip_blank_fk_and_keys(res: dict) -> dict:
    """
    Clean OEM resource schema:
      - drop fields with blank names
      - drop/clean primaryKey if blank
      - drop FK entries with no local fields or no reference.resource
      - allow empty reference.fields (defaults to id later)
    Returns the same dict (mutated) for convenience.
    """
    schema = res.setdefault("schema", {})

    # fields: remove entries with blank/whitespace names
    fields = []
    for f in schema.get("fields") or []:
        if isinstance(f, dict):
            name = (f.get("name") or "").strip()
            if name:
                fields.append(f)
    schema["fields"] = fields

    # primaryKey: normalize/remove blanks
    pk = schema.get("primaryKey")
    if isinstance(pk, list):
        pk = [n.strip() for n in pk if isinstance(n, str) and n.strip()]
        if pk:
            schema["primaryKey"] = pk
        else:
            schema.pop("primaryKey", None)
    elif isinstance(pk, str):
        if pk.strip():
            schema["primaryKey"] = pk.strip()
        else:
            schema.pop("primaryKey", None)
    else:
        schema.pop("primaryKey", None)

    # foreignKeys: keep only well-formed; clean blanks
    clean_fks = []
    for fk in schema.get("foreignKeys") or []:
        if not isinstance(fk, dict):
            continue

        # local fields
        local = fk.get("fields")
        if isinstance(local, list):
            local = [n.strip() for n in local if isinstance(n, str) and n.strip()]
        elif isinstance(local, str):
            local = [local.strip()] if local.strip() else []
        else:
            local = []

        # reference
        ref = fk.get("reference") or {}
        ref_resource = (ref.get("resource") or "").strip()
        ref_fields = ref.get("fields")
        if isinstance(ref_fields, list):
            ref_fields = [
                n.strip() for n in ref_fields if isinstance(n, str) and n.strip()
            ]
        elif isinstance(ref_fields, str):
            ref_fields = [ref_fields.strip()] if ref_fields.strip() else []
        else:
            ref_fields = []

        # require: some local column(s) AND a target resource
        if not local or not ref_resource:
            continue

        # rebuild cleaned FK
        fk_clean = {
            "fields": local if len(local) > 1 else local[0],
            "reference": {"resource": ref_resource},
        }
        if ref_fields:
            fk_clean["reference"]["fields"] = (
                ref_fields if len(ref_fields) > 1 else ref_fields[0]
            )

        clean_fks.append(fk_clean)

    if clean_fks:
        schema["foreignKeys"] = clean_fks
    else:
        schema.pop("foreignKeys", None)

    return res
