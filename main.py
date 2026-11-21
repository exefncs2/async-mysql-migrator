"""CLI 呼叫進入點：負責解析參數、載入設定並呼叫核心遷移流程。"""

from __future__ import annotations

import argparse
import asyncio
import logging
from pathlib import Path

from dotenv import load_dotenv

from config import (
    DEFAULT_BATCH_SIZE,
    DEFAULT_CHARSET,
    DEFAULT_COLLATION,
    DatabaseConfig,
    MigrationOptions,
)
from migrator import migrate_database

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)


def parse_args() -> argparse.Namespace:
    """解析命令列參數。"""
    parser = argparse.ArgumentParser(description="非同步 MySQL 結構與分批資料遷移工具")
    parser.add_argument("--env", type=Path, default=Path(".env"), help="環境變數檔路徑（預設 .env）")
    parser.add_argument("--tables", nargs="*", default=None, help="指定要遷移的資料表清單（未指定則遷移全部）")
    parser.add_argument("--batch-size", type=int, default=DEFAULT_BATCH_SIZE, help="每批搬移筆數（預設 10000）")
    parser.add_argument("--schema-only", action="store_true", help="僅重建資料表結構，不搬移資料列")
    parser.add_argument("--charset", default=DEFAULT_CHARSET, help="目標字元集（預設 utf8mb4）")
    parser.add_argument("--collation", default=DEFAULT_COLLATION, help="目標排序規則")
    return parser.parse_args()


def main() -> None:
    """讀取設定並啟動非同步遷移作業。"""
    args = parse_args()
    if args.batch_size <= 0:
        raise ValueError("批次大小（--batch-size）必須大於 0")

    load_dotenv(args.env)
    source_config = DatabaseConfig.from_env("SOURCE_DB")
    target_config = DatabaseConfig.from_env("TARGET_DB")
    options = MigrationOptions(
        batch_size=args.batch_size,
        is_schema_only=args.schema_only,
        charset=args.charset,
        collation=args.collation,
        tables=tuple(args.tables) if args.tables else None,
    )
    asyncio.run(migrate_database(source_config, target_config, options))


if __name__ == "__main__":
    main()
