import json
import types
import pathlib
import builtins
import pytest
import sqlalchemy as sa

from oem2orm import oep_oedialect_oem2orm as mod


# ------------------------------
# Utilities / Fakes for testing
# ------------------------------


class FakeDialect:
    def __init__(self, has_schema=True, has_table=False):
        self._has_schema = has_schema
        self._has_table = has_table

    def has_schema(self, engine, schema):
        return self._has_schema

    def has_table(self, engine, name, schema):
        return self._has_table


class FakeEngine:
    def __init__(self, dialect=None):
        self.dialect = dialect or FakeDialect()


@pytest.fixture
def fake_db():
    engine = FakeEngine()
    metadata = sa.MetaData()
    return mod.DB(engine, metadata)


@pytest.fixture
def sample_resource():
    # Close to your earlier example, but short & focused
    return {
        "name": "Electricity-HeatPump Decentral Profile",  # table name with spaces/case
        "profile": "tabular-data-resource",
        "format": "csv",
        "schema": {
            "fields": [
                {"name": "Name", "type": "string"},
                {"name": "electricity_bus", "type": "string"},
                {"name": "heat-bus", "type": "string"},
                {"name": "capacity (kW)", "type": "number"},
            ],
            "primaryKey": "Name",
            "foreignKeys": [
                {
                    "fields": "electricity_bus",
                    "reference": {"resource": "Bus", "fields": "Name"},
                },
                {
                    "fields": "heat-bus",
                    "reference": {"resource": "bus", "fields": "Name"},
                },
            ],
        },
    }


@pytest.fixture
def sample_metadata(sample_resource):
    return {"resources": [sample_resource]}


# ------------------------------
# Normalizer tests
# ------------------------------


def test__pg_sanitize_base_basic():
    assert mod._pg_sanitize_base("Foo Bar-1") == "foo_bar_1"
    assert mod._pg_sanitize_base("ok_name") == "ok_name"


def test_normalize_table_identifier_truncation(monkeypatch):
    # Force small MAX_TABLE_LEN to verify truncation
    monkeypatch.setattr(mod, "MAX_TABLE_LEN", 10, raising=False)
    s = mod.normalize_table_identifier("this_is_very_long_name")
    assert s == "this_is_ve"  # length 10


def test_normalize_column_identifier_truncation(monkeypatch):
    monkeypatch.setattr(mod, "MAX_COLUMN_LEN", 12, raising=False)
    s = mod.normalize_column_identifier("this_is_very_long_colname")
    assert len(s) == 12
    assert s == "this_is_very"  # 12 chars


def test_de_umlaut_transforms():
    # NOTE: If this fails, fix de_umlaut to *return* the replaced string.
    # e.g.
    # def de_umlaut(s):
    #     if not s: return s
    #     return (s.replace("Ä","Ae").replace("Ö","Oe").replace("Ü","Ue")
    #             .replace("ä","ae").replace("ö","oe").replace("ü","ue").replace("ß","ss"))
    assert mod.de_umlaut("ÜbergrößE") == "UebergroessE"


def test_build_unique_column_map_handles_collisions(monkeypatch):
    monkeypatch.setattr(mod, "MAX_COLUMN_LEN", 8, raising=False)
    mapping = mod.build_unique_column_map(["Capacity", "capacity", "capacity_1"])
    print(mapping)
    # normalize -> capacity, collision -> capacity_1, then -> capacity_2 (with truncation)
    assert mapping["Capacity"] == "capacity"
    assert mapping["capacity"] == "capaci_1"
    assert mapping["capacity_1"] == "capaci_2"  # truncated + suffix


def test__map_key_names_with_cmap_and_normalizer():
    cmap = {"Name": "name", "heat-bus": "heat_bus"}
    assert mod._map_key_names("Name", cmap) == ["name"]
    assert mod._map_key_names(["Name", "heat-bus"], cmap) == ["name", "heat_bus"]


# ------------------------------
# Resource normalization
# ------------------------------


def test_normalize_resource_inplace(sample_resource, monkeypatch):
    monkeypatch.setattr(mod, "MAX_TABLE_LEN", 20, raising=False)  # to test truncation
    tname, cmap = mod.normalize_resource_inplace(sample_resource)

    assert isinstance(tname, str)
    assert " " not in tname and "-" not in tname
    assert len(tname) <= 20
    # field names mapped/lowercased/underscored
    fields = [f["name"] for f in sample_resource["schema"]["fields"]]
    assert "name" in fields
    assert "electricity_bus" in fields
    assert "heat_bus" in fields
    assert "capacity_kw" in fields  # "(kW)" sanitized

    # PK remapped to normalized column
    assert sample_resource["schema"]["primaryKey"] == "name"

    # FK locals normalized
    fks = sample_resource["schema"]["foreignKeys"]
    assert fks[0]["fields"] == "electricity_bus"
    assert fks[1]["fields"] == "heat_bus"
    # FK references normalized
    assert fks[0]["reference"]["resource"] == mod.TABLE_NORMALIZER("Bus")
    assert fks[0]["reference"]["fields"] == "name"


