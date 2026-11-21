# Async MySQL Migrator

![Python](https://img.shields.io/badge/Python-3.10%2B-3776AB?logo=python&logoColor=white)
![MySQL](https://img.shields.io/badge/MySQL-utf8mb4-4479A1?logo=mysql&logoColor=white)
![Asyncio](https://img.shields.io/badge/Async-asyncio%20%2B%20aiomysql-009688)

基於 Python `asyncio` 與 `aiomysql` 的非同步 MySQL 跨庫遷移工具：支援自動複製表結構、統一轉換字元集為 `utf8mb4`、以及**定額記憶體串流分批搬移**。

## 核心特色

- **真正的串流分批遷移（Constant Memory）**：每讀取一個批次（預設 `10,000` 筆）即刻寫入目標庫並提交，避免大表遷移造成記憶體爆量。
- **表結構自動重建與字元集轉換**：透過 `SHOW CREATE TABLE` 與 `ALTER TABLE ... CONVERT TO` 自動將舊字元集正規化為 `utf8mb4` / `utf8mb4_general_ci`。
- **彈性 CLI 參數**：支援自訂 `.env` 檔、指定遷移資料表、僅遷移結構（`--schema-only`）與自訂批次大小。
- **設定驗證與結構化日誌**：啟動時自動檢核必要環境變數並透過 `logging` 回報即時進度。

## 快速開始

### 1. 安裝相依套件

```bash
pip install -r requirements.txt
```

### 2. 建立環境設定檔

```bash
cp .env.example .env
# 編輯 .env 填入來源與目標資料庫連線資訊
```

### 3. 執行遷移

```bash
# 遷移全部資料表（預設讀取 .env、批次 10,000 筆）
python main.py

# 指定特定環境檔與資料表
python main.py --env .env.prod --tables users orders --batch-size 5000

# 僅複製表結構，不搬移資料
python main.py --schema-only
```

## 執行單元測試

```bash
python -m unittest discover -s tests -v
```
