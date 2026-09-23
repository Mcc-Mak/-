#!/usr/bin/env python3
"""香港樓宇導賞團 — 建築物歷史產生流水線。

逐棟呼叫 crew-ai-orchestrator MCP（STDIO 傳輸），依 Standard.md 撰寫傳記式歷史：
  矩陣(待處理) → run_workflow → 輪詢 get_status → 依 Standard.md 驗收
  → 存檔 歷史/#{AUTO_INCREMENT:05}-{{slug}}-歷史.md → 更新 BUILDING_MATRIX.md + .prior
  → 逐棟 Git 提交並推送 dev-001（含 .prior）。

用法（在 repo 根目錄執行）：
  .\\pipenv\\Scripts\\python pipeline.py                # 處理全部待處理建築物
  .\\pipenv\\Scripts\\python pipeline.py --limit 3      # 只處理 3 棟（測試）
  .\\pipenv\\Scripts\\python pipeline.py --check-mcp    # 只驗證 MCP 連線與工具清單

環境需求：MCP server 會在有 `OPENAI_API_KEY` 時用 OpenAI，否則 fallback 至
OpenCode Zen（`~/.local/share/opencode/auth.json` 的 `opencode.key`，模型 big-pickle）。
兩者皆無時所有 job 會被標記 failed。
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent
MCP_DIR = Path(r"C:\Users\ccmak.AD\Desktop\Workplace\crew-ai-orchestrator-mcp")
MCP_EXE = MCP_DIR / ".venv" / "Scripts" / "mcp-crew-ai.exe"
PRIOR_FILE = ROOT / ".prior"
MATRIX_FILE = ROOT / "BUILDING_MATRIX.md"
OUTPUT_DIR = ROOT / "歷史"
HEADER_LEN = 6  # BUILDING_MATRIX.md 前 6 行（標題＋說明＋欄位標題）

LEVELS_ORDER = ["第一級", "第二級", "第三級", "第四級", "第五級"]

# ---------------------------------------------------------------------------
# .prior 自動遞增（優先權最高）
# ---------------------------------------------------------------------------


def next_increment(prior: set[int]) -> int:
    """下一個 AUTO_INCREMENT：`prior` 最高優先；空 `.prior` 取 00001。"""
    return (max(prior) + 1) if prior else 1


def load_prior() -> set[int]:
    if not PRIOR_FILE.exists():
        return set()
    vals: set[int] = set()
    for line in PRIOR_FILE.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line.isdigit():
            vals.add(int(line))
    return vals


def append_prior(inc: int) -> None:
    with PRIOR_FILE.open("a", encoding="utf-8") as fh:
        fh.write(f"{inc:05d}\n")


# ---------------------------------------------------------------------------
# BUILDING_MATRIX.md
# ---------------------------------------------------------------------------


def parse_matrix() -> tuple[list[str], list[list[str]]]:
    lines = MATRIX_FILE.read_text(encoding="utf-8").splitlines()
    header = lines[:HEADER_LEN]
    rows: list[list[str]] = []
    for line in lines[HEADER_LEN:]:
        if not line.strip().startswith("|"):
            continue
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        rows.append(cells)
    return header, rows


def write_matrix(header: list[str], rows: list[list[str]]) -> None:
    body = [
        "| {0} | {1} | {2} | {3} | {4} | {5} | {6} | {7} | {8} |".format(*row)
        for row in rows
    ]
    MATRIX_FILE.write_text("\n".join(header + body) + "\n", encoding="utf-8")


def slugify(name: str) -> str:
    """英文名轉 kebab-case；缺失時以中文名兜底並移除非 alnum 字元。"""
    s = name.strip().lower()
    s = re.sub(r"[^a-z0-9\u4e00-\u9fff]+", "-", s)
    s = re.sub(r"-{2,}", "-", s).strip("-")
    return s or f"building-{int(time.time())}"


# ---------------------------------------------------------------------------
# Standard.md 驗收（第四章）
# ---------------------------------------------------------------------------


def validate_output(text: str) -> tuple[bool, str]:
    """回傳 (是否通過, 原因)。不合格一律拒絕，不存檔。"""
    if not text or len(text.strip()) < 100:
        return False, "輸出過短（<100 字元）"
    if "參考文獻" not in text:
        return False, "文末缺少「參考文獻」章節"
    if "歷史沿革" not in text:
        return False, "缺少「歷史沿革」敘事段落（退回純編年列表）"
    if not re.search(r"\[\d+\]", text):
        return False, "全文無任何引用編號 [n]"
    # 參考文獻必須按第一級→第五級出現（存在即依序）
    found = [lv for lv in LEVELS_ORDER if lv in text]
    ordered = sorted(found, key=lambda lv: text.index(lv))
    if ordered != found:
        return False, f"參考文獻未按可信度排序（找到：{'、'.join(found)}）"
    return True, "OK"


# ---------------------------------------------------------------------------
# MCP 呼叫（STDIO）
# ---------------------------------------------------------------------------


def start_mcp():
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client

    params = StdioServerParameters(
        command=str(MCP_EXE),
        args=["--agents", "agents.yml", "--tasks", "tasks.yml"],
        cwd=str(MCP_DIR),
        env={k: v for k, v in os.environ.items()},
    )
    return stdio_client(params), ClientSession


async def check_mcp() -> None:
    async with start_mcp()[0] as (r, w):
        async with start_mcp()[1](r, w) as session:
            await session.initialize()
            tools = await session.list_tools()
            names = sorted(t.name for t in tools.tools)
            print("MCP 連線成功，工具清單：", names)
            if not names:
                sys.exit("MCP 工具清單為空")


async def run_one(session: object, building: list[str], inc: int) -> dict:
    en, zh = building[1], building[2]
    topic = (
        f"為下列香港建築物撰寫傳記式歷史（依 Standard.md 規範），"
        f"完整遵守參考文獻分級與引用規則：\n"
        f"英文名稱：{en or '（無）'}\n中文名稱：{zh or '（無）'}\n"
        f"來源清單序號：{building[0]}"
    )
    job_id = (await session.call_tool("run_workflow", {"topic": topic})).content[0].text
    start = time.time()
    while True:
        time.sleep(5)
        if time.time() - start > 1200:
            raise TimeoutError("輪詢超時（>20 分鐘）")
        resp = await session.call_tool("get_status", {"job_id": job_id})
        payload = {"text": resp.content[0].text}
        try:
            status = _parse_status(payload["text"])
        except (ValueError, KeyError):
            status = StatusSnapshot(status="pending")
        if status.status in ("completed", "failed"):
            return {"status": status.status, "error": status.error, "result": status.result}
    # pragma: no cover


class StatusSnapshot:
    def __init__(self, status: str, error: str | None = None, result: str | None = None) -> None:
        self.status = status
        self.error = error
        self.result = result


def _parse_status(text: str) -> StatusSnapshot:
    data = json.loads(text) if text.startswith("{") else {}
    return StatusSnapshot(
        status=str(data.get("status", "pending")),
        error=data.get("error"),
        result=data.get("result"),
    )


# ---------------------------------------------------------------------------
# Git 控制（強制，每棟一提交）
# ---------------------------------------------------------------------------


def git(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True, check=False)


def git_per_building(inc: int, name: str) -> None:
    files = [str(OUTPUT_DIR / f"{inc:05d}-*"), str(MATRIX_FILE), str(PRIOR_FILE)]
    git("add", "--", *files)
    msg = f"feat(歷史): 新增 {name} 歷史"
    git("commit", "-m", msg)
    push = git("push", "origin", "dev-001")
    if push.returncode != 0:
        git("pull", "--rebase", "origin", "dev-001")
        retry = git("push", "origin", "dev-001")
        if retry.returncode != 0:
            sys.exit(f"推送失敗且 rebase 重試失敗：{retry.stderr}")


async def main_async(args: argparse.Namespace) -> None:
    import asyncio

    if args.check_mcp:
        await check_mcp()
        return

    prior = load_prior()
    inc = next_increment(prior)
    header, rows = parse_matrix()
    pending = [r for r in rows if r[6] == "待處理"]
    if not pending:
        print("沒有待處理建築物，流程結束")
        return
    todo = pending[: args.limit] if args.limit else pending
    print(f"本次將處理 {len(todo)} 棟（AUTO_INCREMENT 從 {inc:05d} 開始）")

    async with start_mcp()[0] as (r, w):
        async with start_mcp()[1](r, w) as session:
            await session.initialize()
            for building in todo:
                en, zh = building[1], building[2]
                name = zh or en
                ok, err, result = False, "", ""
                for attempt in range(1, 4):  # 重試最多三次
                    try:
                        out = await run_one(session, building, inc)
                    except Exception as exc:  # noqa: BLE001
                        err = f"{type(exc).__name__}: {exc}"
                        print(f"[{inc:05d}] job 呼叫失敗（第 {attempt} 次）：{err}")
                        continue
                    if out["status"] == "failed":
                        err = out.get("error") or "job failed"
                        print(f"[{inc:05d}] job failed（第 {attempt} 次）：{err}")
                        continue
                    result = out.get("result") or ""
                    ok, reason = validate_output(result)
                    if not ok:
                        err = f"驗收不合格：{reason}"
                        print(f"[{inc:05d}] 拒絕輸出（第 {attempt} 次）：{reason}")
                        continue
                    break
                if not ok:
                    building[6] = "失敗"
                    building[8] = err.replace("|", "/")
                    print(f"[{inc:05d}] {name} -> 失敗（{err}）", flush=True)
                    # 失敗：不分配編號、不提交 Git
                    continue

                slug = slugify(en) if en else slugify(zh)
                fname = f"{inc:05d}-{slug}-歷史.md"
                (OUTPUT_DIR / fname).write_text(result.strip() + "\n", encoding="utf-8")
                building[6] = "已完成"
                building[7] = f"[歷史檔案路徑](歷史/{fname})"
                append_prior(inc)
                write_matrix(header, rows)
                git_per_building(inc, name)
                print(f"[{inc:05d}] {name} -> 已完成 {fname}", flush=True)
                inc += 1


def _has_credentials() -> bool:
    if os.environ.get("OPENAI_API_KEY"):
        return True
    auth = Path.home() / ".local/share/opencode/auth.json"
    try:
        return bool(json.loads(auth.read_text(encoding="utf-8")).get("opencode"))
    except (OSError, ValueError):
        return False


def dry_run(args: argparse.Namespace) -> None:
    """純預演：驗證矩陣解析、.prior 編號、slug、檔名與驗收邏輯，不產生任何副作用。"""
    prior = load_prior()
    inc = next_increment(prior)
    header, rows = parse_matrix()
    pending = [r for r in rows if r[6] == "待處理"]
    todo = pending[: args.limit] if args.limit else pending
    print(f"[dry-run] 待處理 {len(pending)} 棟；AUTO_INCREMENT 起點：{inc:05d}")
    for building in todo[:5]:
        en, zh = building[1], building[2]
        slug = slugify(en) if en else slugify(zh)
        fname = f"{inc:05d}-{slug}-歷史.md"
        print(f"[dry-run] {inc:05d} | {zh or en} | {fname}")
        inc += 1
    sample = (
        "某建築物的歷史沿革開始…… [1]\n\n## 大事年表\n\n" * 2
        + "## 第一級資料結論\n## 第二級資料\n## 第三級資料\n## 第四級資料\n## 第五級資料\n## 參考文獻\n"
    )
    ok, reason = validate_output(sample)
    print(f"[dry-run] validate_output(合格樣本) -> ok={ok} reason={reason}")
    bad = "只有年表，沒有敘事。\n"
    ok2, reason2 = validate_output(bad)
    print(f"[dry-run] validate_output(不合格樣本) -> ok={ok2} reason={reason2}")
    print("[dry-run] 完成，未更動任何檔案")


def main() -> None:
    parser = argparse.ArgumentParser(description="香港樓宇導賞團 建築物歷史流水線")
    parser.add_argument("--limit", type=int, default=None, help="本次最多處理 N 棟（--dry-run 時只看 N 棟計劃）")
    parser.add_argument("--check-mcp", action="store_true", help="只驗證 MCP 連線與工具清單")
    parser.add_argument("--dry-run", action="store_true", help="不呼叫 MCP／不改檔／不 Git，純預演")
    args = parser.parse_args()

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    if args.check_mcp:
        asyncio.run(main_async(args))
        return

    if args.dry_run:
        dry_run(args)
        return

    if not _has_credentials():
        sys.exit("無 LLM 憑證：缺少 OPENAI_API_KEY 且無 opencode Zen 認證（所有 job 都會失敗）")

    asyncio.run(main_async(args))


if __name__ == "__main__":
    main()