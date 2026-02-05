import unittest
from unittest.mock import patch, MagicMock
import sqlalchemy as sa

from oem2orm.oep_oedialect_oem2orm import (
    setup_db_connection,
    create_tables_from_metadata_file,
    check_oep_api_schema_whitelist,
    MetadataError,
)


class TestDatabaseModule(unittest.TestCase):
    @patch("oem2orm.oep_oedialect_oem2orm.sa.create_engine")
    @patch("oem2orm.oep_oedialect_oem2orm.get_oep_token", return_value="API_TOKEN")
    def test_setup_db_connection_prod(self, _get_token, mock_create_engine):
        mock_engine = MagicMock(spec=sa.engine.Engine)
        mock_create_engine.return_value = mock_engine

        with patch.dict(
            "os.environ",
            {
                "OEP_PROFILE": "prod",
                "OEP_USER": "test",
                "OEP_URL": "openenergyplatform.org",
            },
            clear=False,
        ):
            db = setup_db_connection()
            mock_create_engine.assert_called_once_with(
                "postgresql+oedialect://test:API_TOKEN@openenergyplatform.org"
            )
            self.assertIs(db.engine, mock_engine)

    @patch("oem2orm.oep_oedialect_oem2orm.sa.create_engine")
    @patch("oem2orm.oep_oedialect_oem2orm.get_oep_token", return_value="LOCAL_TOKEN")
    def test_setup_db_connection_local(self, _get_token, mock_create_engine):
        mock_engine = MagicMock(spec=sa.engine.Engine)
        mock_create_engine.return_value = mock_engine

        with patch.dict(
            "os.environ",
            {
                "OEP_PROFILE": "local",
                "OEP_USER": "localuser",
                "OEP_URL_LOCAL": "localhost:8000",
            },
            clear=False,
        ):
            db = setup_db_connection()
            mock_create_engine.assert_called_once_with(
                "postgresql+oedialect://localuser:LOCAL_TOKEN@localhost:8000"
            )
            self.assertIs(db.engine, mock_engine)

    def test_check_oep_api_schema_whitelist_allowed(self):
        self.assertTrue(check_oep_api_schema_whitelist("model_draft"))

    def test_check_oep_api_schema_whitelist_disallowed(self):
        self.assertFalse(check_oep_api_schema_whitelist("production_schema"))

    def test_create_tables_from_metadata_file_valid(self):
        metadata = {
            "resources": [
                {
                    "name": "test_table",
                    "schema": {
                        "primaryKey": ["id"],
                        "fields": [
                            {
                                "name": "id",
                                "type": "integer",
                                "description": "Primary key",
                            },
                            {
                                "name": "value",
                                "type": "string",
                                "description": "A value",
                            },
                        ],
                        "foreignKeys": [],
                    },
                }
            ]
        }
        db_mock = MagicMock()
        db_mock.metadata = sa.MetaData()

        tables = create_tables_from_metadata_file(db_mock, metadata)
        self.assertEqual(len(tables), 1)
        self.assertEqual(tables[0].name, "test_table")
        self.assertEqual(len(tables[0].columns), 2)

    def test_create_tables_from_metadata_file_invalid_type(self):
        metadata = {
            "resources": [
                {
                    "name": "invalid_table",
                    "schema": {
                        "primaryKey": ["id"],
                        "fields": [
                            {
                                "name": "id",
                                "type": "nonexistent_type",
                                "description": "Primary key",
                            }
                        ],
                        "foreignKeys": [],
                    },
                }
            ]
        }
        db_mock = MagicMock()
        db_mock.metadata = sa.MetaData()

        with self.assertRaises(MetadataError):
            create_tables_from_metadata_file(db_mock, metadata)


if __name__ == "__main__":
    unittest.main()
