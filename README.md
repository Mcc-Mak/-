# 香港樓宇導賞團

自動化撰寫香港建築物傳記式歷史的專案。從差餉物業估價署（差估署）的「物業資訊網」XML 資料源逐一提取建築物名稱，交由 CrewAI 編排器 MCP 依 `Standard.md` 為每棟建築物撰寫傳記式歷史（敘事主軸＋大事年表），並逐棟提交至 Git。

## 工作流程

1. 取得兩個 XML（市區 `bnb-u`、新界 `bnb-nt`）並解析建築物中英名稱。
2. 將建築物清單寫入 `BUILDING_MATRIX.md`（狀態「待處理」）。
3. 逐棟經由 CrewAI 編排器 MCP 的 `run_workflow` 生成歷史，輪詢至完成。
4. 輸出存入 `歷史/#{AUTO_INCREMENT:5位前導零}-{{building-slug}}-歷史.md`（slug 為英文名 kebab-case；遞增編號由 `.prior` 決定）。
5. 每一棟完成即 Git 提交並推送至 `dev-001` 分支。

## 資料來源

- 市區：`https://res.data.gov.hk/api/get-download-file?name=https%3A%2F%2Fwww.rvd.gov.hk%2Fdatagovhk%2Fbnb-u.xml`
- 新界：`https://res.data.gov.hk/api/get-download-file?name=https%3A%2F%2Fwww.rvd.gov.hk%2Fdatagovhk%2Fbnb-nt.xml`

## 輸出結構

- `歷史/`：每棟建築物一份紀傳式歷史 Markdown（檔名前置 5 位自動遞增編號，由 `.prior` 驅動）。
- `BUILDING_MATRIX.md`：建築物清單與處理狀態（`待處理`／`已完成`／`失敗`）。
- `Standard.md`：歷史生成規範（缺失則流程必須停止）。

## 執行方式

準備：`Standard.md` 完整存在；CrewAI 編排器 MCP 已註冊於 repo 級 `opencode.json`（STDIO；見 `AGENTS.md` 的啟動命令與工具清單）。LLM 憑證：有 `OPENAI_API_KEY` 用 OpenAI，否則 fallback 至 OpenCode Zen（模型 `big-pickle`）。

一鍵自動化（Python 需能 import `mcp` 客戶端套件，可使用 MCP venv 的 python）：

```powershell
& "C:\Users\ccmak.AD\Desktop\Workplace\crew-ai-orchestrator-mcp\.venv\Scripts\python.exe" pipeline.py --check-mcp   # 驗證 MCP 連線
& "C:\Users\ccmak.AD\Desktop\Workplace\crew-ai-orchestrator-mcp\.venv\Scripts\python.exe" pipeline.py --dry-run --limit 3   # 純預演，不產生副作用
& "C:\Users\ccmak.AD\Desktop\Workplace\crew-ai-orchestrator-mcp\.venv\Scripts\python.exe" pipeline.py   # 正式執行全部待處理建築物
```

流水線行為：讀取 `BUILDING_MATRIX.md`「待處理」行 → 依 `.prior` 決定 AUTO_INCREMENT → `run_workflow` → 輪詢 `get_status` → 依 `Standard.md` 第四章驗收（缺引用／文獻未分級排序／只有年表 → 拒絕）→ 存檔 `歷史/NNNNN-{{slug}}-歷史.md` → 更新矩陣與 `.prior` → 逐棟 Git 提交並推送至 `dev-001`。任何一棟重試最多三次，仍失敗則標「失敗」於備註並跳過該棟提交。

詳細運作規則（MCP 配置、Git 控制、錯誤處理）見 `AGENTS.md`。