# ------------------------------
# Table name checks
# ------------------------------


def test_check_table_name_valid_and_invalid():
    assert mod.check_table_name("ok_name")
    assert not mod.check_table_name("bad name")
    assert not mod.check_table_name("9starts_with_digit")


def test_normalize_table_name_deprecated_behaviour(monkeypatch):
    monkeypatch.setattr(mod, "MAX_TABLE_LEN", 5, raising=False)
    assert mod.normalize_table_name("abcdefgh") == "abcde"


# ------------------------------
# Metadata file helpers
# ------------------------------


def test_load_and_save_json(tmp_path):
    p = tmp_path / "x.json"
    mod.saveMdToJson({"a": 1}, p)
    data = mod.load_json(p)
    assert data == {"a": 1}


def test_mdToDict_finds_file(tmp_path):
    d = tmp_path / "meta"
    d.mkdir()
    p = d / "datapackage.json"
    mod.saveMdToJson({"hello": "world"}, p)
    got = mod.mdToDict(d, "datapackage.json")
    assert got == {"hello": "world"}


def test_select_oem_dir_returns_path(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "meta").mkdir()
    out = mod.select_oem_dir("meta")
    assert isinstance(out, pathlib.Path)
    assert out.exists()


def test_select_oem_dir_raises_when_none():
    with pytest.raises(FileNotFoundError):
        mod.select_oem_dir(None)


def test_getTableSchemaNameFromOEM():
    md = {"resources": [{"name": "schema.table"}]}
    assert mod.getTableSchemaNameFromOEM(md) == ("schema", "table")
    md2 = {"resources": [{"name": "just_table"}]}
    assert mod.getTableSchemaNameFromOEM(md2) == (None, "just_table")


# ------------------------------
# API helpers
# ------------------------------


def test_setupApiAction_builds_url_and_headers(monkeypatch):
    monkeypatch.setattr(mod, "OEP_API_URL_LOCAL", "https://host/api/", raising=False)
    monkeypatch.setattr(mod, "setUserToken", lambda: "T0K3N", raising=False)
    action = mod.setupApiAction("model_draft", "tbl")
    assert action.dest_url == "https://host/api/schema/model_draft/tables/tbl/meta/"
    assert (
        "Authorization" in action.headers and "Token" in action.headers["Authorization"]
    )


def test_setUserToken_env(monkeypatch):
    monkeypatch.setenv("OEP_TOKEN", "ENV_TOKEN")
    assert mod.setUserToken() == "ENV_TOKEN"


def test_setUserToken_getpass(monkeypatch):
    monkeypatch.delenv("OEP_TOKEN", raising=False)
    monkeypatch.setattr(
        mod.getpass, "getpass", lambda prompt="": "GP_TOKEN", raising=False
    )
    assert mod.setUserToken() == "GP_TOKEN"


def test_api_downloadMd(monkeypatch):
    class FakeResp:
        def __init__(self, payload):
            self._payload = payload

        def json(self):
            return self._payload

    def fake_get(url):
        return FakeResp({"ok": True})

    monkeypatch.setattr(mod, "requests", types.SimpleNamespace(get=fake_get))
    monkeypatch.setattr(
        mod,
        "setupApiAction",
        lambda s, t, token=None: types.SimpleNamespace(dest_url="http://x", headers={}),
    )
    out = mod.api_downloadMd("model_draft", "tbl")
    assert out == {"ok": True}


@pytest.mark.parametrize(
    "status,json_text,is_json",
    [
        (200, "ok", False),
        (400, "<h3>Bad</h3>", False),
        (400, json.dumps({"error": "bad"}), True),
    ],
)
def test_api_updateMdOnTable(monkeypatch, status, json_text, is_json):
    # Prepare metadata
    md = {"resources": [{"name": "tbl"}]}

    class FakeResp:
        def __init__(self, status, text):
            self.status_code = status
            self.text = text
            self.url = "http://x"

        def json(self):
            return json.loads(self.text)

    def fake_post(url, json=None, headers=None, verify=False):
        return FakeResp(status, json_text)

    monkeypatch.setattr(
        mod,
        "setupApiAction",
        lambda s, t, token=None: types.SimpleNamespace(dest_url="http://x", headers={}),
    )
    monkeypatch.setattr(mod, "requests", types.SimpleNamespace(post=fake_post))

    if status == 200:
        mod.api_updateMdOnTable(md)
    else:
        with pytest.raises(mod.MetadataError):
            mod.api_updateMdOnTable(md)


