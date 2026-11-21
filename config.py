"""參數與設定模組：集中管理常數與 MySQL 連線設定（Fail Fast 驗證）。"""

from __future__ import annotations

import os
from dataclasses import dataclass

DEFAULT_PORT = 3306
DEFAULT_BATCH_SIZE = 10_000
DEFAULT_POOL_MAX_SIZE = 5
DEFAULT_CHARSET = "utf8mb4"
DEFAULT_COLLATION = "utf8mb4_general_ci"


@dataclass(frozen=True)
class DatabaseConfig:
    """不可變 MySQL 資料庫連線設定。"""

    host: str
    port: int
    user: str
    password: str
    database: str

    @classmethod
    def from_env(cls, prefix: str) -> "DatabaseConfig":
        """由環境變數讀取設定，缺少必要欄位時立即拋出例外（Fail Fast）。"""
        required_keys = (
            f"{prefix}_HOST",
            f"{prefix}_USER",
            f"{prefix}_PASSWORD",
            f"{prefix}_NAME",
        )
        missing_keys = [key for key in required_keys if not os.getenv(key)]
        if missing_keys:
            raise ValueError(f"缺少必要環境變數：{', '.join(missing_keys)}")

        return cls(
            host=os.environ[f"{prefix}_HOST"],
            port=int(os.getenv(f"{prefix}_PORT", str(DEFAULT_PORT))),
            user=os.environ[f"{prefix}_USER"],
            password=os.environ[f"{prefix}_PASSWORD"],
            database=os.environ[f"{prefix}_NAME"],
        )


@dataclass(frozen=True)
class MigrationOptions:
    """單次遷移任務之不可變執行參數。"""

    batch_size: int = DEFAULT_BATCH_SIZE
    is_schema_only: bool = False
    charset: str = DEFAULT_CHARSET
    collation: str = DEFAULT_COLLATION
    tables: tuple[str, ...] | None = None
