# 苗栗縣天氣小站

使用 Python 3.12、Flask 與 Open-Meteo 公開 API 查詢苗栗縣 18 個鄉鎮市的即時天氣及未來 5 日預報。API 使用 HTTPS，不需 API 金鑰；頁面為繁體中文，包含手機版排版及友善的資料讀取錯誤提示。

## 功能

- 支援苗栗市、頭份市、竹南鎮、後龍鎮、通霄鎮、苑裡鎮、卓蘭鎮、造橋鄉、西湖鄉、頭屋鄉、公館鄉、銅鑼鄉、三義鄉、大湖鄉、獅潭鄉、三灣鄉、南庄鄉、泰安鄉。
- 首頁預設苗栗市；可用下拉選單或網址參數切換，例如 `/?town=sanyi`。不支援的代碼會回到苗栗市。
- 顯示溫度、體感、相對濕度、風速、天氣描述及五日最高/最低溫與降雨機率。
- 每個鄉鎮市的成功回應會在記憶體快取 10 分鐘；快取可能因 Vercel 無伺服器執行個體重啟或擴增而重置。

## 本機啟動（Python 3.12）

在專案根目錄執行：

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
python app.py
```

若 PowerShell 不允許啟用虛擬環境，也可直接執行：

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe app.py
```

開啟終端機顯示的本機網址（預設 `http://127.0.0.1:5000`）。測試其他地區可開啟 `http://127.0.0.1:5000/?town=sanyi`。此應用不需要 `.env` 或 API 金鑰。

## 推送至 GitHub

先在 GitHub 建立一個空白儲存庫（不要先加入 README、授權或 `.gitignore`），再於專案根目錄執行以下命令，並將網址換成你自己的儲存庫網址：

```powershell
git init
git add .
git commit -m "建立苗栗縣天氣查詢網站"
git branch -M main
git remote add origin https://github.com/你的帳號/你的儲存庫.git
git push -u origin main
```

`.gitignore` 會排除虛擬環境、Python 快取、`.env` 及 Vercel 本機設定目錄。推送前可用 `git status` 確認沒有本機設定檔或其他不應提交的資料。

## 部署至 Vercel

1. 將程式碼推送至 GitHub。
2. 登入 [Vercel](https://vercel.com/)，選擇 **Add New → Project**，匯入剛才的 GitHub 儲存庫。
3. Framework Preset 選 **Other**（或讓 Vercel 使用 `vercel.json` 偵測設定）。根目錄維持預設值；不需設定環境變數或 Build Command。Vercel 會依 `vercel.json` 以 `@vercel/python` 執行 `app.py`，並安裝 `requirements.txt` 中的依賴。
4. 按 **Deploy**，完成後以 Vercel 提供的網址開啟網站。後續推送到連結的分支會觸發新的部署。

### 部署後檢查

- 首頁 `/` 顯示苗栗市；`/?town=sanyi` 顯示三義鄉；`/?town=invalid` 安全退回苗栗市。
- 若看到友善的資料載入提示，代表外部 API 請求逾時（8 秒）、網路失敗或回應格式異常；可查看 Vercel 部署的 **Functions / Logs**，並稍後重試。網站不會因 API 暫時不可用而直接拋出錯誤頁。
- 確認 Vercel 專案以 Python runtime 部署，`requirements.txt` 可被讀取，且 `templates/`、`static/` 隨函式打包。若修改專案根目錄，需同步更新 `vercel.json`。
- 無伺服器平台有執行時間與記憶體限制；本程式的單次 Open-Meteo 呼叫逾時設為 8 秒，10 分鐘記憶體快取是盡力而為，不保證跨執行個體共享或永久保存。大量流量時應留意 Vercel 函式執行時間與 Open-Meteo 可用性。

## 資料來源

天氣資料由 [Open-Meteo Forecast API](https://open-meteo.com/en/docs) 提供，採 `Asia/Taipei` 時區。各行政區以代表性座標查詢；資料僅供參考。
