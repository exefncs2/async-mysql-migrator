# Async MySQL Migrator

![Python](https://img.shields.io/badge/Python-3.10%2B-3776AB?logo=python&logoColor=white)
![MySQL](https://img.shields.io/badge/MySQL-utf8mb4-4479A1?logo=mysql&logoColor=white)
![Asyncio](https://img.shields.io/badge/Async-asyncio%20%2B%20aiomysql-009688)

基於 Python `asyncio` 與 `aiomysql` 的非同步 MySQL 跨庫遷移工具：採用**三檔分離架構**（參數設定 / 核心邏輯 / CLI 進入點），支援定額記憶體串流分批搬移與自動轉換 `utf8mb4`。

## 專案架構（三檔分離）

```text
async-mysql-migrator/
├── config.py        # 參數設定檔：常數、不可變 DatabaseConfig / MigrationOptions 與環境變數驗證
├── migrator.py      # 核心邏輯檔：表結構正規化、字元集轉換與串流分批讀寫
├── main.py          # 呼叫進入點：CLI 參數解析與啟動流程
├── tests/           # 單元測試
└── .env.example     # 環境變數範本
```

## 快速開始

```bash
pip install -r requirements.txt
cp .env.example .env

# 遷移全部資料表
python main.py

# 指定資料表與每批筆數
python main.py --env .env.prod --tables users orders --batch-size 5000

# 僅複製表結構
python main.py --schema-only
```

## 執行單元測試

```bash
python -m unittest discover -s tests -v
```
