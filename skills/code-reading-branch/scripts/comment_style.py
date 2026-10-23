#!/usr/bin/env python3
"""检查注释的行宽、符号、密度下限。

对应五类阅读体验问题：
- 超宽：一行注释在 IDE 里折成三行，占满一屏
- 符号：框线、箭头、圆圈数字，读的时候要猜
- 空壳：只有文件头，函数体一句注释都没有
- 罗列：一行堆四个以上函数名
- 脏行：注释被粘到代码行末尾

用法:
    python comment_style.py <repo> [--max-width 72] [--max-names 2]
退出码: 0 通过 / 1 不合规 / 2 无法检查
"""

import argparse
import re
import sys
import unicodedata
from pathlib import Path

IGNORE_DIRS = {
    "node_modules", "vendor", "dist", "build", "target",
    ".venv", "venv", "env", "__pycache__", ".next", ".nuxt",
    "coverage", ".git", ".idea", ".vscode", ".tox",
}

SOURCE_EXT = {".py", ".go", ".js", ".jsx", ".ts", ".tsx", ".java", ".rb", ".php", ".rs", ".kt"}

READ_COMMENT = re.compile(r"^(\s*)(#|//)\s*\[READ\]")
BANNED_CHARS = {
    "─": "框线", "━": "框线", "═": "框线",
    "←": "箭头", "→": "箭头", "↑": "箭头", "↓": "箭头",
    "·": "间隔点",
    "①": "圈号", "②": "圈号", "③": "圈号", "④": "圈号", "⑤": "圈号",
    "⑥": "圈号", "⑦": "圈号", "⑧": "圈号", "⑨": "圈号",
    "【": "方括号", "】": "方括号",
}
CALL_RE = re.compile(r"[A-Za-z_][A-Za-z0-9_]*\(")


def width(s: str) -> int:
    """中文/全角算 2，其余算 1。"""
    return sum(2 if unicodedata.east_asian_width(ch) in ("W", "F") else 1 for ch in s)


def iter_sources(root: Path):
    for p in root.rglob("*"):
        if not p.is_file() or p.suffix.lower() not in SOURCE_EXT:
            continue
        if any(part in IGNORE_DIRS for part in p.relative_to(root).parts):
            continue
        yield p


def main() -> int:
    ap = argparse.ArgumentParser(description="检查注释样式")
    ap.add_argument("repo")
    ap.add_argument("--max-width", type=int, default=72)
    ap.add_argument("--max-names", type=int, default=2)
    ap.add_argument("--max-header", type=int, default=12)
    args = ap.parse_args()

    root = Path(args.repo).resolve()
    if not root.is_dir():
        print(f"✗ 路径不存在: {root}")
        return 2

    errors = []
    checked_files = 0
    total_lines = 0

    for path in iter_sources(root):
        try:
            lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
        except OSError:
            continue
        read_idx = [i for i, ln in enumerate(lines) if "[READ]" in ln]
        if not read_idx:
            continue
        checked_files += 1
        rel = path.relative_to(root).as_posix()

        # 文件头 = 第一段连续的 [READ] 行；其余（含类前注释）算正文
        header = 0
        k = read_idx[0]
        while k < len(lines) and "[READ]" in lines[k]:
            header += 1
            k += 1
        body = len(read_idx) - header

        for i in read_idx:
            ln = lines[i]
            total_lines += 1

            m = READ_COMMENT.match(ln)
            if not m:
                errors.append(f"{rel}:{i+1} 注释没独占整行（可能被拼到代码后面）")
                continue

            w = width(ln)
            if w > args.max_width:
                errors.append(f"{rel}:{i+1} 行宽 {w} 超过 {args.max_width}（会折行）")

            for ch, kind in BANNED_CHARS.items():
                if ch in ln:
                    errors.append(f"{rel}:{i+1} 出现{kind}「{ch}」")
                    break

            names = CALL_RE.findall(ln)
            if len(names) > args.max_names:
                errors.append(
                    f"{rel}:{i+1} 一行出现 {len(names)} 个函数名（{', '.join(names[:4])}…），上限 {args.max_names}"
                )

        if header > args.max_header:
            errors.append(f"{rel} 文件头 {header} 行，超过 {args.max_header} 行")

        need_body = 1 if len(lines) < 50 else 2
        if body < need_body:
            errors.append(
                f"{rel} 只有表头、没有函数级注释（当前 {body} 条，至少 {need_body} 条）"
            )

    if not checked_files:
        print("没找到任何 [READ] 注释，跳过")
        return 0

    print(f"检查 {checked_files} 个文件、{total_lines} 行注释")
    if errors:
        print(f"\n✗ {len(errors)} 处不合规：")
        for e in errors[:40]:
            print(f"  - {e}")
        if len(errors) > 40:
            print(f"  …… 另有 {len(errors) - 40} 处")
        print("\n处理：按 references/comments.md 改。宽度超了先断行，符号删掉换中文词。")
        return 1

    print("✅ 行宽、符号、密度都合规。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