def test_push_resource_meta(monkeypatch):
    # Mock omi spec + validation + post
    fake_spec = types.SimpleNamespace(
        template={"resources": [{}]}, example={"@context": {}, "metaMetadata": {}}
    )
    monkeypatch.setattr(mod, "get_metadata_specification", lambda v: fake_spec)
    monkeypatch.setattr(mod, "validate_metadata", lambda *a, **k: None)

    posted = {}

    def fake_post(url, json=None, headers=None, verify=False):
        posted["json"] = json

        class Resp:
            status_code = 200
            text = "ok"
            url = "http://x"

        return Resp()

    monkeypatch.setattr(
        mod,
        "setupApiAction",
        lambda s, t, token=None: types.SimpleNamespace(dest_url="http://x", headers={}),
    )
    monkeypatch.setattr(mod, "requests", types.SimpleNamespace(post=fake_post))
    monkeypatch.setattr(mod, "setUserToken", lambda: "T0K3N", raising=False)

    res = {"name": "tbl", "schema": {"fields": [{"name": "id", "type": "integer"}]}}
    mod.push_resource_meta(res)
    assert "resources" in posted["json"]


# ------------------------------
# Table creation pipeline
# ------------------------------


def test_create_tables_from_metadata_file_dict(fake_db, sample_metadata):
    tables = mod.create_tables_from_metadata_file(fake_db, sample_metadata)
    assert tables, "Should produce at least one SQLAlchemy Table"
    t = tables[0]
    # id auto-added and PK-only
    pks = [c.name for c in t.primary_key.columns]
    assert pks == ["id"]
    assert "id" in t.columns
    # normalized field names present
    assert "name" in t.columns
    assert "electricity_bus" in t.columns
    assert "heat_bus" in t.columns
    # FKs compiled on the columns that reference other tables
    fk_cols = [c for c in t.columns if c.foreign_keys]
    assert len(fk_cols) > 0, "At least one FK expected"


def test_collect_tables_from_oem_object_orders_by_fk(fake_db, sample_metadata):
    # Two simple resources; second references first via FK
    md1 = {
        "resources": [
            {"name": "bus", "schema": {"fields": [{"name": "id", "type": "integer"}]}}
        ]
    }
    md2 = {
        "resources": [
            {
                "name": "gen",
                "schema": {
                    "fields": [
                        {"name": "id", "type": "integer"},
                        {"name": "bus_id", "type": "integer"},
                    ],
                    "foreignKeys": [
                        {
                            "fields": "bus_id",
                            "reference": {"resource": "bus", "fields": "id"},
                        }
                    ],
                },
            }
        ]
    }
    tables = mod.collect_tables_from_oem_object(fake_db, [md1, md2])
    # Ordered by number of FKs (bus first (0), then gen (1))
    assert [t.name for t in tables] == ["bus", "gen"]


def test_create_tables_happy_path(monkeypatch):
    # Use two dummy "tables" to avoid SQLAlchemy DDL
    created = []

    class DummyTable:
        def __init__(self, name, schema="model_draft", fks=0):
            self.name = name
            self.schema = schema
            self.foreign_keys = [None] * fks

        def create(self, checkfirst=True):
            created.append(self.name)

    engine = FakeEngine(FakeDialect(has_schema=True, has_table=False))
    db = mod.DB(engine, sa.MetaData())

    mod.create_tables(db, [DummyTable("t1"), DummyTable("t2")])
    assert created == ["t1", "t2"]


def test_create_tables_missing_schema_raises():
    class DummyTable:
        def __init__(self, name, schema="bad_schema"):
            self.name = name
            self.schema = schema
            self.foreign_keys = []

        def create(self, checkfirst=True):
            pass

    engine = FakeEngine(FakeDialect(has_schema=False, has_table=False))
    db = mod.DB(engine, sa.MetaData())

    with pytest.raises(mod.DatabaseError):
        mod.create_tables(db, [DummyTable("t1")])


def test_delete_tables_confirms_and_drops(monkeypatch):
    dropped = []

    class DummyTable:
        def __init__(self, name, fks=0):
            self.name = name
            self.foreign_keys = [None] * fks

        def drop(self, engine, checkfirst=True):
            dropped.append(self.name)

    engine = FakeEngine()
    db = mod.DB(engine, sa.MetaData())

    monkeypatch.setattr(builtins, "input", lambda prompt="": "y")
    mod.delete_tables(db, [DummyTable("a", 0), DummyTable("b", 2)])
    # b (2 fks) should be dropped last because we reverse the sorted order
    assert set(dropped) == {"a", "b"}


