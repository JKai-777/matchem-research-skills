#!/usr/bin/env python3
"""verify_repo.py — 复刻 DSH 技能管理插件（@michengai/dsh-skills-manager 1.2.13）
对 GitHub 仓库订阅的扫描规则，在推送到 GitHub 之前就地把问题查出来。

规则出处（插件 lib/repositories.js / lib/core.js）：
  LIMIT = 32 << 20                     单仓库归档上限        repositories.js:7
  decodeRepositoryArchive              解压总量 64MiB / 1e4 条目   repositories.js:101
  refresh 扫描循环                     找 SKILL.md、尺寸、有效判定  repositories.js:637-654
  valid 判定                            见下面 valid_of()      repositories.js:653
  parseSkillDoc                         frontmatter 解析        core.js:757-801

用法：
  python tools/verify_repo.py [仓库根目录] [--subdir skills]
"""
from __future__ import annotations

import io
import re
import sys
import zipfile
from pathlib import Path

ZIP_LIMIT = 32 << 20          # 32 MiB，codeload 归档
RAW_LIMIT = 64 << 20          # 解压总量
ENTRY_LIMIT = 10_000          # 归档条目数
SKILL_DOC_LIMIT = 256 << 10   # 单个 SKILL.md
BODY_LIMIT = 4 << 20          # 技能正文合计
SKILL_COUNT_LIMIT = 500
FILE_COUNT_LIMIT = 1000

NAME_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
RESERVED_RE = re.compile(r"^(con|prn|aux|nul|com[1-9]|lpt[1-9])$", re.I)
FIELD_RE = re.compile(r"^([A-Za-z0-9_-]+)\s*:\s*(.*)$")
BLOCK_RE = re.compile(r"^([>|])(?:([1-9])[-+]?|[-+]([1-9])?)?\s*$")


def decode_yaml_scalar(v: str) -> str:
    s = (v or "").strip()
    if len(s) >= 2 and s[0] == '"' and s[-1] == '"':
        try:
            import json
            out = json.loads(s)
            if isinstance(out, str):
                return out
        except Exception:
            pass
    if len(s) >= 2 and s[0] == "'" and s[-1] == "'":
        return s[1:-1].replace("''", "'")
    return s


def parse_skill_doc(src: str) -> dict:
    """镜像 core.js:757 parseSkillDoc（单行标量 + | / > 块标量）。

    JS 的 String.prototype.trim 会去掉 U+FEFF，Python 的 str.strip 不会，
    这里显式剥一次，免得带 BOM 的文件在本地被误判为"没有 frontmatter"
    （插件那边其实是能过的）。
    """
    src = src.lstrip("\ufeff")
    lines = re.split(r"\r?\n", src)
    mapping: dict[str, str] = {}
    has_frontmatter = False
    body = src
    if lines and lines[0].strip() == "---":
        end = -1
        for i in range(1, len(lines)):
            if lines[i].strip() == "---":
                end = i
                break
        if end >= 0:
            has_frontmatter = True
            i = 1
            while i < end:
                m = FIELD_RE.match(lines[i])
                if not m:
                    i += 1
                    continue
                key, raw = m.group(1), m.group(2)
                block = BLOCK_RE.match(raw)
                if block:
                    content = []
                    while i + 1 < end and (re.match(r"^\s", lines[i + 1]) or lines[i + 1] == ""):
                        i += 1
                        content.append(lines[i])
                    explicit = block.group(2) or block.group(3)
                    widths = [len(re.match(r"^\s*", ln).group(0)) for ln in content if ln.strip() != ""]
                    indent = int(explicit) if explicit else (min(widths) if widths else 0)
                    normalized = [ln[min(indent, len(ln)):] for ln in content]
                    if block.group(1) == ">":
                        mapping[key] = re.sub(r"\s+", " ", " ".join(normalized)).strip()
                    elif explicit:
                        mapping[key] = re.sub(r"^\n+|\n+$", "", "\n".join(normalized))
                    else:
                        mapping[key] = "\n".join(normalized).strip()
                else:
                    mapping[key] = decode_yaml_scalar(raw)
                i += 1
            body = "\n".join(lines[end + 1:])
    return {"map": mapping, "body": body, "hasFrontmatter": has_frontmatter}


def valid_of(parsed: dict) -> tuple[bool, list[str]]:
    reasons = []
    name = str(parsed["map"].get("name", ""))
    desc = str(parsed["map"].get("description", ""))
    if not parsed["hasFrontmatter"]:
        reasons.append("没有 frontmatter（首行须为 --- 且有闭合 ---）")
    if not NAME_RE.match(name):
        reasons.append(f"name 不是 kebab-case：{name!r}（须匹配 ^[a-z0-9]+(?:-[a-z0-9]+)*$）")
    if RESERVED_RE.match(name):
        reasons.append(f"name 是 Windows 保留名：{name!r}")
    if len(name) > 100:
        reasons.append(f"name 超过 100 字符（{len(name)}）")
    if not desc:
        reasons.append("description 为空")
    return (not reasons, reasons)


def human(n: int) -> str:
    for unit in ("B", "KiB", "MiB", "GiB"):
        if n < 1024 or unit == "GiB":
            return f"{n:.1f} {unit}" if unit != "B" else f"{n} B"
        n /= 1024.0
    return f"{n} B"


