"""核心遷移邏輯模組：負責表結構正規化與定額記憶體串流分批搬移。"""

from __future__ import annotations

import logging
import re
from typing import Any, Mapping, Sequence

import aiomysql

from config import (
    DEFAULT_CHARSET,
    DEFAULT_COLLATION,
    DEFAULT_POOL_MAX_SIZE,
    DatabaseConfig,
    MigrationOptions,
)

logger = logging.getLogger(__name__)

# 舊版 MySQL 常見無效零日期字串，於嚴格模式寫入目標庫前須轉為 NULL
INVALID_ZERO_DATES = frozenset({"0000-00-00", "0000-00-00 00:00:00"})


def sanitize_row_values(row: Mapping[str, Any], columns: Sequence[str]) -> tuple[Any, ...]:
    """清洗單筆資料列，將舊 MySQL 零日期字串轉為 None 避免目標庫嚴格模式報錯。"""
    return tuple(
        None if isinstance(row[col], str) and row[col] in INVALID_ZERO_DATES else row[col]
        for col in columns
    )


def rewrite_create_table_sql(
    create_sql: str,
    source_db: str,
    charset: str = DEFAULT_CHARSET,
    collation: str = DEFAULT_COLLATION,
) -> str:
    """移除來源庫前綴並將建表語法之字元集與排序規則統一為目標設定。"""
    normalized_sql = create_sql.replace(f"`{source_db}`.", "")

    if not re.search(r"(?i)DEFAULT\s+CHARSET\s*=", normalized_sql):
        return f"{normalized_sql.rstrip(';')} DEFAULT CHARSET={charset} COLLATE={collation};"

    normalized_sql = re.sub(
        r"(?i)DEFAULT\s+CHARSET\s*=\s*\w+",
        f"DEFAULT CHARSET={charset}",
        normalized_sql,
    )
    if re.search(r"(?i)COLLATE\s*=\s*\w+", normalized_sql):
        return re.sub(r"(?i)COLLATE\s*=\s*\w+", f"COLLATE={collation}", normalized_sql)

    return f"{normalized_sql.rstrip(';')} COLLATE={collation};"


async def create_pool(
    config: DatabaseConfig,
    max_size: int = DEFAULT_POOL_MAX_SIZE,
) -> aiomysql.Pool:
    """建立非同步 MySQL 連線池。"""
    return await aiomysql.create_pool(
        host=config.host,
        port=config.port,
        user=config.user,
        password=config.password,
        db=config.database,
        charset=DEFAULT_CHARSET,
        autocommit=False,
        maxsize=max_size,
    )


async def fetch_table_names(source_pool: aiomysql.Pool) -> list[str]:
    """取得來源資料庫中的所有資料表名稱。"""
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
    charset: str = DEFAULT_CHARSET,
    collation: str = DEFAULT_COLLATION,
) -> None:
    """於目標庫重建單一資料表結構並強制轉換文字欄位編碼。"""
    async with source_pool.acquire() as source_conn:
        async with source_conn.cursor() as source_cursor:
            await source_cursor.execute(f"SHOW CREATE TABLE `{table_name}`;")
            result = await source_cursor.fetchone()
            if not result:
                raise RuntimeError(f"無法讀取來源資料表結構：`{table_name}`")
            create_sql = rewrite_create_table_sql(
                result[1],
                source_db=source_db,
                charset=charset,
                collation=collation,
            )

    # 明確鎖定目標庫名稱，避免任何誤刪來源庫資料表的風險
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

    logger.info("資料表結構重建並轉換為 %s 完成：`%s`", charset, table_name)


async def stream_table_data(
    source_pool: aiomysql.Pool,
    target_pool: aiomysql.Pool,
    target_db: str,
    table_name: str,
    batch_size: int,
) -> int:
    """以串流方式逐批讀寫資料表，自動清洗零日期並避免大表一次載入造成記憶體溢位。"""
    async with source_pool.acquire() as count_conn:
        async with count_conn.cursor() as count_cursor:
            await count_cursor.execute(f"SELECT COUNT(1) FROM `{table_name}`;")
            total_rows = (await count_cursor.fetchone())[0]

    if total_rows == 0:
        logger.info("`%s` 無資料列，略過資料搬移", table_name)
        return 0

    logger.info("開始遷移 `%s`，總計 %d 筆（每批 %d 筆）", table_name, total_rows, batch_size)
    migrated_rows = 0

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
                insert_sql = f"INSERT INTO `{target_db}`.`{table_name}` ({col_sql}) VALUES ({placeholders});"
                values = [sanitize_row_values(row, columns) for row in batch]

                await dst_cur.executemany(insert_sql, values)
                await dst_conn.commit()

                migrated_rows += len(batch)
                progress_pct = migrated_rows / total_rows * 100
                logger.info("`%s` 進度：%d / %d (%.1f%%)", table_name, migrated_rows, total_rows, progress_pct)

    return migrated_rows


async def migrate_database(
    source_config: DatabaseConfig,
    target_config: DatabaseConfig,
    options: MigrationOptions,
) -> None:
    """依注入的來源／目標設定與遷移選項執行完整遷移流程。"""
    source_pool = await create_pool(source_config)
    target_pool = await create_pool(target_config)

    try:
        target_tables: Sequence[str] = (
            options.tables if options.tables else await fetch_table_names(source_pool)
        )
        logger.info("待遷移資料表共 %d 張：%s", len(target_tables), ", ".join(target_tables))

        for table_name in target_tables:
            await replicate_table_schema(
                source_pool=source_pool,
                target_pool=target_pool,
                source_db=source_config.database,
                target_db=target_config.database,
                table_name=table_name,
                charset=options.charset,
                collation=options.collation,
            )
            if options.is_schema_only:
                continue

            await stream_table_data(
                source_pool=source_pool,
                target_pool=target_pool,
                target_db=target_config.database,
                table_name=table_name,
                batch_size=options.batch_size,
            )

        logger.info("全部資料表遷移作業完成")
    finally:
        source_pool.close()
        await source_pool.wait_closed()
        target_pool.close()
        await target_pool.wait_closed()
