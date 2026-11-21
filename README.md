# Async MySQL Migrator

使用 Python `asyncio` + `aiomysql` 撰寫的 MySQL 跨庫資料表結構與資料搬移工具。

## 1. 緣起與解決的問題

實務上把舊環境的 MySQL 資料庫搬到新環境時，常遇到三個麻煩：
1. **編碼混雜導致亂碼**：舊表常殘留 `latin1` 或不一致的排序規則，搬過去中文就出問題。
2. **舊資料含無效零日期**：舊版 MySQL 允許存 `0000-00-00`，但在新版嚴格模式下寫入會直接中斷報錯。
3. **大表一次讀爆記憶體**：如果先 `fetchall()` 把整張表載進記憶體再逐筆寫入，遇到幾十萬筆以上的表很容易 OOM 且耗時很久。

這支工具就是針對這幾個實務痛點整理出來的搬移腳本。

---

## 2. 設計思路與關鍵取捨

### (1) 為什麼先重寫建表 SQL，還要再補一次 `ALTER TABLE ... CONVERT TO`？
- 從來源庫拿到的 `SHOW CREATE TABLE` 語法，除了可能夾帶來源庫前綴（`` `source_db`. ``）外，就算改了表尾的 `DEFAULT CHARSET=utf8mb4`，原本單獨標記在個別欄位上的 `CHARACTER SET latin1` 還是不會跟著改。
- 因此流程採兩階段：先清掉來源庫前綴並統一表層級編碼，建表後再對目標表執行 `ALTER TABLE ... CONVERT TO CHARACTER SET utf8mb4`，確保所有文字欄位都徹底轉碼。
- 另外在 `DROP TABLE` 前會明確加上目標庫名稱（`` `target_db`.`table_name` ``），避免連線誤切時砍錯來源庫。

### (2) 為什麼改為「串流分批讀寫」與 `executemany`？
- 初版原本是先把整張表讀完存成 list 再逐筆 `execute`，後來重構成在同一個迴圈裡逐批 `LIMIT / OFFSET` 讀取、立刻清洗零日期、立刻用 `executemany` 整批寫入並 `commit`。
- **好處**：記憶體占用固定在單批（預設 10,000 筆）以內，寫入速度也比逐筆送 SQL 快很多。

### (3) 為什麼保留零日期清洗（`sanitize_row_values`）？
- 寫入前會檢查每個欄位，把 `"0000-00-00"` 與 `"0000-00-00 00:00:00"` 轉成 `None`（對應 SQL `NULL`），避免新資料庫開啟 `NO_ZERO_DATE` 嚴格模式時整批失敗。

### (4) 為什麼拆成三檔（`config.py` / `migrator.py` / `main.py`）？
- 把環境變數檢查（`DatabaseConfig.from_env`）、純邏輯（SQL 字元集改寫、零日期清洗、串流搬移）與 CLI 參數解析分開，這樣不用真的架兩台 MySQL，也能先透過 `unittest` 驗證設定驗證與資料轉換邏輯沒寫壞。

---

## 3. 目前已知限制

- **超大表分頁效能**：目前採 `LIMIT / OFFSET` 分批，幾十萬筆以內很順，但若是千萬筆以上超大表，後段 `OFFSET` 掃描成本會拉高；這類情境建議改用主鍵游標分頁（Keyset Pagination）。
- **全量覆蓋模式**：目標表會先 `DROP TABLE IF EXISTS` 再重建，適合初始化或離線整庫搬遷，不適合線上雙寫增量同步。

---

## 4. 專案結構

```text
async-mysql-migrator/
├── config.py        # 常數、不可變連線設定與 Fail Fast 環境變數檢查
├── migrator.py      # 建表 SQL 改寫、零日期清洗與分批串流讀寫邏輯
├── main.py          # CLI 參數解析與執行進入點
├── tests/           # 單元測試（設定檢查、SQL 轉換、零日期清洗）
└── .env.example     # 來源與目標資料庫連線範本
```

## 5. 執行方式

```bash
pip install -r requirements.txt
cp .env.example .env

# 搬移全部資料表
python main.py

# 只搬指定資料表並自訂批次大小
python main.py --env .env.prod --tables users orders --batch-size 5000

# 只重建目標庫表結構，不搬資料
python main.py --schema-only

# 執行單元測試
python -m unittest discover -s tests -v
```
