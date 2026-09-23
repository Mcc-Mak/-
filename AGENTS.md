# AGENTS.md

本檔定義自動化代理在此 repo 的運作規則，源於 `Prompt.md`。**所有輸出（提交訊息、Markdown 內容、資料夾／檔案名稱、錯誤報告）一律使用繁體中文書面語**；程式碼、JSON 鍵值與 Git 分支名稱可保留英文。

## 專案目的

從差估署 XML 資料源逐一提取建築物名稱，交由 CrewAI 編排器 MCP 依 `Standard.md` **撰寫每棟建築物的傳記式歷史**（以敘事為主軸，非純編年列表）。每完成一棟即 Git 提交並推送至 `dev-001`。

## 必備文件（開始前檢查，缺失即停止）

- `Standard.md`：建築物歷史撰寫規範（含章節結構與驗收門檻）。**缺失 → 立即停止並回報（Prompt.md §6、§7）。**
- `README.md`、`AGENTS.md`：隨專案維護。
- `BUILDING_MATRIX.md`：建築物清單及狀態（`待處理`／`已完成`／`失敗`），含備註欄記錄 XML 解析錯誤。

## 資料來源

- 市區：`https://res.data.gov.hk/api/get-download-file?name=https%3A%2F%2Fwww.rvd.gov.hk%2Fdatagovhk%2Fbnb-u.xml`
- 新界：`https://res.data.gov.hk/api/get-download-file?name=https%3A%2F%2Fwww.rvd.gov.hk%2Fdatagovhk%2Fbnb-nt.xml`

提取規則：遍歷建築物節點，同時保留英文與中文名稱。XML 解析失敗時，將錯誤寫入 `BUILDING_MATRIX.md` 備註欄並繼續處理另一來源；不要中止整個流程。

## CrewAI 編排器 MCP

- 路徑：`C:\Users\ccmak.AD\Desktop\Workplace\crew-ai-orchestrator-mcp`
- 傳輸：STDIO（本地進程）。該目錄**沒有** `mcp.json`／HTTP／SSE 端點，勿嘗試 HTTP 傳輸。
- 啟動命令（注意：本機未發布至 PyPI，**不能用 `uvx`**，須用本地 venv 直跑）：
  `& "C:\Users\ccmak.AD\Desktop\Workplace\crew-ai-orchestrator-mcp\.venv\Scripts\mcp-crew-ai.exe" --agents agents.yml --tasks tasks.yml`
  - 已註冊為 repo 級 MCP（`opencode.json` 的 `crew-ai-orchestrator`，含 `cwd` 指向 MCP 目錄）。
  - ⚠️ `Prompt.md` 範例的 `python -m crew_ai_orchestrator_mcp` 是錯的——實際模組名為 `mcp_crew_ai`，console script 為 `mcp-crew-ai`。
  - LLM 憑證：有 `OPENAI_API_KEY` 用 OpenAI；否則 fallback 至 OpenCode Zen（`~/.local/share/opencode/auth.json` 的 `opencode.key`，模型 `big-pickle`）。兩者皆無時 `run_workflow` 仍回傳 `job_id`，但背景 job 會被標記為 `failed`。
- 可用工具（已於 `server.py` 驗證）：
  - `run_workflow(topic, process="sequential")` → **立即回傳 job_id（非同步）**，須用 `get_status` 輪詢至完成。`process` 只能是 `sequential` 或 `hierarchical`，且 `topic` 不可為空。
  - `get_status(job_id)` → 狀態：`pending` / `running` / `completed` / `failed`。
  - `list_crews()`、`list_agents(crew_name)`、`list_tasks(crew_name)`。

## 執行流程

1. HTTP 取得兩個 XML → 解析出建築物名稱 → 填寫 `BUILDING_MATRIX.md`（序號、中英名、來源檔案、狀態「待處理」）。
2. 逐棟呼叫 `run_workflow`（並把 `Standard.md` 及可信度規範傳給 MCP），輪詢至 `completed` 後取回結果。
3. 驗收輸出（依 `Standard.md` 第四章）：缺引用編號、參考文獻未按第一級→第五級排序、**只有年表而無敘事正文** → **拒絕輸出**，要求重新生成。
4. 存檔為 `歷史/#{AUTO_INCREMENT:5位前導零}-{{building-slug}}-歷史.md`，例如 `歷史/00001-central-plaza-歷史.md`。slug = 英文名 kebab-case。**「歷史」＝建築物傳記式歷史，勿改叫時間線。**
5. 編號管理：AUTO_INCREMENT 由 `.prior` 文件驅動，其序號在所有場合具最高優先權（見下「.prior 自動遞增」）。更新 `BUILDING_MATRIX.md` 為「已完成」並以 `[歷史檔案路徑](路徑)` 記錄檔案路徑。
6. 每棟完成即執行 Git 提交＋推送（見下）。

以上步驟已由 `pipeline.py` 自動化：

- `python pipeline.py --check-mcp`：只驗證 MCP 連線並列出工具。
- `python pipeline.py --dry-run [--limit N]`：純預演（解析矩陣、演算 `.prior` 編號、slug、驗收邏輯），**不呼叫 MCP、不改任何檔案**。
- `python pipeline.py [--limit N]`：正式執行（MCP 呼叫 → 輪詢 → 驗收 → 存檔 → 更新矩陣／`.prior` → 逐棟 Git 提交＋推送至 `dev-001`）。每棟重試最多三次；失敗標「失敗」並跳過 Git 提交。

## .prior 自動遞增

- 檔名前置的 5 位自動遞增編號（00001 起）存放於 `.prior`。
- `.prior` 是純文字檔，每行一個已使用的遞增編號（預設為**空檔**＝從 00001 開始）。
- **優先權**：決定下一個編號時，一律以 `.prior` 內容為準（最高優先），不得自行推算或覆寫；若 `.prior` 為空則取 00001。
- 每次存檔成功後，把該編號附加入 `.prior` 並一併提交。

## Git 控制（強制，每棟一提交）

- 分支一律 `dev-001`；不存在則 `git checkout -b dev-001`。
- 提交內容（原子性）：新增的 `歷史/*.md` + 更新後的 `BUILDING_MATRIX.md` + 更新的 `.prior`。
- 提交訊息（約定式）：`feat(歷史): 新增 {{建築物名稱}} 歷史`
- 每次提交後 `git push origin dev-001`。推送失敗：`git pull --rebase origin dev-001` 後重試；衝突無法自動解決則停止並回報。
- MCP 呼叫失敗：重試**最多三次**；仍失敗 → 標記「失敗」、記錄錯誤、**跳過該棟的 Git 提交**，繼續下一棟。

## 打包時注意

- 分支已建立：`dev-001`（首次提交 `9b24b18 docs(專案): 建立專案文件與建築物矩陣`，命名機制由 `edd4177 docs(歷史): 檔案命名改為 AUTO_INCREMENT 前綴並引入 .prior` 確立；後續以 `pipeline.py` 逐棟自動提交）。
- 所有歷史完成後：確認 `BUILDING_MATRIX.md` 全為「已完成」、全部已推送，可建標籤 `v0.1.0-dev001`。