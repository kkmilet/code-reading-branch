#!/usr/bin/env python3
"""检查注释里的「文件:行号」引用是否真的跳得过去。

一条跳不过去的引用，比没有引用更糟：用户会去点，点不到，然后开始怀疑整份注释。
用法:
    python check_refs.py <repo> [--no-reading]
退出码: 0 通过 / 1 有坏引用 / 2 无法检查
"""

import argparse
import re
import sys
from pathlib import Path

SOURCE_EXT = "py|go|js|jsx|ts|tsx|java|rb|php|rs|kt|yml|yaml|toml|json|sql|mod"
REF_RE = re.compile(
    rf"([A-Za-z0-9_][A-Za-z0-9_./\\-]*\.(?:{SOURCE_EXT}))(?::(\d+))?(?![\w])"
)
# 「符号()（路径）」形式：既查路径，也查符号是否真的在这个文件里
SYM_REF_RE = re.compile(
    rf"([A-Za-z_][\w.]*)\(\)[（(]\s*([A-Za-z0-9_][A-Za-z0-9_./\\-]*\.(?:{SOURCE_EXT}))\s*[）)]"
)
IGNORE_DIRS = {
    "node_modules", "vendor", "dist", "build", "target",
    ".venv", "venv", "env", "__pycache__", ".next", ".nuxt",
    "coverage", ".git", ".idea", ".vscode", ".tox",
}
READ_MARK = "[READ]"


def iter_files(root: Path, exts=None):
    for p in root.rglob("*"):
        if not p.is_file():
            continue
        if any(part in IGNORE_DIRS for part in p.relative_to(root).parts):
            continue
        if exts and p.suffix.lower() not in exts:
            continue
        yield p


def build_index(root: Path):
    index = {}
    for p in iter_files(root):
        rel = p.relative_to(root).as_posix()
        try:
            n = p.read_bytes().count(b"\n") + 1
        except OSError:
            continue
        index[rel] = n
    return index


def resolve(ref: str, index):
    ref = ref.replace("\\", "/")
    while ref.startswith("./"):
        ref = ref[2:]
    if ref in index:
        return ref, ""
    cands = [p for p in index if p.endswith("/" + ref)]
    if len(cands) == 1:
        return cands[0], ""
    if len(cands) > 1:
        return None, f"有 {len(cands)} 个同名文件：" + "、".join(sorted(cands)[:3])
    return None, "找不到该文件"


def has_symbol(text: str, symbol: str) -> bool:
    """判断文件里是否真的定义了这个符号（函数 / 类 / 常量）。"""
    name = symbol.split(".")[-1]
    if not name:
        return False
    pats = [
        rf"\bdef\s+{re.escape(name)}\b",
        rf"\bclass\s+{re.escape(name)}\b",
        rf"\bfunction\s+{re.escape(name)}\b",
        rf"\b{re.escape(name)}\s*[:=]",
    ]
    return any(re.search(p, text) for p in pats)


def main() -> int:
    ap = argparse.ArgumentParser(description="检查注释中的文件引用")
    ap.add_argument("repo")
    ap.add_argument("--no-reading", action="store_true", help="不检查 READING.md")
    args = ap.parse_args()

    root = Path(args.repo).resolve()
    if not root.is_dir():
        print(f"✗ 路径不存在: {root}")
        return 2

    index = build_index(root)
    if not index:
        print("✗ 仓库里没有可索引的文件")
        return 2

    targets = [p for p in iter_files(root) if p.suffix.lower() in {".py", ".go", ".js", ".ts", ".jsx", ".tsx", ".java", ".rb", ".php", ".rs", ".kt"}]
    if not args.no_reading and (root / "READING.md").exists():
        targets.append(root / "READING.md")

    total = 0
    bad = []
    ambiguous = []

    for path in targets:
        try:
            lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
        except OSError:
            continue
        rel_self = path.relative_to(root).as_posix()
        for lineno, line in enumerate(lines, 1):
            if READ_MARK not in line and path.name != "READING.md":
                continue

            covered = []
            for sm in SYM_REF_RE.finditer(line):
                symbol, ref = sm.group(1), sm.group(2)
                covered.append((sm.start(), sm.end()))
                total += 1
                resolved, why = resolve(ref, index)
                if resolved is None:
                    (ambiguous if "同名" in why else bad).append(
                        (rel_self, lineno, f"{symbol}（{ref}）", why)
                    )
                    continue
                try:
                    ftext = (root / resolved).read_text(encoding="utf-8", errors="replace")
                except OSError:
                    ftext = ""
                if not has_symbol(ftext, symbol):
                    bad.append(
                        (rel_self, lineno, f"{symbol}（{ref}）",
                         f"{resolved} 里找不到符号 {symbol}")
                    )

            for m in REF_RE.finditer(line):
                if any(a <= m.start() < b for a, b in covered):
                    continue
                ref, line_no = m.group(1), m.group(2)
                if "://" in line[max(0, m.start() - 8): m.end()]:
                    continue
                if ref.startswith("http"):
                    continue
                total += 1
                resolved, why = resolve(ref, index)
                if resolved is None:
                    if "同名" in why:
                        ambiguous.append((rel_self, lineno, ref, why))
                    else:
                        bad.append((rel_self, lineno, ref, why))
                    continue
                if line_no:
                    limit = index[resolved]
                    if int(line_no) > limit:
                        bad.append((rel_self, lineno, f"{ref}:{line_no}", f"行号超出（{resolved} 只有 {limit} 行）"))

    print(f"检查引用: {total} 条")
    if bad or ambiguous:
        if ambiguous:
            print(f"\n✗ 无法确定指向（{len(ambiguous)}）：短文件名在仓库里有重名，读者跳过去可能落到错的文件")
            for where, ln, ref, why in ambiguous:
                print(f"  - {where}:{ln} → {ref}：{why}")
            print("  处理：改成相对于仓库根的完整路径（如 src/pkg/mod.py）。")
        if bad:
            print(f"\n✗ 跳不过去（{len(bad)}）：")
            for where, ln, ref, why in bad:
                print(f"  - {where}:{ln} → {ref}：{why}")
            print("  处理：改成真实路径，或降级为只写函数名。别留着跳不过去的引用。")
        return 1

    print("\n✅ 全部引用都能唯一解析到真实文件。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