def collect(root: Path, subdir: str | None):
    """镜像 decodeRepositoryArchive + refresh：返回 entries 与技能列表。"""
    entries: dict[str, bytes] = {}
    for p in sorted(root.rglob("*")):
        if not p.is_file():
            continue
        rel = p.relative_to(root).as_posix()
        if rel.split("/")[0] == ".git":
            continue
        entries[rel] = p.read_bytes()

    skills, errors = [], []
    body_total = 0
    for path, data in entries.items():
        if path != "SKILL.md" and not path.endswith("/SKILL.md"):
            continue
        directory = "" if path == "SKILL.md" else path[: -len("SKILL.md")]
        directory = directory.rstrip("/")
        if subdir and directory != subdir and not directory.startswith(subdir + "/"):
            continue
        if len(data) > SKILL_DOC_LIMIT:
            errors.append(f"{path}: SKILL.md {human(len(data))} 超过 256 KiB")
            continue
        if len(skills) >= SKILL_COUNT_LIMIT:
            errors.append("技能数超过 500")
            break
        body_total += len(data)
        if body_total > BODY_LIMIT:
            errors.append("技能正文合计超过 4 MiB")
            break
        parsed = parse_skill_doc(data.decode("utf-8", "replace"))
        name = str(parsed["map"].get("name", "")) or (directory.split("/")[-1] if directory else root.name)
        desc = str(parsed["map"].get("description", ""))
        prefix = directory + "/" if directory else ""
        files = [p for p in entries if p.startswith(prefix)]
        if len(files) > FILE_COUNT_LIMIT:
            errors.append(f"{path}: 技能文件数 {len(files)} 超过 1000")
        ok, reasons = valid_of(parsed)
        skills.append({
            "path": directory, "name": name, "description": desc,
            "bytes": len(data), "files": files, "valid": ok, "reasons": reasons,
        })
    return entries, skills, errors


def zip_size(root: Path) -> int:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as zf:
        for p in sorted(root.rglob("*")):
            if not p.is_file():
                continue
            rel = p.relative_to(root).as_posix()
            if rel.split("/")[0] == ".git":
                continue
            zf.write(p, f"{root.name}/{rel}")
    return buf.tell()


def main() -> int:
    argv = [a for a in sys.argv[1:]]
    subdir = None
    if "--subdir" in argv:
        i = argv.index("--subdir")
        subdir = argv[i + 1].strip("/")
        del argv[i:i + 2]
    # 不给路径时默认用仓库根本身（本文件的上一级），而不是当前工作目录——
    # 否则在别的目录下运行会把无关文件一起扫进来，误报 OVER。
    default_root = Path(__file__).resolve().parent.parent
    root = Path(argv[0]).resolve() if argv else default_root
    if not root.is_dir():
        print(f"目录不存在：{root}")
        return 2

    print(f"仓库根：{root}")
    if subdir:
        print(f"只扫子目录：{subdir}/")
    print()

    entries, skills, errors = collect(root, subdir)
    raw = sum(len(v) for v in entries.values())

    # 尺寸
    rows = [
        ("归档条目数", len(entries), ENTRY_LIMIT),
        ("解压总量", raw, RAW_LIMIT),
        ("技能数", len(skills), SKILL_COUNT_LIMIT),
        ("技能正文合计", sum(s["bytes"] for s in skills), BODY_LIMIT),
    ]
    limit_fail = False
    for label, value, cap in rows:
        unit = "" if isinstance(value, int) and cap in (ENTRY_LIMIT, SKILL_COUNT_LIMIT) else ""
        shown = f"{value}" if label in ("归档条目数", "技能数") else human(value)
        capsh = f"{cap}" if label in ("归档条目数", "技能数") else human(cap)
        flag = "OK " if value <= cap else "OVER"
        if value > cap:
            limit_fail = True
        print(f"  [{flag}] {label:<12} {shown:>12} / {capsh}")

    zs = zip_size(root)
    zflag = "OK " if zs <= ZIP_LIMIT else "OVER"
    if zs > ZIP_LIMIT:
        limit_fail = True
    print(f"  [{zflag}] {'归档 zip 预估':<12} {human(zs):>12} / {human(ZIP_LIMIT)}   （本地压缩预估，codeload 实际值会有差异）")
    print()

    # 技能表
    width = max([len(s["name"]) for s in skills] + [4])
    invalid = 0
    print("技能：")
    for s in skills:
        mark = "valid  " if s["valid"] else "INVALID"
        if not s["valid"]:
            invalid += 1
        print(f"  [{mark}] {s['name']:<{width}}  文件 {len(s['files']):>2}  说明 {human(s['bytes']):>9}  目录 {s['path'] or '.'}")
        for r in s["reasons"]:
            print(f"              - {r}")
    if not skills:
        print("  （没有找到任何 SKILL.md）")
    print()

    # 目录名与 name 不一致（不是插件硬性要求，但安装后目录名与技能名会不同，容易混）
    mismatch = [s for s in skills if s["path"] and s["path"].split("/")[-1] != s["name"]]
    if mismatch:
        print("提示（非错误）：目录名与 frontmatter name 不一致，安装后以 name 为准：")
        for s in mismatch:
            print(f"  {s['path']}  ->  {s['name']}")
        print()

    dupes: dict[str, list[str]] = {}
    for s in skills:
        dupes.setdefault(s["name"], []).append(s["path"])
    dup = {k: v for k, v in dupes.items() if len(v) > 1}
    if dup:
        print("错误：同名技能重复（安装时会冲突，第二个装不上）：")
        for k, v in dup.items():
            print(f"  {k}: {', '.join(v)}")
        invalid += len(dup)
        print()

    if errors:
        print("扫描错误：")
        for e in errors:
            print(f"  - {e}")
        print()

    bad = invalid + (1 if limit_fail else 0) + len(errors)
    print("结论：", "PASS —— 可以推送" if bad == 0 else f"FAIL —— {bad} 处问题需要修")
    return 0 if bad == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
