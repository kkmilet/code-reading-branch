#!/usr/bin/env python3
"""校验阅读分支：剥离所有 [READ] 注释后必须与基线逐字节一致，并统计覆盖率。

用法:
    python verify.py <repo> [--base main]

退出码: 0 通过 / 1 校验失败 / 2 无法校验
"""

import argparse
import subprocess
import sys
from pathlib import Path

SOURCE_EXT = {
    ".py", ".go", ".js", ".jsx", ".ts", ".tsx",
    ".java", ".rb", ".php", ".rs", ".kt", ".scala", ".cs",
}

IGNORE_DIRS = {
    "node_modules", "vendor", "dist", "build", "target",
    ".venv", "venv", "env", "__pycache__", ".next", ".nuxt",
    "coverage", ".git", ".idea", ".vscode", ".tox", ".mypy_cache",
}

# 这些文件是自己新增的产物：仅当状态为「新增(A)」时放行；
# 若同名的项目文件被修改(M)，仍然要查，否则等于开了一个静默改动的后门。
ALLOW_FILES = {"reading.md", "glossary.md"}
ALLOW_PREFIXES = ("reading/", "docs/code-reading/")


def git(repo, *args, binary=False):
    r = subprocess.run(["git", *args], cwd=str(repo), capture_output=True)
    if r.returncode != 0:
        return None
    return r.stdout if binary else r.stdout.decode("utf-8", "replace").strip()


def detect_base(repo, explicit):
    if explicit:
        return explicit
    for cand in ("main", "master", "develop", "trunk"):
        if git(repo, "rev-parse", "--verify", "--quiet", cand) is not None:
            return cand
    return None


def strip_read(data: bytes) -> bytes:
    """删掉所有以 [READ] 开头的注释行，其余字节原样保留。"""
    out = []
    for line in data.splitlines(keepends=True):
        s = line.lstrip(b" \t")
        if s.startswith(b"#"):
            if s[1:].lstrip(b" \t").startswith(b"[READ]"):
                continue
        elif s.startswith(b"//"):
            if s[2:].lstrip(b" \t").startswith(b"[READ]"):
                continue
        out.append(line)
    return b"".join(out)


def has_read(data: bytes) -> bool:
    for line in data.splitlines():
        s = line.lstrip(b" \t")
        if s.startswith(b"#") and s[1:].lstrip(b" \t").startswith(b"[READ]"):
            return True
        if s.startswith(b"//") and s[2:].lstrip(b" \t").startswith(b"[READ]"):
            return True
    return False


def norm(data: bytes) -> bytes:
    return data.replace(b"\r\n", b"\n")


def eol_style(data: bytes) -> bytes:
    return b"\r\n" if b"\r\n" in data else b"\n"


def is_allowed(rel: str, status: str) -> bool:
    """只有「新增」的产物文件放行；被修改的同名文件仍然受检。"""
    if status != "A":
        return False
    low = rel.replace("\\", "/").lower()
    if low in ALLOW_FILES:
        return True
    return low.startswith(ALLOW_PREFIXES)


def base_from_reading_md(repo: Path):
    """优先用 READING.md 里记录的 base_commit（固定 SHA），避免基线随分支漂移。"""
    for candidate in (repo / "READING.md", repo / "READING" / "READING.md"):
        if not candidate.exists():
            continue
        try:
            text = candidate.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        for line in text.splitlines():
            if line.lower().startswith("base_commit:"):
                value = line.split(":", 1)[1].strip()
                if value and value not in {"-", "unknown", "null"}:
                    return value
    return None


def iter_sources(root: Path):
    for p in root.rglob("*"):
        if not p.is_file():
            continue
        if p.suffix.lower() not in SOURCE_EXT:
            continue
        if any(part in IGNORE_DIRS for part in p.relative_to(root).parts):
            continue
        yield p


def main() -> int:
    ap = argparse.ArgumentParser(description="校验阅读分支是否为只增不改")
    ap.add_argument("repo", help="仓库路径")
    ap.add_argument("--base", default=None, help="基线分支，默认探测 main/master/develop")
    args = ap.parse_args()

    target = Path(args.repo).resolve()
    if not target.exists():
        print(f"✗ 路径不存在: {target}")
        return 2

    top = git(target, "rev-parse", "--show-toplevel")
    if not top:
        print("✗ 不是 git 仓库。按降级方案走：输出 READING/ 目录 + 注释清单，不校验字节一致。")
        return 2
    repo = Path(top)

    pinned = base_from_reading_md(repo)
    base = args.base or pinned or detect_base(repo, None)
    if not base:
        print("✗ 找不到基线：READING.md 里没有 base_commit，也没有 main/master/develop")
        return 2
    if git(repo, "rev-parse", "--verify", "--quiet", f"{base}^{{commit}}") is None:
        print(f"⚠️ 基线 {base} 无法解析为提交，回退到分支探测")
        base = detect_base(repo, None)
        pinned = None
        if not base:
            return 2

    changed_raw = git(repo, "diff", "--name-status", base)
    if changed_raw is None:
        print(f"✗ 无法与 {base} 比较")
        return 2

    entries = []
    for line in changed_raw.splitlines():
        parts = line.split("\t")
        if len(parts) < 2:
            continue
        status = parts[0][0]  # R100 -> R, C75 -> C
        entries.append((status, parts[-1]))

    annotated, failures, deleted, eol_changed = [], [], [], []

    for status, rel in entries:
        if is_allowed(rel, status):
            continue
        path = repo / rel
        if status == "D" or not path.exists():
            deleted.append(rel)
            continue
        if status == "A":
            failures.append((rel, "新增了源码文件（阅读分支不应新增源码，只应加注释）"))
            continue
        current = path.read_bytes()
        if not has_read(current):
            failures.append((rel, "文件被改动，但没有任何 [READ] 注释"))
            continue
        annotated.append(rel)
        original = git(repo, "show", f"{base}:{rel}", binary=True)
        if original is None:
            failures.append((rel, f"{base} 中不存在该文件（是否误新增？）"))
            continue
        if norm(strip_read(current)) != norm(original):
            failures.append((rel, "剥离 [READ] 后与基线不一致（有代码被改）"))
            continue
        if eol_style(current) != eol_style(original):
            eol_changed.append(rel)

    sources = list(iter_sources(repo))
    total = len(sources)
    with_read = sum(1 for p in sources if has_read(p.read_bytes()))

    tag = "（已固定，不随分支漂移）" if pinned else "（分支名，会漂移）"
    print(f"基线      : {base} {tag}")
    print(f"改动文件  : {len(entries)}")
    print(f"带注释文件: {len(annotated)}")
    print(f"源文件总数: {total}")
    if total:
        print(f"覆盖率    : {with_read}/{total} = {with_read / total:.1%}")
    if deleted:
        print(f"\n⚠️ 文件被删除（{len(deleted)}），请确认是否为有意：")
        for d in deleted:
            print(f"  - {d}")
    if eol_changed:
        print(f"\n⚠️ 换行符被改动（{len(eol_changed)}），建议保持原文件风格：")
        for e in eol_changed:
            print(f"  - {e}")

    if failures:
        print(f"\n✗ 校验失败（{len(failures)}）：")
        for rel, why in failures:
            print(f"  - {rel}：{why}")
        print("\n处理：把业务改动撤回，只保留 [READ] 注释行，然后重跑。")
        return 1

    print("\n✅ 通过：剥离注释后与基线逐字节一致，没有任何业务代码被改动。")
    print("   （覆盖率低不一定错：骨架文件之外的目录本来就不注释。）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
