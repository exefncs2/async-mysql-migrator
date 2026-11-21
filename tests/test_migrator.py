"""設定載入、建表 SQL 正規化與零日期清洗單元測試。"""

import os
import sys
import unittest
from unittest.mock import MagicMock, patch

from config import DatabaseConfig

if "aiomysql" not in sys.modules:
    sys.modules["aiomysql"] = MagicMock()

from migrator import rewrite_create_table_sql, sanitize_row_values  # noqa: E402


class TestMigratorConfigAndSql(unittest.TestCase):
    """驗證 Fail Fast 設定載入、字元集轉換與零日期清洗規則。"""

    def test_missing_env_raises_value_error(self) -> None:
        with patch.dict(os.environ, {}, clear=True):
            with self.assertRaises(ValueError):
                DatabaseConfig.from_env("SOURCE_DB")

    def test_load_database_config_from_env(self) -> None:
        env = {
            "SOURCE_DB_HOST": "127.0.0.1",
            "SOURCE_DB_PORT": "3307",
            "SOURCE_DB_USER": "admin",
            "SOURCE_DB_PASSWORD": "secret",
            "SOURCE_DB_NAME": "app",
        }
        with patch.dict(os.environ, env, clear=True):
            cfg = DatabaseConfig.from_env("SOURCE_DB")
            self.assertEqual(cfg.port, 3307)
            self.assertEqual(cfg.database, "app")

    def test_rewrite_replaces_existing_charset(self) -> None:
        raw = "CREATE TABLE `src_db`.`users` (`id` INT) DEFAULT CHARSET=latin1 COLLATE=latin1_swedish_ci;"
        out = rewrite_create_table_sql(raw, source_db="src_db")
        self.assertNotIn("`src_db`.", out)
        self.assertIn("DEFAULT CHARSET=utf8mb4", out)
        self.assertIn("COLLATE=utf8mb4_general_ci", out)

    def test_rewrite_appends_charset_when_absent(self) -> None:
        raw = "CREATE TABLE `logs` (`id` INT);"
        out = rewrite_create_table_sql(raw, source_db="src_db")
        self.assertTrue(out.endswith("DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;"))

    def test_sanitize_row_converts_zero_dates_to_none(self) -> None:
        row = {"id": 1, "birth": "0000-00-00", "updated_at": "0000-00-00 00:00:00", "name": "Felix"}
        cleaned = sanitize_row_values(row, ["id", "birth", "updated_at", "name"])
        self.assertEqual(cleaned, (1, None, None, "Felix"))


if __name__ == "__main__":
    unittest.main()
