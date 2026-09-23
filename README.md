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

前置條件：`Standard.md` 完整存在；本機已預備 CrewAI 編排器 MCP（見 `AGENTS.md` 的啟動命令與工具清單）；實際生成需要 `OPENAI_API_KEY`。

詳細運作規則（MCP 配置、Git 控制、錯誤處理）見 `AGENTS.md`。