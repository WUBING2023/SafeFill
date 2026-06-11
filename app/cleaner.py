# -*- coding: utf-8 -*-
"""
SafeFill-Cleaner — 隐私清理工具
preview: 预览将被清理的文件
clean:   执行清理（需 --confirm CLEAN）
"""

import os, sys, json
from datetime import datetime
from pathlib import Path

PROJECT = Path(__file__).resolve().parent.parent
DOCS_DIR = PROJECT / "docs"
PREVIEW_REPORT = DOCS_DIR / "cleaner_preview_report.md"
CLEAN_REPORT = DOCS_DIR / "cleaner_clean_report.md"

# 默认清理目录
DEFAULT_CLEAN_DIRS = [
    "input_forms", "new_forms", "candidate_reviews",
    "draft_outputs", "filling_reports", "review_html",
    "review_results", "final_reports",
    "api_previews", "api_results", "api_logs", "logs",
]

# 可选清理（需 --include-final）
OPTIONAL_CLEAN_DIRS = ["final_outputs"]

# 永久排除
NEVER_CLEAN = [
    "vault", "app", "skills", "docs", "deprecated",
    "SKILL.md", "README.md", "AGENTS.md", ".gitignore",
    "app/api_config.json", "app/api_config_template.json",
    "vault/profiles/profile_template.json",
]

def collect_files(dirs: list) -> dict:
    """收集所有待清理文件。返回 {dir: [(name, size, mtime), ...]}"""
    result = {}
    for d in dirs:
        dp = PROJECT / d
        if not dp.exists():
            result[d] = []
            continue
        files = []
        for f in dp.iterdir():
            if f.is_file():
                st = f.stat()
                files.append((f.name, st.st_size, st.st_mtime))
        result[d] = sorted(files)
    return result

def cmd_preview():
    """预览模式：只报告，不删除。"""
    print(f"\n{'='*50}")
    print(f"  SafeFill-Cleaner 预览")
    print(f"  {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'='*50}")

    files = collect_files(DEFAULT_CLEAN_DIRS)
    total = sum(len(v) for v in files.values())

    print(f"\n将清理 {len(DEFAULT_CLEAN_DIRS)} 个目录，共 {total} 个文件:\n")
    for d in DEFAULT_CLEAN_DIRS:
        flist = files.get(d, [])
        print(f"  {d}/ : {len(flist)} 文件")
        for name, size, _ in flist[:3]:
            print(f"    - {name} ({size} B)")
        if len(flist) > 3:
            print(f"    ... 共 {len(flist)} 个文件")

    print(f"\n默认不清理:")
    print(f"  vault/       — 长期个人资料库")
    print(f"  final_outputs/ — 最终导出文件（默认保留）")
    print(f"  app/ skills/ docs/ — 核心代码和文档")

    # 生成报告
    with open(PREVIEW_REPORT, "w", encoding="utf-8") as f:
        f.write(f"# SafeFill-Cleaner 预览报告\n\n时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
        f.write(f"## 将清理 {total} 个文件\n\n")
        for d in DEFAULT_CLEAN_DIRS:
            flist = files.get(d, [])
            f.write(f"### {d}/ ({len(flist)} 文件)\n")
            for name, size, _ in flist:
                f.write(f"- {name} ({size} B)\n")
            f.write("\n")
        f.write("## 安全\n- 未联网\n- 未调用 API\n- vault 不会清理\n- final_outputs 默认不清理\n")
    print(f"\n  报告: {PREVIEW_REPORT}")
    print(f"\n  执行清理: python cleaner.py clean --confirm CLEAN")
    print(f"{'='*50}\n")

def cmd_clean(include_final: bool, confirm: str):
    """执行清理。"""
    if confirm != "CLEAN":
        print("\n[STOP] 必须使用 --confirm CLEAN 确认清理操作。\n")
        sys.exit(1)

    dirs = DEFAULT_CLEAN_DIRS.copy()
    if include_final:
        dirs += OPTIONAL_CLEAN_DIRS

    # 先预览
    files = collect_files(dirs)
    total = sum(len(v) for v in files.values())
    print(f"\n将清理 {total} 个文件，开始执行...")

    deleted = 0
    skipped = 0
    for d in dirs:
        dp = PROJECT / d
        if not dp.exists():
            continue
        for f in dp.iterdir():
            if not f.is_file():
                skipped += 1
                continue
            try:
                # 安全检查：必须在项目根下
                f.resolve().relative_to(PROJECT.resolve())
                f.unlink()
                deleted += 1
            except Exception as e:
                print(f"  跳过 {d}/{f.name}: {e}")
                skipped += 1

    print(f"\n  删除: {deleted} | 跳过: {skipped}")

    if include_final:
        print(f"  final_outputs: 已清理")
    else:
        print(f"  final_outputs: 保留（使用 --include-final 可清理）")
    print(f"  vault: 保留（本工具不清理 vault）")

    # 报告
    with open(CLEAN_REPORT, "w", encoding="utf-8") as f:
        f.write(f"# SafeFill-Cleaner 清理报告\n\n时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
        f.write(f"删除: {deleted}\n跳过: {skipped}\n")
        f.write(f"final_outputs: {'已清理' if include_final else '保留'}\n")
        f.write(f"vault: 保留\n\n")
        f.write("## 安全\n- 未联网\n- 未调用 API\n- 未删除 vault\n- 未删除核心脚本\n")
    print(f"  报告: {CLEAN_REPORT}\n")

def main():
    print("\nSafeFill-Cleaner — 隐私清理")
    print("默认不清理 vault 和 final_outputs | 需确认才删除\n")
    args = sys.argv[1:]
    mode = args[0] if args else ""
    include_final = "--include-final" in args
    confirm = ""
    for i, a in enumerate(args):
        if a == "--confirm" and i + 1 < len(args):
            confirm = args[i + 1]

    if mode == "preview":
        cmd_preview()
    elif mode == "clean":
        cmd_clean(include_final, confirm)
    else:
        print(f"\n{'='*55}")
        print(f"  SafeFill-Cleaner 隐私清理工具")
        print(f"{'='*55}")
        print(f"\n这个工具可以帮助你清理旧表、草稿、网页预览、检查结果和日志，")
        print(f"减少隐私残留。")
        print(f"\n默认安全规则：")
        print(f"  - 不清理 vault")
        print(f"  - 不默认清理 final_outputs")
        print(f"  - 不联网")
        print(f"  - 不调用 API")
        print(f"  - 不会在没有确认时删除文件")
        print(f"\n可用命令：")
        print(f"  1. 预览可清理内容：")
        print(f"     python D:\\SafeFill\\app\\cleaner.py preview")
        print(f"\n  2. 执行清理：")
        print(f"     python D:\\SafeFill\\app\\cleaner.py clean --confirm CLEAN")
        print(f"\n  3. 连最终输出也一起清理：")
        print(f"     python D:\\SafeFill\\app\\cleaner.py clean --include-final --confirm CLEAN")
        print(f"\n提示：建议先运行 preview，确认无误后再 clean。")
        print(f"{'='*55}\n")

if __name__ == "__main__":
    main()
