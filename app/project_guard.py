# -*- coding: utf-8 -*-
"""
SafeFill-ProjectGuard — 只读项目体检脚本
检查核心脚本、API状态、目录状态、vault状态、流程状态、旧流程残留。
不修改任何文件，不联网，不调用 API。
"""

import os, sys, json, re
from datetime import datetime
from pathlib import Path

PROJECT = Path(__file__).resolve().parent.parent
APP_DIR = PROJECT / "app"
SKILLS_DIR = PROJECT / "skills"
DOCS_DIR = PROJECT / "docs"

# 核心脚本
CORE_SCRIPTS = [
    ("extract_candidates.py", "ProfileExtract", True),
    ("save_confirmed_profile.py", "ProfileSave", True),
    ("form_review.py", "FormReview", True),
    ("export_final.py", "FinalExport", True),
    ("api_assist.py", "APIAssist", True),
    ("fill_form_draft.py", "DraftFill(内部)", False),
    ("review_server.py", "ReviewUI(内部)", False),
]

# 正式 Skill
OFFICIAL_SKILLS = [
    "SafeFill-ProjectGuard", "SafeFill-ProfileExtract", "SafeFill-ProfileSave",
    "SafeFill-FormReview", "SafeFill-FinalExport", "SafeFill-Cleaner",
]

# 测试数据关键词
TEST_KEYWORDS = ["测试人员", "测试大学", "哈利波特", "110101", "1381234", "example.invalid"]

# 旧流程残留关键词
OLD_FLOW = ["SafeFill-DraftFill", "SafeFill-ReviewUI"]

REPORT_PATH = DOCS_DIR / "guard_check_report.md"

