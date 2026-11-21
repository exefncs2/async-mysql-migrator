# Async MySQL Migrator（MySQL 非同步跨庫搬移工具紀錄）

> 以 Python `asyncio` + `aiomysql` 撰寫的跨庫搬移腳本，紀錄自己在處理 MySQL 舊表轉碼與資料搬移時的實作方式與整理過程。

## 1. 這支腳本實際解決的問題與做法

這支工具針對實務搬移舊 MySQL 時實際遇到的三個狀況來寫：

1. **重建表結構並統一轉成 `utf8mb4`**（`migrator.py: replicate_table_schema`）
   - 先對來源庫執行 `SHOW CREATE TABLE`，用正規表達式拿掉來源庫前綴（`` `source_db`. ``），並將建表語法的字元集與排序規則改寫為目標設定（預設 `utf8mb4` / `utf8mb4_general_ci`）。
   - 在目標庫明確指定目標資料庫名稱執行 `DROP TABLE IF EXISTS` 與 `CREATE TABLE`，再補一道 `ALTER TABLE ... CONVERT TO CHARACTER SET`，把表內文字欄位一併轉碼。
2. **分批讀取與寫入**（`migrator.py: stream_table_data`）
   - 原本初版是把整張表讀完塞進一個大 list 再逐筆寫入；重構後改在同一個迴圈裡逐批用 `LIMIT / OFFSET`（預設每批 10,000 筆）讀取，再用 `executemany` 整批寫入並 `commit`，同時印出進度百分比。
3. **清洗 `"0000-00-00"` 零日期**（`migrator.py: sanitize_row_values`）
   - 寫入目標庫前會檢查每個欄位值，若為 `"0000-00-00"` 或 `"0000-00-00 00:00:00"` 字串就轉成 `None`（SQL `NULL`），避免目標庫嚴格模式報錯。
4. **從手改程式改成三檔＋CLI 參數**
   - 把設定（`config.py`）、搬移邏輯（`migrator.py`）、命令列進入點（`main.py`）分開，並把原本需要改原始碼的項目（`.env` 路徑、指定資料表、只搬結構、字元集）改成 CLI 參數，同時補了 5 個不需連 MySQL 就能跑的單元測試。

---

## 2. 目前限制

- 分批讀取採 `LIMIT / OFFSET`，超大表（例如千萬筆以上）在後段頁次會變慢。
- 目標表會先 `DROP TABLE IF EXISTS` 再重建，只適合初始化或整庫覆蓋搬移，不適合線上增量同步。

---

## 3. 正式使用方式

### 步驟 1：安裝依賴並設定 `.env`
```bash
pip install -r requirements.txt
cp .env.example .env
```

編輯 `.env` 填入來源與目標 MySQL 連線資訊（`SOURCE_DB_*` 與 `TARGET_DB_*`）。

### 步驟 2：執行搬移與單元測試
```bash
# 搬移全部資料表（預設讀取 .env、每批 10,000 筆）
python main.py

# 指定 env 檔、指定資料表與批次筆數
python main.py --env .env_A --tables users orders --batch-size 5000

# 只重建目標表結構，不搬資料
python main.py --schema-only

# 自訂字元集與排序規則
python main.py --charset utf8mb4 --collation utf8mb4_unicode_ci

# 執行單元測試
python -m unittest discover -s tests -v
```
