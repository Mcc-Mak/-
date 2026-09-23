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
- 啟動命令（在 MCP 目錄下執行；`agents.yml`／`tasks.yml` 有預設值）：
  `uvx mcp-crew-ai --agents agents.yml --tasks tasks.yml`
  - ⚠️ `Prompt.md` 範例的 `python -m crew_ai_orchestrator_mcp` 是錯的——實際模組名為 `mcp_crew_ai`，console script 為 `mcp-crew-ai`。
  - 執行真實工作流程需要 `OPENAI_API_KEY`。缺 key 時 `run_workflow` 仍會回傳 `job_id`，但背景 job 會被標記為 `failed`。
- 可用工具（已於 `server.py` 驗證）：
  - `run_workflow(topic, process="sequential")` → **立即回傳 job_id（非同步）**，須用 `get_status` 輪詢至完成。`process` 只能是 `sequential` 或 `hierarchical`，且 `topic` 不可為空。
  - `get_status(job_id)` → 狀態：`pending` / `running` / `completed` / `failed`。
  - `list_crews()`、`list_agents(crew_name)`、`list_tasks(crew_name)`。

## 執行流程

1. HTTP 取得兩個 XML → 解析出建築物名稱 → 填寫 `BUILDING_MATRIX.md`（序號、中英名、來源檔案、狀態「待處理」）。
2. 逐棟呼叫 `run_workflow`（並把 `Standard.md` 及可信度規範傳給 MCP），輪詢至 `completed` 後取回結果。
3. 驗收輸出（依 `Standard.md` 第四章）：缺引用編號、參考文獻未按第一級→第五級排序、**只有年表而無敘事正文** → **拒絕輸出**，要求重新生成。
4. 存檔為 `歷史/{{building-slug}}-歷史.md`（slug = 英文名 kebab-case，如 `central-plaza-歷史.md`），更新 `BUILDING_MATRIX.md` 為「已完成」並記錄檔案路徑。**「歷史」＝建築物傳記式歷史，勿改叫時間線。**
5. 每棟完成即執行 Git 提交＋推送（見下）。

## Git 控制（強制，每棟一提交）

- 分支一律 `dev-001`；不存在則 `git checkout -b dev-001`。
- 提交內容（原子性）：新增的 `歷史/*.md` + 更新後的 `BUILDING_MATRIX.md`。
- 提交訊息（約定式）：`feat(歷史): 新增 {{建築物名稱}} 歷史`
- 每次提交後 `git push origin dev-001`。推送失敗：`git pull --rebase origin dev-001` 後重試；衝突無法自動解決則停止並回報。
- MCP 呼叫失敗：重試**最多三次**；仍失敗 → 標記「失敗」、記錄錯誤、**跳過該棟的 Git 提交**，繼續下一棟。

## 打包時注意

- 目前 repo 只有 `Prompt.md`，git 尚未產生任何 commit（分支 `master`）；首次需建 `dev-001`。
- 所有歷史完成後：確認 `BUILDING_MATRIX.md` 全為「已完成」、全部已推送，可建標籤 `v0.1.0-dev001`。