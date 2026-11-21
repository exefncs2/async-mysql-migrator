# Async MySQL Migrator（MySQL 非同步跨庫遷移實作筆記）

> 一個以 Python `asyncio` + `aiomysql` 實作的 MySQL 跨庫搬移工具紀錄，重點整理實務遷移時常碰到的編碼亂碼、無效零日期與大表記憶體問題。

## 1. 學習背景與實務痛點

在把舊系統 MySQL 資料表搬移到新環境時，實作過程中陸續碰到三個坑：
1. **文字欄位編碼殘留**：從來源庫拉出來的 `SHOW CREATE TABLE` 語法常帶著來源庫前綴（`` `source_db`. ``）與舊編碼（如 `latin1`）；就算只改了建表語法結尾的 `DEFAULT CHARSET=utf8mb4`，原本個別欄位上的字元集設定仍可能沒跟著轉，搬完還是亂碼。
2. **舊資料含有 `"0000-00-00"` 零日期**：舊版 MySQL 允許寫入零日期字串，但新版資料庫預設開啟嚴格模式，直接寫入會中斷失敗。
3. **一次載入整張表容易爆記憶體**：初版先將整張表分批讀完收集成一整包 list 後再逐筆 `INSERT`，表一大起來既吃記憶體又慢。

---

## 2. 設計思路與重構演進

### (1) 表結構重建與強制轉碼兩段式處理
- 先用 `SHOW CREATE TABLE` 取得原表結構，透過正規表達式移除來源庫名稱並統一字元集為 `utf8mb4`／`utf8mb4_general_ci`。
- 在目標庫明確指定資料庫名稱（`` `target_db`.`table_name` ``）執行 `DROP TABLE IF EXISTS` → `CREATE TABLE`，避免任何誤砍來源庫的風險。
- 建表後再補執行 `ALTER TABLE ... CONVERT TO CHARACTER SET utf8mb4`，確保表內所有文字欄位都徹底轉碼。

### (2) 從「整表暫存」改為「定額記憶體串流分批」
- 後來重構成在單一分批迴圈內「讀一批（`LIMIT / OFFSET`）→ 清洗零日期（`"0000-00-00"` 轉 `None`）→ `executemany` 整批寫入並 `commit`」，記憶體用量固定控制在單批大小內（預設 10,000 筆），同時即時輸出進度百分比。

### (3) 從「手動改程式碼」改為「三檔分離＋CLI 參數」
- 初版若要切換 `.env` 檔、指定單一資料表或只複製結構，都必須直接改 `main.py` 原始碼。
- 重構後拆成三個檔案，並把原本常修改的四個項目全部改成命令列參數，也順便補上不需連真實 MySQL 就能驗證邏輯的單元測試：
  - `config.py`：常數、不可變 `DatabaseConfig` / `MigrationOptions` 與環境變數 Fail Fast 檢查。
  - `migrator.py`：SQL 改寫、零日期清洗、表結構重建與串流分批核心邏輯。
  - `main.py`：CLI 參數解析與啟動進入點。

### (4) 目前已知限制
- 分批讀取使用 `LIMIT / OFFSET`，在幾十萬筆以內表現穩定；若面對千萬筆以上超大表，後段頁次會變慢，較適合改用主鍵游標分頁。
- 目標表採 `DROP + CREATE` 全量重建，僅適用於初始化或離線全量遷移，不適用於線上即時增量同步。

---

## 3. 正式使用方式

### 步驟 1：安裝依賴與建立環境設定檔
```bash
pip install -r requirements.txt
cp .env.example .env
```

編輯 `.env` 填入來源與目標資料庫連線資訊：
```ini
SOURCE_DB_HOST=your_source_host
SOURCE_DB_PORT=3306
SOURCE_DB_USER=your_source_user
SOURCE_DB_PASSWORD=your_source_password
SOURCE_DB_NAME=your_source_db

TARGET_DB_HOST=your_target_host
TARGET_DB_PORT=3306
TARGET_DB_USER=your_target_user
TARGET_DB_PASSWORD=your_target_password
TARGET_DB_NAME=your_target_db
```

### 步驟 2：執行遷移指令
```bash
# 搬移全部資料表（預設讀取 .env、每批 10,000 筆）
python main.py

# 對應舊版「指定 env 檔」與「指定資料表」
python main.py --env .env_A --tables users orders --batch-size 5000

# 對應舊版「只拉表結構不拉資料」
python main.py --schema-only

# 對應舊版「自訂字元集與排序規則」
python main.py --charset utf8mb4 --collation utf8mb4_unicode_ci
```

### 步驟 3：執行單元測試
```bash
python -m unittest discover -s tests -v
```
