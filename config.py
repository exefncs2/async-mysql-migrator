"""Configuration and SQL normalization helpers for Async MySQL Migrator."""

from __future__ import annotations

import os
import re
from dataclasses import dataclass


@dataclass(frozen=True)
class DBConfig:
    """Connection parameters for a MySQL database."""

    host: str
    port: int
    user: str
    password: str
    database: str

    @classmethod
    def from_env(cls, prefix: str) -> "DBConfig":
        """Load database credentials from environment variables with `prefix`."""
        missing = [
            key
            for key in (f"{prefix}_HOST", f"{prefix}_USER", f"{prefix}_PASSWORD", f"{prefix}_NAME")
            if not os.getenv(key)
        ]
        if missing:
            raise ValueError(f"Missing required environment variables: {', '.join(missing)}")

        return cls(
            host=os.environ[f"{prefix}_HOST"],
            port=int(os.getenv(f"{prefix}_PORT", "3306")),
            user=os.environ[f"{prefix}_USER"],
            password=os.environ[f"{prefix}_PASSWORD"],
            database=os.environ[f"{prefix}_NAME"],
        )


def rewrite_create_table_sql(
    create_sql: str,
    source_db: str,
    charset: str = "utf8mb4",
    collation: str = "utf8mb4_general_ci",
) -> str:
    """Normalize a SHOW CREATE TABLE statement for target execution."""
    sql = create_sql.replace(f"`{source_db}`.", "")

    if re.search(r"(?i)DEFAULT\s+CHARSET\s*=", sql):
        sql = re.sub(r"(?i)DEFAULT\s+CHARSET\s*=\s*\w+", f"DEFAULT CHARSET={charset}", sql)
        if re.search(r"(?i)COLLATE\s*=\s*\w+", sql):
            sql = re.sub(r"(?i)COLLATE\s*=\s*\w+", f"COLLATE={collation}", sql)
        else:
            sql = sql.rstrip(";") + f" COLLATE={collation};"
    else:
        sql = sql.rstrip(";") + f" DEFAULT CHARSET={charset} COLLATE={collation};"

    return sql
