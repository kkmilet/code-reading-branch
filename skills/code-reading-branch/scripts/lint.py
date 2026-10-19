#!/usr/bin/env python3
"""检查 READING.md 的结构是否合规。

把「站数/每站文件数/术语条数/证据标签/改动卡片」这些软要求变成硬闸门。
用法:
    python lint.py <repo_or_READING.md> [--max-lines 180]
退出码: 0 通过 / 1 不合规 / 2 找不到文件
"""

import argparse
import re
import sys
from pathlib import Path

REQUIRED_SECTIONS = [
    ("画像", ("画像", "一句话")),
    ("启动链路", ("跑起来", "启动", "runbook")),
    ("阅读路线", ("阅读路线", "路线")),
    ("旅程", ("旅程",)),
    ("模块地图", ("模块地图", "模块清单")),
    ("改动地图", ("改动地图", "改 x 先看", "改动卡片")),
    ("术语表", ("术语",)),
]

ALLOWED_LABELS = ("进站", "不用关注", "别改")
EVIDENCE_TAGS = ("【文档明示】", "【代码推断】", "【未知】")
BANNED_PHRASES = (
    "一般来说", "通常是", "应该是", "大体上",
    "综上所述", "总的来说", "值得注意的是", "简单来说",
    "希望对你有所帮助", "让我们一起", "首先，", "其次，",
)

STATION_RE = re.compile(r"^###\s*第\s*\d+\s*站")
PATH_RE = re.compile(r"`([^`]+\.(?:py|go|js|jsx|ts|tsx|java|rb|php|rs|kt|yml|yaml|toml|json|cfg|ini|env|md|sql|mod))`")


def split_sections(text):
    """按二级标题切段，返回 [(标题, 起止行号, 正文列表)]。"""
    lines = text.splitlines()
    heads = [(i, ln) for i, ln in enumerate(lines) if ln.startswith("## ")]
    out = []
    for idx, (start, head) in enumerate(heads):
        end = heads[idx + 1][0] if idx + 1 < len(heads) else len(lines)
        out.append((head.lstrip("#").strip(), start, lines[start:end]))
    return out


def find_section(sections, keywords):
    for title, start, body in sections:
        low = title.lower()
        if any(k.lower() in low for k in keywords):
            return title, start, body
    return None


def table_rows(body):
    """返回表格数据行（跳过表头与分隔行）。"""
    rows = []
    header_seen = False
    for i, ln in enumerate(body):
        s = ln.strip()
        if not s.startswith("|"):
            continue
        if set(s) <= set("|-: "):
            continue
        if not header_seen:
            header_seen = True
            continue
        rows.append((i, s))
    return rows


