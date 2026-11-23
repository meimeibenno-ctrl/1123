# 苗栗縣天氣小站

使用 Python 3.12、Flask 與中央氣象署（CWA）開放資料 API 查詢苗栗縣 18 個鄉鎮市的最新時段預報及未來 5 日預報。API 使用 HTTPS。中央氣象署 API 需要會員授權碼，程式從 `CWA_API_KEY` 環境變數讀取，請勿將授權碼寫入程式碼或提交至 Git。

## 功能

- 支援苗栗市、頭份市、竹南鎮、後龍鎮、通霄鎮、苑裡鎮、卓蘭鎮、造橋鄉、西湖鄉、頭屋鄉、公館鄉、銅鑼鄉、三義鄉、大湖鄉、獅潭鄉、三灣鄉、南庄鄉、泰安鄉。
- 首頁預設苗栗市；可用下拉選單或網址參數切換，例如 `/?town=sanyi`。不支援的代碼會回到苗栗市。
- 顯示預報溫度、體感、相對濕度、風速、天氣現象及五日最高/最低溫與降雨機率。中央氣象署的風速單位為公尺/秒；降雨機率只在資料有提供的日期顯示數值。
- 每個鄉鎮市的成功回應會在記憶體快取 10 分鐘；快取可能因 Vercel 無伺服器執行個體重啟或擴增而重置。
- 使用苗栗縣未來一週鄉鎮預報資料集 `F-D0047-015`。該資料為預報時段資料，頁面標示「最新時段預報」，不代表即時觀測值。

## 申請中央氣象署 API 授權碼

到[中央氣象署資料開放平台](https://opendata.cwa.gov.tw/)註冊/登入並取得會員授權碼。此應用使用[苗栗縣未來一週鄉鎮預報資料集](https://opendata.cwa.gov.tw/dataset/forecast/F-D0047-015)。

## 本機啟動（Python 3.12）

在專案根目錄執行：

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
$env:CWA_API_KEY = "貼上你的中央氣象署授權碼"
python app.py
```

若 PowerShell 不允許啟用虛擬環境，也可直接執行：

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
$env:CWA_API_KEY = "貼上你的中央氣象署授權碼"
.\.venv\Scripts\python.exe app.py
```

開啟終端機顯示的本機網址（預設 `http://127.0.0.1:5000`）。環境變數只對目前 PowerShell 工作階段生效；請勿把授權碼貼入 `app.py`、README 或 Git 提交。

## 推送至 GitHub

若尚未初始化 Git，先在 GitHub 建立一個空白儲存庫（不要先加入 README、授權或 `.gitignore`），再於專案根目錄執行以下命令，並將網址換成你自己的儲存庫網址：

```powershell
git init
git add .
git commit -m "建立苗栗縣天氣查詢網站"
git branch -M main
git remote add origin https://github.com/你的帳號/你的儲存庫.git
git push -u origin main
```

`.gitignore` 會排除虛擬環境、Python 快取、`.env` 及 Vercel 本機設定目錄。推送前可用 `git status` 確認沒有授權碼或本機設定檔被加入提交。

## 部署至 Vercel

1. 將程式碼推送至 GitHub。
2. 登入 [Vercel](https://vercel.com/)，選擇 **Add New → Project**，匯入 GitHub 儲存庫。
3. Framework Preset 選 **Other**；根目錄維持預設，不需設定 Build Command。Vercel 依 `vercel.json` 執行 `app.py`，並安裝 `requirements.txt` 中的依賴。
4. 在 Vercel 專案 **Settings → Environment Variables** 新增 `CWA_API_KEY`，值填入你的中央氣象署授權碼，選擇要套用的部署環境後儲存。
5. 按 **Deploy**。若已先部署，新增環境變數後需重新部署，讓函式讀取新設定。

### 部署後檢查

- 首頁 `/` 顯示苗栗市；`/?town=sanyi` 顯示三義鄉；`/?town=invalid` 安全退回苗栗市。
- 若尚未設定 `CWA_API_KEY`，網站會提示設定授權碼；若授權碼無效、API 逾時（8 秒）、連線失敗或回應格式異常，頁面會顯示友善訊息。可查看 Vercel 部署的 **Functions / Logs**。
- 確認 Vercel 專案以 Python runtime 部署，`requirements.txt` 可被讀取，且 `templates/`、`static/` 隨函式打包。若修改專案根目錄，需同步更新 `vercel.json`。
- Vercel 無伺服器記憶體快取是盡力而為，不保證跨執行個體共享或永久保存。此程式每次只查詢所選鄉鎮的 CWA 預報，請留意 API 授權使用規範及 Vercel 函式執行限制。

## 資料來源

資料由[中央氣象署開放資料平台「苗栗縣鄉鎮未來一週天氣預報」](https://opendata.cwa.gov.tw/dataset/forecast/F-D0047-015)提供，預報以鄉鎮市區公所為代表點；內容僅供參考。