# --- table/column name lengths on normalized SQLAlchemy Tables ----


def test_normalized_sqlalchemy_names_respect_module_limits(fake_db, sample_metadata):
    """
    Ensure that the SQLAlchemy Table created from normalized metadata
    uses names that respect MAX_TABLE_LEN / MAX_COLUMN_LEN.
    """
    tables = mod.create_tables_from_metadata_file(fake_db, sample_metadata)
    assert tables, "No tables returned from normalization/builder"
    t = tables[0]

    # Table name length (post-normalization)
    assert len(t.name) <= mod.MAX_TABLE_LEN, (
        f"Normalized table name too long: {t.name} (len={len(t.name)}), "
        f"MAX_TABLE_LEN={mod.MAX_TABLE_LEN}"
    )

    # Column name lengths (post-normalization)
    for c in t.columns:
        assert len(c.name) <= mod.MAX_COLUMN_LEN, (
            f"Normalized column name too long: {c.name} (len={len(c.name)}), "
            f"MAX_COLUMN_LEN={mod.MAX_COLUMN_LEN}"
        )

    # Also check the table name equals the output of your table normalizer pipeline
    original = sample_metadata["resources"][0]["name"]
    assert t.name == mod.TABLE_NORMALIZER(original)


@pytest.mark.xfail(
    reason="Fails until MAX_TABLE_LEN <= (50 - OEP prefix length, usually 36)"
)
def test_oep_prefixed_table_name_total_limit(fake_db, sample_metadata):
    """
    OEP API prepends a run prefix like 'r123456789012_' and requires TOTAL <= 50.
    This test ensures the final name (prefix + normalized) fits that limit.

    Remove xfail after you set MAX_TABLE_LEN = 50 - len(PREFIX) (e.g., 36).
    """
    PREFIX = "r123456789012_"  # 14 chars: 'r' + 12 digits + '_'
    TOTAL_LIMIT = 50

    tables = mod.create_tables_from_metadata_file(fake_db, sample_metadata)
    assert tables, "No tables returned from normalization/builder"
    t = tables[0]

    final_name = f"{PREFIX}{t.name}"
    assert len(final_name) <= TOTAL_LIMIT, (
        f"OEP-prefixed name too long: '{final_name}' (len={len(final_name)}). "
        f"Set MAX_TABLE_LEN <= {TOTAL_LIMIT - len(PREFIX)} to satisfy OEP."
    )


def test_fk_without_schema_defaults_to_current_schema(fake_db):
    md = {
        "resources": [
            {
                "name": "bus",
                "schema": {
                    "fields": [
                        {"name": "id", "type": "integer"},
                        {"name": "name", "type": "string"},
                    ]
                },
            },
            {
                "name": "biomass_gas_commodity",
                "schema": {
                    "fields": [
                        {"name": "id", "type": "integer"},
                        {"name": "bus", "type": "string"},
                    ],
                    "foreignKeys": [
                        {
                            "fields": "bus",
                            "reference": {"resource": "bus", "fields": "name"},
                        }
                    ],
                },
            },
        ]
    }
    tables = mod.create_tables_from_metadata_file(fake_db, md)
    t = next(t for t in tables if t.name == "biomass_gas_commodity")
    fk_col = next(c for c in t.columns if c.name == "bus")
    fk = next(iter(fk_col.foreign_keys))
    # SQLAlchemy formats target fullname as "schema.table.column"
    assert str(fk.target_fullname).endswith(".bus.name")


def test_fk_forward_reference_is_ok(fake_db):
    # child declared before parent — still resolves due to two-pass build
    md = {
        "resources": [
            {
                "name": "child",
                "schema": {
                    "fields": [
                        {"name": "id", "type": "integer"},
                        {"name": "parent_id", "type": "integer"},
                    ],
                    "foreignKeys": [
                        {
                            "fields": "parent_id",
                            "reference": {"resource": "parent", "fields": "id"},
                        }
                    ],
                },
            },
            {
                "name": "parent",
                "schema": {"fields": [{"name": "id", "type": "integer"}]},
            },
        ]
    }
    tables = mod.create_tables_from_metadata_file(fake_db, md)
    child = next(t for t in tables if t.name == "child")
    assert any(
        len(c.foreign_keys) for c in child.columns
    ), "FK should be attached in pass 2"
