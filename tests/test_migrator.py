import os
import unittest
from unittest.mock import patch

from config import DBConfig, rewrite_create_table_sql


class TestMigratorHelpers(unittest.TestCase):
    def test_rewrite_replaces_existing_charset_and_collation(self):
        raw = "CREATE TABLE `src_db`.`users` (`id` INT) ENGINE=InnoDB DEFAULT CHARSET=latin1 COLLATE=latin1_swedish_ci;"
        out = rewrite_create_table_sql(raw, source_db="src_db")
        self.assertNotIn("`src_db`.", out)
        self.assertIn("DEFAULT CHARSET=utf8mb4", out)
        self.assertIn("COLLATE=utf8mb4_general_ci", out)

    def test_rewrite_appends_charset_when_missing(self):
        raw = "CREATE TABLE `logs` (`id` INT);"
        out = rewrite_create_table_sql(raw, source_db="src_db")
        self.assertTrue(out.endswith("DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;"))

    def test_db_config_missing_env_raises(self):
        with patch.dict(os.environ, {}, clear=True):
            with self.assertRaises(ValueError):
                DBConfig.from_env("SOURCE_DB")

    def test_db_config_from_env_success(self):
        env = {
            "SOURCE_DB_HOST": "127.0.0.1",
            "SOURCE_DB_PORT": "3307",
            "SOURCE_DB_USER": "admin",
            "SOURCE_DB_PASSWORD": "secret",
            "SOURCE_DB_NAME": "app",
        }
        with patch.dict(os.environ, env, clear=True):
            cfg = DBConfig.from_env("SOURCE_DB")
            self.assertEqual(cfg.port, 3307)
            self.assertEqual(cfg.database, "app")


if __name__ == "__main__":
    unittest.main()