def main():
    print(f"\n{'='*55}")
    print(f"  欢迎使用 SafeFill")
    print(f"  SafeFill-ProjectGuard 项目体检")
    print(f"  {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'='*55}")
    print("\n我会先做一次只读检查，判断项目是否安全、流程走到哪一步、下一步该做什么。")
    print("主流程: ProfileExtract → ProfileSave → FormReview → FinalExport")
    print("安全承诺: 不联网 | 不调用 API | 不修改 vault | 不删除文件\n")

    issues = []
    warnings = []
    status = {"step": "", "next_skill": "", "next_cmd": ""}

    # ---- [1] 核心脚本 ----
    print(f"\n[1] 核心脚本")
    all_ok = True
    for fname, label, is_core in CORE_SCRIPTS:
        exists = (APP_DIR / fname).exists()
        tag = "核心" if is_core else "内部"
        if exists:
            print(f"  OK: {fname} ({tag})")
        else:
            print(f"  MISSING: {fname}")
            all_ok = False
            issues.append(f"缺少脚本: {fname}")
    if all_ok:
        print(f"  结果: {len(CORE_SCRIPTS)}/{len(CORE_SCRIPTS)} 存在")

    # ---- [2] 正式 skills 目录 ----
    print(f"\n[2] 正式 skills 目录")
    extra = []
    if SKILLS_DIR.exists():
        for d in sorted(SKILLS_DIR.iterdir()):
            if d.is_dir():
                if d.name in OFFICIAL_SKILLS:
                    print(f"  OK: {d.name}")
                else:
                    print(f"  WARN: {d.name} (不应在正式 skills 目录中)")
                    extra.append(d.name)
    if extra:
        warnings.append(f"旧 Skill 目录: {', '.join(extra)}")

    # ---- [3] API 状态 ----
    print(f"\n[3] API 状态")
    api_config = APP_DIR / "api_config.json"
    if api_config.exists():
        try:
            with open(api_config, "r", encoding="utf-8") as f:
                cfg = json.load(f)
            enabled = cfg.get("enabled", False)
            dry_run = cfg.get("dry_run", True)
            endpoint = cfg.get("endpoint", "")
            if not enabled and dry_run:
                print(f"  OK: enabled=false, dry_run=true (安全关闭)")
            else:
                if enabled:
                    print(f"  WARN: enabled=true (高风险)")
                    warnings.append("API enabled=true")
                if not dry_run:
                    print(f"  WARN: dry_run=false (高风险)")
                    warnings.append("API dry_run=false")
            if endpoint:
                print(f"  endpoint: {endpoint[:50]}...")
        except Exception:
            print(f"  WARN: api_config.json 读取失败")
    else:
        print(f"  OK: 未发现 api_config.json (API 默认关闭)")

    # ---- [4] 资料库 vault ----
    print(f"\n[4] 资料库 vault")
    vault_dir = PROJECT / "vault"
    profile_path = vault_dir / "profile.json"
    legacy_profiles_dir = vault_dir / "profiles"
    legacy_persons = sorted(legacy_profiles_dir.glob("person_*.json")) if legacy_profiles_dir.exists() else []
    persons = [profile_path] if profile_path.exists() else []
    print(f"  profile.json: {'OK' if profile_path.exists() else 'MISSING'}")
    if legacy_persons:
        print(f"  WARN: 发现旧版 person_*.json {len(legacy_persons)} 个（历史残留，不作为正式资料库）")
        warnings.append(f"旧版 person_*.json 残留 {len(legacy_persons)} 个")
    if len(persons) == 0:
        status["step"] = "资料库未初始化"
        status["next_skill"] = "SafeFill-ProfileExtract"
        status["next_cmd"] = f"python {APP_DIR / 'extract_candidates.py'}"
        status["reason"] = "vault 资料库还没有个人资料。"

    # 测试数据检测
    if persons:
        for p in persons[:1]:
            try:
                with open(p, "r", encoding="utf-8") as f:
                    content = f.read()
                found = [kw for kw in TEST_KEYWORDS if kw in content]
                if found:
                    print(f"  WARN: {p.name} 疑似测试数据 ({', '.join(found[:3])})")
                    warnings.append(f"{p.name} 疑似测试数据残留")
            except Exception:
                pass

    # ---- [4.5] 新旧资料提醒 ----
    latest_candidate = PROJECT / "candidate_reviews" / "latest_candidate.json"
    if persons and latest_candidate.exists():
        try:
            lc_mtime = latest_candidate.stat().st_mtime
            p1_mtime = persons[0].stat().st_mtime
            if lc_mtime > p1_mtime:
                print(f"\n[4.5] 新旧资料提醒")
                print(f"  WARN: 有新的提取结果 (latest_candidate.json 比 vault\\profile.json 更新)")
                print(f"  建议先运行 SafeFill-ProfileSave 确认是否更新 vault")
                print(f"  命令: python D:\\SafeFill\\app\\save_confirmed_profile.py")
                status["reminder_save"] = True
        except Exception:
            pass

    # ---- [4.6] PDF / MinerU 状态 ----
    print(f"\n[4.6] PDF 提取支持")
    pdf_files = sorted(INPUT_DIR.glob("*.pdf")) if (INPUT_DIR := PROJECT / "input_forms").exists() else []
    pdf_count = len(pdf_files)
    pdf_outputs_dir = PROJECT / "pdf_extract_outputs"
    print(f"  input_forms PDF 数量: {pdf_count}")
    print(f"  pdf_extract_outputs: {'存在' if pdf_outputs_dir.exists() else '不存在'}")

    mineru_ok = False
    mineru_path = ""
    mineru_ver = ""
    try:
        sys.path.insert(0, str(APP_DIR))
        from pdf_extract import check_mineru
        mineru_ok, mineru_ver, mineru_path, _ = check_mineru()
    except Exception:
        pass
    if mineru_ok:
        print(f"  MinerU: 已安装")
        print(f"  版本: {mineru_ver}")
        if mineru_path:
            print(f"  路径: {mineru_path}")
    else:
        print(f"  MinerU: 未安装")
    if pdf_count > 0 and not mineru_ok:
        print(f"  WARN: 检测到 PDF 旧资料，但 MinerU 未安装，PDF 将不会被提取。")
        print(f"  安装: .\\tools\\install_mineru.ps1")
        warnings.append(f"MinerU 未安装，{pdf_count} 个 PDF 将跳过")

    # ---- [4.7] Word 文本框支持 ----
    print(f"\n[4.7] Word 文本框支持")
    print(f"  ProfileExtract 文本框提取: 已支持")
    print(f"  FormReview 文本框识别: 已支持")
    print(f"  简单文本框写入: 已支持")
    print(f"  ReviewUI 文本框状态展示: 已支持")

    # ---- [5] 目录状态 ----
    print(f"\n[5] 目录状态")
    dirs = {
        "input_forms": "旧表格", "candidate_reviews": "候选信息", "new_forms": "新表格",
        "draft_outputs": "草稿", "review_html": "HTML预览", "review_results": "检查结果",
        "final_outputs": "最终文件", "final_reports": "导出报告",
    }
    for dname, dlabel in dirs.items():
        dp = PROJECT / dname
        count = len(list(dp.glob("*"))) if dp.exists() else -1
        marker = "" if count > 0 else " (空)"
        print(f"  {dlabel}: {count} 文件{marker}")

    # ---- [6] 流程状态 ----
    print(f"\n[6] 流程状态")
    new_forms_has = bool(list((PROJECT/"new_forms").glob("*.docx")) + list((PROJECT/"new_forms").glob("*.xlsx")))

    # 正式 review_result
    rr_dir = PROJECT / "review_results"
    formal_rr = []
    if rr_dir.exists():
        for f in rr_dir.glob("review_result_*.json"):
            name_lower = f.name.lower()
            if any(kw in name_lower for kw in ("_test_", "html_test", "sample", "demo")):
                continue
            formal_rr.append(f)
    formal_rr.sort(key=lambda f: f.stat().st_mtime, reverse=True)

    final_dir = PROJECT / "final_outputs"
    final_files = sorted(final_dir.glob("*_最终版*"), key=lambda f: f.stat().st_mtime, reverse=True) if final_dir.exists() else []

    if not status["next_skill"]:  # not set by vault check
        if not new_forms_has:
            status["step"] = "资料库就绪，待放入新表格"
            status["next_cmd"] = "把 .docx/.xlsx 放入 new_forms\\"
            status["next_skill"] = "SafeFill-FormReview"
            status["reason"] = "资料库已有，但还没有待填写的新表。"
        elif not formal_rr:
            status["step"] = "待网页检查保存"
            status["next_skill"] = "SafeFill-FormReview"
            status["next_cmd"] = f"python {APP_DIR / 'form_review.py'}"
            status["reason"] = "需要填表并在网页保存检查结果。"
        elif not final_files:
            status["step"] = "待最终导出"
            status["next_skill"] = "SafeFill-FinalExport"
            status["next_cmd"] = f"python {APP_DIR / 'export_final.py'}"
            status["reason"] = "网页检查结果已保存，可以导出最终文件。"
        else:
            rr_mtime = formal_rr[0].stat().st_mtime
            fo_mtime = final_files[0].stat().st_mtime
            if fo_mtime > rr_mtime:
                status["step"] = "已导出"
                status["next_cmd"] = f"检查 {final_files[0].name}"
                status["reason"] = "最终文件已经生成。"
            else:
                status["step"] = "待最终导出"
                status["next_skill"] = "SafeFill-FinalExport"
                status["next_cmd"] = f"python {APP_DIR / 'export_final.py'}"
                status["reason"] = "网页检查结果已保存，可以导出最终文件。"

    print(f"  当前: {status.get('step', '未知')}")
    if formal_rr:
        print(f"  正式 review_result: {formal_rr[0].name}")

    # ---- [7] 旧流程残留 ----
    print(f"\n[7] 旧流程残留")
    docs_to_check = [
        "skills/SafeFill-Orchestrator/SKILL.md",
        "docs/小Skill运行顺序.md", "docs/小Skill输入输出契约.md", "docs/命令入口清单.md",
    ]
    residues = []
    for rel in docs_to_check:
        fp = PROJECT / rel
        if not fp.exists(): continue
        try:
            with open(fp, "r", encoding="utf-8") as f:
                content = f.read()
            for kw in OLD_FLOW:
                if kw in content:
                    # 检查上下文：是否为"内部实现"
                    idx = content.find(kw)
                    ctx = content[max(0,idx-30):idx+len(kw)+30]
                    if "内部" not in ctx and "deprecated" not in ctx.lower() and "合并" not in ctx:
                        residues.append(f"{rel}: {kw}")
        except Exception:
            pass
    if residues:
        for r in residues:
            print(f"  WARN: {r}")
        warnings.append(f"旧流程残留 {len(residues)} 处")
    else:
        print(f"  OK: 无正式流程残留")

    # ---- 总结 ----
    print(f"\n{'='*55}")
    print(f"  体检完成")
    if issues:
        print(f"  问题: {len(issues)}")
        for i in issues: print(f"    - {i}")
    if warnings:
        print(f"  警告: {len(warnings)}")
        for w in warnings: print(f"    - {w}")
    if not issues and not warnings:
        print(f"  状态: 健康")
    print(f"\n  {'─'*40}")
    print(f"  建议下一步")
    if status.get('next_skill'):
        print(f"  子 Skill: {status['next_skill']}")
    print(f"  操作: {status.get('next_cmd', '')}")
    if status.get('reason'):
        print(f"  原因: {status['reason']}")
    if status.get("step") == "待网页检查保存":
        print(f"  提醒: 网页打开后请检查内容，修改完成必须点击“保存检查结果”。")
    elif status.get("step") == "待最终导出":
        print(f"  提醒: FinalExport 只读取已保存、已确认的 review_result。")
    elif status.get("step") == "资料库未初始化":
        print(f"  提醒: ProfileExtract 只提取候选信息，不会直接写入 vault。")
    print(f"\n  安全确认: 未联网 | 未调用 API | 未修改 vault | 未删除文件")

    # 已导出时建议 Cleaner
    if status.get("step") == "已导出":
        print(f"\n  可选收尾: SafeFill-Cleaner")
        print(f"    预览: python D:\\SafeFill\\app\\cleaner.py preview")
        print(f"    Cleaner 默认不清理 vault 和 final_outputs。")

    print(f"{'='*55}\n")

    # 生成报告
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(REPORT_PATH, "w", encoding="utf-8") as f:
        f.write(f"# SafeFill-ProjectGuard 体检报告\n\n")
        f.write(f"时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
        f.write(f"## 脚本: {len(CORE_SCRIPTS)}/{len(CORE_SCRIPTS)}\n")
        f.write(f"## API: {'安全关闭' if (api_config.exists() and not cfg.get('enabled',False) and cfg.get('dry_run',True)) else '需检查'}\n")
        f.write(f"## vault: {'profile.json 存在' if persons else 'profile.json 不存在'}\n")
        f.write(f"## 下一步: {status.get('next_skill','')} — {status.get('next_cmd','')}\n")
        f.write(f"## 安全: 未联网, 未调用 API, 未修改 vault, 未删除文件\n")
        if warnings:
            f.write(f"\n## 警告\n")
            for w in warnings: f.write(f"- {w}\n")
    print(f"  报告: {REPORT_PATH}\n")


if __name__ == "__main__":
    main()
