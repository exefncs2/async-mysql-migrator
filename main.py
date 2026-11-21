"""Asynchronous MySQL schema & data migration utility.

Streams rows in fixed-size batches from a source MySQL database to a target
MySQL database using asyncio + aiomysql, automatically normalizing table and
column character sets to utf8mb4.
"""

from __future__ import annotations

import argparse
import asyncio
import logging
from typing import Iterable, Sequence

import aiomysql
from dotenv import load_dotenv

from config import DBConfig, rewrite_create_table_sql

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("async_mysql_migrator")


async def create_pool(cfg: DBConfig, maxsize: int = 5) -> aiomysql.Pool:
    """Create an async MySQL connection pool."""
    return await aiomysql.create_pool(
        host=cfg.host,
        port=cfg.port,
        user=cfg.user,
        password=cfg.password,
        db=cfg.database,
        charset="utf8mb4",
        autocommit=False,
        maxsize=maxsize,
    )


async def list_tables(source_pool: aiomysql.Pool) -> list[str]:
    """Fetch all table names from the source database."""
    async with source_pool.acquire() as conn:
        async with conn.cursor() as cursor:
            await cursor.execute("SHOW TABLES;")
            rows = await cursor.fetchall()
            return [row[0] for row in rows]


async def replicate_table_schema(
    source_pool: aiomysql.Pool,
    target_pool: aiomysql.Pool,
    source_db: str,
    target_db: str,
    table_name: str,
    charset: str = "utf8mb4",
    collation: str = "utf8mb4_general_ci",
) -> None:
    """Replicate a single table schema onto the target DB with normalized charset."""
    async with source_pool.acquire() as source_conn:
        async with source_conn.cursor() as source_cursor:
            await source_cursor.execute(f"SHOW CREATE TABLE `{table_name}`;")
            result = await source_cursor.fetchone()
            if not result:
                raise RuntimeError(f"Unable to read schema for table `{table_name}`")
            create_sql = rewrite_create_table_sql(
                result[1], source_db=source_db, charset=charset, collation=collation
            )

    async with target_pool.acquire() as target_conn:
        async with target_conn.cursor() as target_cursor:
            await target_cursor.execute(f"USE `{target_db}`;")
            await target_cursor.execute(f"DROP TABLE IF EXISTS `{target_db}`.`{table_name}`;")
            await target_cursor.execute(create_sql)
            await target_cursor.execute(
                f"ALTER TABLE `{target_db}`.`{table_name}` "
                f"CONVERT TO CHARACTER SET {charset} COLLATE {collation};"
            )
            await target_conn.commit()

    logger.info("Schema replicated & converted to %s: `%s`", charset, table_name)


async def stream_table_data(
    source_pool: aiomysql.Pool,
    target_pool: aiomysql.Pool,
    table_name: str,
    batch_size: int = 10_000,
) -> int:
    """Stream rows batch-by-batch from source to target with constant memory usage."""
    async with source_pool.acquire() as src_conn:
        async with src_conn.cursor() as count_cur:
            await count_cur.execute(f"SELECT COUNT(1) FROM `{table_name}`;")
            total_rows = (await count_cur.fetchone())[0]

    if total_rows == 0:
        logger.info("`%s`: 0 rows (skipped data transfer)", table_name)
        return 0

    logger.info("`%s`: migrating %d rows (batch_size=%d)...", table_name, total_rows, batch_size)
    migrated = 0

    async with source_pool.acquire() as src_conn, target_pool.acquire() as dst_conn:
        async with src_conn.cursor(aiomysql.DictCursor) as src_cur, dst_conn.cursor() as dst_cur:
            for offset in range(0, total_rows, batch_size):
                await src_cur.execute(
                    f"SELECT * FROM `{table_name}` LIMIT %s OFFSET %s;",
                    (batch_size, offset),
                )
                batch = await src_cur.fetchall()
                if not batch:
                    break

                columns = list(batch[0].keys())
                col_sql = ", ".join(f"`{col}`" for col in columns)
                placeholders = ", ".join(["%s"] * len(columns))
                insert_sql = f"INSERT INTO `{table_name}` ({col_sql}) VALUES ({placeholders});"
                values = [tuple(row[col] for col in columns) for row in batch]

                await dst_cur.executemany(insert_sql, values)
                await dst_conn.commit()

                migrated += len(batch)
                pct = migrated / total_rows * 100
                logger.info("`%s`: %d / %d rows (%.1f%%)", table_name, migrated, total_rows, pct)

    return migrated


async def migrate_database(
    source_cfg: DBConfig,
    target_cfg: DBConfig,
    tables: Sequence[str] | None = None,
    batch_size: int = 10_000,
    schema_only: bool = False,
    charset: str = "utf8mb4",
    collation: str = "utf8mb4_general_ci",
) -> None:
    """Run full database migration for all or selected tables."""
    source_pool = await create_pool(source_cfg)
    target_pool = await create_pool(target_cfg)

    try:
        target_tables: Iterable[str] = tables if tables else await list_tables(source_pool)
        target_tables = list(target_tables)
        logger.info("Target tables (%d): %s", len(target_tables), ", ".join(target_tables))

        for table in target_tables:
            await replicate_table_schema(
                source_pool=source_pool,
                target_pool=target_pool,
                source_db=source_cfg.database,
                target_db=target_cfg.database,
                table_name=table,
                charset=charset,
                collation=collation,
            )
            if not schema_only:
                await stream_table_data(
                    source_pool=source_pool,
                    target_pool=target_pool,
                    table_name=table,
                    batch_size=batch_size,
                )
        logger.info("Migration completed successfully.")
    finally:
        source_pool.close()
        await source_pool.wait_closed()
        target_pool.close()
        await target_pool.wait_closed()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Async MySQL schema & batch data migrator")
    parser.add_argument("--env", default=".env", help="Path to .env file (default: .env)")
    parser.add_argument("--tables", nargs="*", default=None, help="Specific tables to migrate (default: all)")
    parser.add_argument("--batch-size", type=int, default=10_000, help="Rows per batch (default: 10000)")
    parser.add_argument("--schema-only", action="store_true", help="Migrate table schemas only, skip rows")
    parser.add_argument("--charset", default="utf8mb4", help="Target MySQL charset (default: utf8mb4)")
    parser.add_argument("--collation", default="utf8mb4_general_ci", help="Target collation")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    load_dotenv(args.env)
    source_cfg = DBConfig.from_env("SOURCE_DB")
    target_cfg = DBConfig.from_env("TARGET_DB")

    asyncio.run(
        migrate_database(
            source_cfg=source_cfg,
            target_cfg=target_cfg,
            tables=args.tables,
            batch_size=args.batch_size,
            schema_only=args.schema_only,
            charset=args.charset,
            collation=args.collation,
        )
    )


if __name__ == "__main__":
    main()
