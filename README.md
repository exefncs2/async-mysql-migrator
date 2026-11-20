# Async MySQL Migrator

基於 Python `asyncio` 與 `aiomysql` 實作的非同步 MySQL 資料庫遷移工具，可自動複製資料表結構、分批搬移大量資料，並將字元集統一轉換為 `utf8mb4` / `utf8mb4_general_ci`。

## 核心功能

- **表結構自動複製與字元集轉換**
  - 透過 `SHOW CREATE TABLE` 取得來源表定義，於目標資料庫重建表結構。
  - 使用正規表達式自動將支援的字元集與排序規則統一轉換為 `utf8mb4` / `utf8mb4_general_ci`。
- **分批資料搬移**
  - 預設以 `BATCH_SIZE = 10000` 分批讀取與寫入，避免大表遷移造成記憶體溢位，並即時輸出進度。
- **全流程非同步處理**
  - 使用 `asyncio` + `aiomysql` 連線池提升跨庫遷移吞吐量。

## 快速開始

### 1. 安裝相依套件

```bash
pip install -r requirements.txt
```

### 2. 設定環境變數

複製範例檔並填入來源與目標資料庫連線資訊（對應 `main.py` 中的 `load_dotenv(".env_A")`）：

```bash
cp .env.example .env_A
```

```env
SOURCE_DB_HOST=your_source_host
SOURCE_DB_USER=your_source_user
SOURCE_DB_PASSWORD=your_source_password
SOURCE_DB_NAME=your_source_db

TARGET_DB_HOST=your_target_host
TARGET_DB_USER=your_target_user
TARGET_DB_PASSWORD=your_target_password
TARGET_DB_NAME=your_target_db
```

### 3. 執行遷移

```bash
python main.py
```

## 自訂調整說明

- **切換設定檔**：修改 `main.py` 頂部的 `load_dotenv(".env_A")` 即可切換不同遷移方向或環境。
- **指定特定資料表**：調整 `tables` 清單以限制遷移範圍。
- **僅同步表結構**：註解 `await insert_data(...)` 即可只建立 Schema 不搬移資料。
- **自訂編碼**：可依需求調整 `CONVERT TO CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci`。