def main() -> int:
    ap = argparse.ArgumentParser(description="检查 READING.md 结构")
    ap.add_argument("target", help="仓库路径或 READING.md 路径")
    ap.add_argument("--max-lines", type=int, default=180)
    args = ap.parse_args()

    target = Path(args.target)
    if target.is_dir():
        target = target / "READING.md"
    if not target.exists():
        print(f"✗ 找不到 {target}（用 --path 指定，或先跑 S3 生成骨架）")
        return 2

    text = target.read_text(encoding="utf-8", errors="replace")
    lines = text.splitlines()
    sections = split_sections(text)

    errors = []

    if len(lines) > args.max_lines:
        errors.append(f"全文 {len(lines)} 行，超过上限 {args.max_lines}——说明在写报告，不是写导航")

    if "base_commit:" not in text[:800].lower():
        errors.append("frontmatter 缺 base_commit（校验基线会随分支漂移）")

    for name, keys in REQUIRED_SECTIONS:
        if not find_section(sections, keys):
            errors.append(f"缺少章节：{name}")

    route = find_section(sections, ("阅读路线", "路线"))
    if route:
        title, start, body = route
        stations = [(i, ln) for i, ln in enumerate(body) if STATION_RE.match(ln)]
        if not 3 <= len(stations) <= 8:
            errors.append(f"站数为 {len(stations)}，硬边界是 3~8")
        for i, ln in stations:
            n = int(re.search(r"第\s*(\d+)\s*站", ln).group(1))
            nxt = next((k for k in range(i + 1, len(body)) if body[k].startswith("### ")), len(body))
            fields = [x for x in body[i + 1: nxt] if x.startswith("**")]
            if len(fields) > 3:
                errors.append(f"第 {n} 站写了 {len(fields)} 个字段，上限 3 个（为什么 / 读什么 / 能说出什么）")
            read_line = ""
            for nxt_line in body[i + 1: i + 6]:
                if nxt_line.startswith("**要读**"):
                    read_line = nxt_line
                    break
            if not read_line:
                errors.append(f"第 {n} 站缺少「**要读**」行")
                continue
            files = PATH_RE.findall(read_line)
            if len(files) > 4:
                errors.append(f"第 {n} 站要读 {len(files)} 个文件，超过每站 4 个上限")

    runbook = find_section(sections, ("跑起来", "启动", "runbook"))
    if runbook:
        _, start, body = runbook
        for i, row in table_rows(body):
            if not any(tag in row for tag in EVIDENCE_TAGS):
                errors.append(f"L{start + i + 1} 启动链缺少证据标签（【文档明示】/【代码推断】/【未知】）")

    modmap = find_section(sections, ("模块地图", "模块清单"))
    if modmap:
        _, start, body = modmap
        rows = table_rows(body)
        if not rows:
            errors.append("模块地图没有表格行")
        for i, row in rows:
            cells = [c.strip() for c in row.strip().strip("|").split("|")]
            if len(cells) < 3:
                errors.append(f"L{start + i + 1} 模块地图行缺第三列（要不要看）")
                continue
            label = cells[2]
            if not label.startswith(ALLOWED_LABELS):
                errors.append(
                    f"L{start + i + 1} 模块标签为「{label[:12]}」，只允许 进站 / 不用关注 / 别改"
                )

    changes = find_section(sections, ("改动地图", "改 x 先看", "改动卡片"))
    if changes:
        _, start, body = changes
        blocks = [(i, ln) for i, ln in enumerate(body) if ln.startswith("### ")]
        if len(blocks) < 3:
            errors.append(f"改动卡片只有 {len(blocks)} 张，至少 3 张")
        for k, (i, _) in enumerate(blocks):
            end = blocks[k + 1][0] if k + 1 < len(blocks) else len(body)
            chunk = "\n".join(body[i:end])
            if "影响面" not in chunk:
                errors.append(f"L{start + i + 1} 改动卡片缺「影响面」")
            if "验证" not in chunk:
                errors.append(f"L{start + i + 1} 改动卡片缺「验证」")

    glossary = find_section(sections, ("术语",))
    if glossary:
        _, start, body = glossary
        n = len(table_rows(body))
        if n > 12:
            errors.append(f"术语表 {n} 条，超过 12 条上限（只收“看名字猜不到”的）")

    journey = find_section(sections, ("旅程",))
    if journey:
        _, start, body = journey
        joined = "\n".join(body)
        if "```mermaid" not in joined:
            errors.append("旅程图缺少 mermaid 代码块")
        if not re.search(r"[①②③④⑤]", joined):
            errors.append("旅程图缺少 ①②③ 编号步骤")

    for i, ln in enumerate(lines, 1):
        for p in BANNED_PHRASES:
            if p in ln:
                errors.append(f"L{i} 出现空话「{p}」（不承载信息）：{ln.strip()[:40]}")

    if errors:
        print(f"✗ {target.name} 结构检查未通过（{len(errors)} 处）：")
        for e in errors:
            print(f"  - {e}")
        print("\n修完再重跑。这些不是风格建议，是交付门槛。")
        return 1

    print(f"✅ {target.name} 结构检查通过：{len(sections)} 节 / {len(lines)} 行。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
