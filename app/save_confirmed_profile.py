# -*- coding: utf-8 -*-
"""
SafeFill-ProfileSave v2
功能：读取 confirmed_profile.json，检测重复后保存到 vault，成功后自动归档。
安全约束：不覆盖已有 profile，不保存空/未确认字段，重复时不新增。
"""

import os
import sys
import json
import shutil
from datetime import datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
VAULT_DIR = PROJECT_ROOT / "vault"
VAULT_PROFILE = VAULT_DIR / "profile.json"
TEMPLATE_DIR = PROJECT_ROOT / "vault" / "profiles"
CANDIDATE_DIR = PROJECT_ROOT / "candidate_reviews"
SAVED_DIR = CANDIDATE_DIR / "saved_confirmed_profiles"
LOGS_DIR = PROJECT_ROOT / "logs"
TEMPLATE_PATH = TEMPLATE_DIR / "profile_template.json"

ALLOWED_FIELDS = {
    "name", "gender", "birth_date", "id_number", "phone", "email",
    "organization", "department", "title", "education", "degree",
    "major", "research_area", "address", "photo_path",
    "project_experience", "biography",
}

SENSITIVE_KEYS = {"id_number", "phone", "address", "photo_path"}

def write_log(msg: str):
    LOGS_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with open(LOGS_DIR / "save_profile.log", "a", encoding="utf-8") as f:
        f.write(f"[{ts}] {msg}\n")
    print(f"[LOG] {msg}")

# ------------------------------------------------------------
# 数据加载
# ------------------------------------------------------------
def load_confirmed_data(path: Path) -> tuple:
    """返回 (to_save_dict, issues_list)。to_save 为空时保存失败。"""
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except json.JSONDecodeError as e:
        return {}, [f"JSON 格式错误: {e}"]

    candidates = data.get("candidates", None)
    if candidates is None:
        # 兼容简单格式：直接放字段
        candidates = {k: v for k, v in data.items() if not k.startswith("_")}

    if not candidates:
        return {}, ["未找到任何候选字段"]

    to_save = {}
    issues = []

    for key, value in candidates.items():
        if key not in ALLOWED_FIELDS:
            issues.append(f"未知字段 '{key}'，跳过")
            write_log(f"INFO: 跳过未知字段: {key}")
            continue

        if isinstance(value, dict):
            actual = value.get("value", "")
            confirmed = value.get("confirmed", False)
        else:
            actual = value
            confirmed = True

        if not actual or (isinstance(actual, str) and not actual.strip()):
            issues.append(f"字段 '{key}' 值为空，跳过")
            write_log(f"INFO: 跳过空字段: {key}")
            continue

        if not confirmed:
            issues.append(f"字段 '{key}' 未确认，跳过")
            write_log(f"INFO: 跳过未确认字段: {key}")
            continue

        to_save[key] = actual

    custom_fields = data.get("custom_fields", {})
    if isinstance(custom_fields, dict):
        for key, value in custom_fields.items():
            if isinstance(value, dict):
                actual = value.get("value", "")
                confirmed = value.get("confirmed", False)
            else:
                actual = value
                confirmed = True

            if not actual or (isinstance(actual, str) and not actual.strip()):
                issues.append(f"自定义字段 '{key}' 值为空，跳过")
                write_log(f"INFO: 跳过空自定义字段: {key}")
                continue

            if not confirmed:
                issues.append(f"自定义字段 '{key}' 未确认，跳过")
                write_log(f"INFO: 跳过未确认自定义字段: {key}")
                continue

            to_save[key] = actual

    if not to_save:
        issues.append("没有可保存的字段")
    return to_save, issues

# ------------------------------------------------------------
# 重复检测
# ------------------------------------------------------------
def load_existing_profiles() -> dict:
    """加载 profile.json 的字段值。返回 {filename: {field: value}}。"""
    profiles = {}
    if VAULT_PROFILE.exists():
        try:
            with open(VAULT_PROFILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            fields = {}
            for k, v in data.items():
                if k.startswith("_"): continue
                if isinstance(v, dict):
                    fields[k] = v.get("value", "")
                elif isinstance(v, list):
                    fields[k] = str(v) if v else ""
                else:
                    fields[k] = v
            profiles["profile.json"] = fields
        except Exception:
            pass
    return profiles

def check_duplicate(to_save: dict, existing: dict) -> str | None:
    """
    检测 to_save 是否与某个已有 profile 重复。
    返回重复的 person 文件名，或 None。
    """
    for fname, fields in existing.items():
        core_match = 0
        total = len(to_save)
        for key, val in to_save.items():
            if key in fields and str(fields[key]).strip() == str(val).strip():
                core_match += 1
        # 所有字段都匹配 → 完全重复
        if core_match == total and total > 0:
            return fname
        # name 相同 + major 相同 + department 相同
        if (to_save.get("name") and fields.get("name") == to_save["name"]
                and to_save.get("major") and fields.get("major") == to_save["major"]
                and to_save.get("department") and fields.get("department") == to_save["department"]):
            return fname
        # name 相同 + research_area 相同
        if (to_save.get("name") and fields.get("name") == to_save["name"]
                and to_save.get("research_area") and fields.get("research_area") == to_save["research_area"]):
            return fname
    return None


def check_name_conflict(to_save: dict, existing: dict) -> tuple:
    """
    检测新资料姓名是否与已有 profile 不同。
    返回 (has_conflict, existing_name, new_name)。
    """
    new_name = to_save.get("name", "").strip()
    if not new_name:
        return (False, "", "")
    for fname, fields in existing.items():
        existing_name = (fields.get("name") or "").strip()
        if existing_name and existing_name != new_name:
            return (True, existing_name, new_name)
    return (False, "", "")


def find_latest_candidate_template() -> Path | None:
    """Return the latest confirmed profile template pointed to by latest_candidate.json."""
    latest_path = CANDIDATE_DIR / "latest_candidate.json"
    if not latest_path.exists():
        return None
    try:
        with open(latest_path, "r", encoding="utf-8") as f:
            latest = json.load(f)
    except Exception as e:
        write_log(f"WARN: latest_candidate.json 读取失败: {e}")
        return None

    template_value = latest.get("confirmed_profile_template", "")
    if not template_value:
        return None

    template_path = Path(template_value)
    if not template_path.is_absolute():
        template_path = CANDIDATE_DIR / template_path.name

    try:
        resolved = template_path.resolve()
        resolved.relative_to(CANDIDATE_DIR.resolve())
    except ValueError:
        write_log("SECURITY: latest_candidate 指向 candidate_reviews 外部路径，已拒绝")
        return None

    return resolved if resolved.exists() else None


def select_profile_source() -> tuple[Path | None, str]:
    """
    Pick the profile source for saving.
    Prefer user-created confirmed_profile.json when present, otherwise use latest candidate template.
    """
    confirmed_path = CANDIDATE_DIR / "confirmed_profile.json"
    if confirmed_path.exists():
        return confirmed_path, "confirmed_profile.json"

    latest_template = find_latest_candidate_template()
    if latest_template:
        return latest_template, latest_template.name

    return None, ""


def print_profile_summary(title: str, data: dict):
    """Print a concise local-only summary for user confirmation."""
    print(f"\n{title}")
    for key in [
        "name", "gender", "phone", "email", "organization", "department",
        "title", "education", "degree", "major", "research_area", "address",
    ]:
        value = str(data.get(key, "")).strip()
        if value:
            print(f"  {VAULT_LABELS.get(key, key):8s}: {value}")
    custom = data.get("custom_fields")
    if isinstance(custom, dict) and custom:
        print("  自定义字段:")
        for k, v in custom.items():
            if isinstance(v, dict):
                value = v.get("value", "")
            else:
                value = v
            if value:
                print(f"    {k}: {value}")


def confirm_initial_save(to_save: dict, source_label: str) -> bool:
    """Ask whether to create vault/profile.json from latest extraction."""
    print("\n当前 vault 还没有 profile.json。")
    print("SafeFill 初版只维护一个个人信息库：vault\\profile.json")
    print(f"本次将使用最新提取结果：{source_label}")
    print_profile_summary("最新提取摘要：", to_save)
    print("\n是否保存为 vault\\profile.json？")
    print("  1. 保存")
    print("  2. 停止，不保存")
    try:
        choice = input("  请输入 1/2 [默认 2]: ").strip()
    except (EOFError, KeyboardInterrupt):
        choice = "2"
    return choice == "1"


# ------------------------------------------------------------
# 资料对比 + 交互菜单
# ------------------------------------------------------------
def diff_and_menu(to_save: dict):
    """
    当 vault 已有资料时，全面对比新旧资料，用菜单让用户选择处理方式。
    返回 True 表示用户做了选择（可能修改了 vault），False 表示停止。
    """
    existing = load_existing_profiles()
    if not existing:
        return True  # 没有已有资料，直接保存

    # 只取 profile 作为当前资料
    p1_fields = list(existing.values())[0] if existing else {}
    p1_name = list(existing.keys())[0] if existing else "?"

    # 分类
    same = {}
    can_fill = {}
    conflicts = {}
    new_customs = {}

    for k, new_val in to_save.items():
        old_val = (p1_fields.get(k) or "").strip() if k in ALLOWED_FIELDS else ""
        new_str = str(new_val).strip()
        if k not in ALLOWED_FIELDS:
            # 自定义字段
            cf_data = {}
            if VAULT_PROFILE.exists():
                with open(VAULT_PROFILE, "r", encoding="utf-8") as _f:
                    cf_data = json.load(_f).get("custom_fields", {})
            old_c = str(cf_data.get(k, {}).get("value", "")) if isinstance(cf_data.get(k, {}), dict) else ""
            if old_c == new_str:
                same[k] = (old_c, new_str)
            elif not old_c:
                new_customs[k] = ("(空)", new_str)
            else:
                conflicts[k] = (old_c, new_str)
        elif not old_val:
            can_fill[k] = ("(空)", new_str)
        elif old_val == new_str:
            same[k] = (old_val, new_str)
        else:
            conflicts[k] = (old_val, new_str)

    total_diffs = len(can_fill) + len(conflicts) + len(new_customs)
    if total_diffs == 0:
        print("  所有字段与 vault 一致，无需处理。")
        return True

    # 展示差异
    print(f"\n{'='*50}")
    print(f"  检测到 vault 已有个人资料，发现 {total_diffs} 个差异字段")
    print(f"{'='*50}")
    print(f"\n当前 vault [{p1_name}]:")
    for k in VAULT_DISPLAY_ORDER:
        v = p1_fields.get(k, "") if isinstance(p1_fields.get(k, ""), str) else str(p1_fields.get(k, ""))
        if v: print(f"  {VAULT_LABELS.get(k,k):8s}: {v[:50]}")
    print(f"\n新提取资料:")
    for k in VAULT_DISPLAY_ORDER:
        if k in to_save:
            print(f"  {VAULT_LABELS.get(k,k):8s}: {str(to_save[k])[:50]}")

    if conflicts:
        print(f"\n[冲突 {len(conflicts)} 个] (vault → 新提取):")
        for i, (k, (old, new)) in enumerate(conflicts.items(), 1):
            label = VAULT_LABELS.get(k, k)
            print(f"  [{i}] {label}: {old[:30]} → {new[:30]}")
    if can_fill:
        print(f"\n[可补充 {len(can_fill)} 个] (vault 为空):")
        for k, (old, new) in can_fill.items():
            print(f"  {VAULT_LABELS.get(k,k)}: {new[:40]}")
    if new_customs:
        print(f"\n[新自定义字段 {len(new_customs)} 个]:")
        for k, (old, new) in new_customs.items():
            print(f"  {k}: {new[:40]}")

    # 姓名不同 → 提示
    name_old = (p1_fields.get("name") or "").strip()
    name_new = str(to_save.get("name", "")).strip()
    if name_old and name_new and name_old != name_new:
        print(f"\n姓名不同 ({name_old} vs {name_new})，SafeFill 初版只支持一个个人资料库 profile.json。")

    print(f"\n请选择处理方式:")
    print(f"  1. 用新提取资料替换当前 profile.json（会先备份）")
    print(f"  2. 只补充空字段，不覆盖已有字段")
    print(f"  3. 逐字段确认")
    print(f"  4. 停止，不保存")
    print(f"")

    try:
        choice = input("  请输入 1/2/3/4 [默认 4]: ").strip()
    except (EOFError, KeyboardInterrupt):
        choice = "4"

    if not choice or choice not in "1234":
        choice = "4"

    target = VAULT_DIR / p1_name

    if choice == "1":
        # 覆盖
        print(f"\n将用新提取资料替换 {p1_name}。旧资料会先备份。")
        try:
            confirm = input("  确认替换？输入 REPLACE 确认: ").strip()
        except (EOFError, KeyboardInterrupt):
            confirm = ""
        if confirm != "REPLACE":
            print("  已取消。")
            return False
        BACKUP_DIR_ABS = VAULT_DIR / "backups"
        BACKUP_DIR_ABS.mkdir(parents=True, exist_ok=True)
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        bk = BACKUP_DIR_ABS / f"profile_backup_{ts}.json"
        shutil.copy2(str(target), str(bk))
        write_log(f"INFO: 覆盖前备份: {bk.name}")
        # 直接写入 profile
        template = {}
        if TEMPLATE_PATH.exists():
            with open(TEMPLATE_PATH, "r", encoding="utf-8") as f:
                template = json.load(f)
        save_data = {"_profile_id": "profile", "_创建时间": datetime.now().strftime("%Y-%m-%d %H:%M:%S"), "_来源": "overwrite"}
        for key in ALLOWED_FIELDS:
            if key in template:
                if isinstance(template[key], dict):
                    save_data[key] = dict(template[key])
                    save_data[key]["value"] = to_save.get(key, "")
                else:
                    save_data[key] = to_save.get(key, template[key])
            else:
                save_data[key] = to_save.get(key, "")
        for key in to_save:
            if key in ALLOWED_FIELDS:
                continue
            if "custom_fields" not in save_data:
                save_data["custom_fields"] = {}
            save_data["custom_fields"][key] = {"value": str(to_save[key]), "confirmed": True, "source": "overwrite", "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
        with open(target, "w", encoding="utf-8") as f:
            json.dump(save_data, f, ensure_ascii=False, indent=2)
        print(f"\n[OK] {p1_name} 已更新。备份: {bk.name}")
        write_log(f"INFO: {p1_name} 已覆盖，备份: {bk.name}")
        show_vault_merged_profile()
        return False

    elif choice == "2":
        # 只补充空字段
        filled = 0
        for k, (old, new) in can_fill.items():
            # update profile
            with open(target, "r", encoding="utf-8") as f:
                data = json.load(f)
            if k in data and isinstance(data[k], dict):
                data[k]["value"] = new
            else:
                data[k] = new
            with open(target, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            filled += 1
            write_log(f"INFO: 补充空字段: {k}")
        print(f"\n[OK] 已补充 {filled} 个空字段。冲突字段未修改。")
        show_vault_merged_profile()
        return False

    elif choice == "3":
        # 逐字段处理
        all_items = list(conflicts.items()) + list(can_fill.items())
        for i, (k, (old, new)) in enumerate(all_items, 1):
            label = VAULT_LABELS.get(k, k)
            try:
                c = input(f"\n  [{label}] vault={old[:30]} new={new[:30]} → 覆盖? (y/n/skip): ").strip().lower()
            except (EOFError, KeyboardInterrupt):
                c = "n"
            if c in ("y", "yes"):
                with open(target, "r", encoding="utf-8") as f:
                    data = json.load(f)
                if k in data and isinstance(data[k], dict):
                    data[k]["value"] = new
                else:
                    data[k] = new
                with open(target, "w", encoding="utf-8") as f:
                    json.dump(data, f, ensure_ascii=False, indent=2)
                write_log(f"INFO: 逐字段覆盖: {k}")
                print(f"    已覆盖 {label}")
            elif c == "skip":
                print(f"    已跳过 {label}")
            else:
                print(f"    保留原值 {label}")
        show_vault_merged_profile()
        return False

    else:  # choice == "4"
        print("\n已停止，vault 未修改。")
        write_log("INFO: 用户选择停止，vault 未修改")
        return False


# ------------------------------------------------------------
# --choice 非交互模式：检测冲突并输出 JSON（供 ControlCenter 使用）
# ------------------------------------------------------------
def detect_and_output_json(to_save: dict):
    """计算新旧差异并以 JSON 输出到 stdout，供 ControlCenter 网页弹窗使用。"""
    existing = load_existing_profiles()
    if not existing:
        print(json.dumps({"status": "empty", "vault_exists": False}, ensure_ascii=False))
        return

    p1_fields = list(existing.values())[0] if existing else {}
    p1_name = list(existing.keys())[0] if existing else "?"

    conflicts_list = []
    can_fill_list = []
    new_customs_list = []
    same_count = 0

    for k, new_val in to_save.items():
        old_val = (p1_fields.get(k) or "").strip() if k in ALLOWED_FIELDS else ""
        new_str = str(new_val).strip()
        label = VAULT_LABELS.get(k, k)

        if k not in ALLOWED_FIELDS:
            cf_data = {}
            if VAULT_PROFILE.exists():
                with open(VAULT_PROFILE, "r", encoding="utf-8") as _f:
                    cf_data = json.load(_f).get("custom_fields", {})
            old_c = str(cf_data.get(k, {}).get("value", "")) if isinstance(cf_data.get(k, {}), dict) else ""
            if old_c == new_str:
                same_count += 1
            elif not old_c:
                new_customs_list.append({"field": k, "label": label, "value": new_str})
            else:
                conflicts_list.append({"field": k, "label": label, "old": old_c[:60], "new": new_str[:60]})
        elif not old_val:
            can_fill_list.append({"field": k, "label": label, "value": new_str[:60]})
        elif old_val == new_str:
            same_count += 1
        else:
            conflicts_list.append({"field": k, "label": label, "old": old_val[:60], "new": new_str[:60]})

    total_diffs = len(conflicts_list) + len(can_fill_list) + len(new_customs_list)
    name_old = (p1_fields.get("name") or "").strip()
    name_new = str(to_save.get("name", "")).strip()
    has_name_conflict = bool(name_old and name_new and name_old != name_new)

    result = {
        "status": "conflict" if total_diffs > 0 else "same",
        "vault_exists": True,
        "existing_name": name_old,
        "new_name": name_new,
        "has_name_conflict": has_name_conflict,
        "total_diffs": total_diffs,
        "conflicts": conflicts_list,
        "can_fill": can_fill_list,
        "new_customs": new_customs_list,
        "same_count": same_count,
    }
    print(json.dumps(result, ensure_ascii=False))


def execute_replace(to_save: dict, p1_fields: dict):
    """非交互式执行替换操作（--choice replace）。"""
    p1_name = "profile.json"
    target = VAULT_DIR / p1_name

    # 备份
    BACKUP_DIR_ABS = VAULT_DIR / "backups"
    BACKUP_DIR_ABS.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    bk = BACKUP_DIR_ABS / f"profile_backup_{ts}.json"
    shutil.copy2(str(target), str(bk))
    write_log(f"INFO: --choice replace 备份: {bk.name}")

    # 写入
    template = {}
    if TEMPLATE_PATH.exists():
        with open(TEMPLATE_PATH, "r", encoding="utf-8") as f:
            template = json.load(f)
    save_data = {"_profile_id": "profile", "_创建时间": datetime.now().strftime("%Y-%m-%d %H:%M:%S"), "_来源": "replace_by_control_center"}
    for key in ALLOWED_FIELDS:
        if key in template:
            if isinstance(template[key], dict):
                save_data[key] = dict(template[key])
                save_data[key]["value"] = to_save.get(key, "")
            else:
                save_data[key] = to_save.get(key, template[key])
        else:
            save_data[key] = to_save.get(key, "")
    for key in to_save:
        if key in ALLOWED_FIELDS:
            continue
        if "custom_fields" not in save_data:
            save_data["custom_fields"] = {}
        save_data["custom_fields"][key] = {"value": str(to_save[key]), "confirmed": True, "source": "replace_by_control_center", "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
    with open(target, "w", encoding="utf-8") as f:
        json.dump(save_data, f, ensure_ascii=False, indent=2)
    name_new = str(to_save.get("name", ""))
    print(f"\n[OK] profile.json 已替换为 {name_new}。备份: {bk.name}")
    write_log(f"INFO: --choice replace 完成，备份: {bk.name}")


def execute_fill_empty(to_save: dict, existing: dict):
    """非交互式执行只补充空字段操作（--choice fill-empty）。"""
    p1_fields = list(existing.values())[0] if existing else {}
    p1_name = list(existing.keys())[0] if existing else "profile.json"
    target = VAULT_DIR / p1_name

    # 计算可补充字段
    can_fill = {}
    for k, new_val in to_save.items():
        old_val = (p1_fields.get(k) or "").strip() if k in ALLOWED_FIELDS else ""
        new_str = str(new_val).strip()
        if k not in ALLOWED_FIELDS:
            cf_data = {}
            if VAULT_PROFILE.exists():
                with open(VAULT_PROFILE, "r", encoding="utf-8") as _f:
                    cf_data = json.load(_f).get("custom_fields", {})
            old_c = str(cf_data.get(k, {}).get("value", "")) if isinstance(cf_data.get(k, {}), dict) else ""
            if not old_c and new_str:
                can_fill[k] = new_str
        elif not old_val and new_str:
            can_fill[k] = new_str

    if not can_fill:
        print("\n没有可补充的空字段。vault 未修改。")
        write_log("INFO: --choice fill-empty 无可补充字段")
        return

    filled = 0
    for k, new in can_fill.items():
        with open(target, "r", encoding="utf-8") as f:
            data = json.load(f)
        if k in ALLOWED_FIELDS:
            if k in data and isinstance(data[k], dict):
                data[k]["value"] = new
            else:
                data[k] = new
        else:
            if "custom_fields" not in data:
                data["custom_fields"] = {}
            data["custom_fields"][k] = {"value": str(new), "confirmed": True, "source": "fill_empty_by_control_center", "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
        with open(target, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        filled += 1
        write_log(f"INFO: --choice fill-empty 补充: {k}")
    print(f"\n[OK] 已补充 {filled} 个空字段。冲突字段未修改。")
    write_log(f"INFO: --choice fill-empty 完成，{filled} 字段")


# ------------------------------------------------------------
# 归档 confirmed_profile.json
# ------------------------------------------------------------
def archive_confirmed(src: Path) -> Path:
    """移动 confirmed_profile.json 到 saved_confirmed_profiles 目录。"""
    SAVED_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    dst = SAVED_DIR / f"confirmed_profile_saved_{ts}.json"
    if dst.exists():
        dst = SAVED_DIR / f"confirmed_profile_saved_{ts}_001.json"
    shutil.move(str(src), str(dst))
    return dst

# ------------------------------------------------------------
# 保存
# ------------------------------------------------------------
def save_to_vault(to_save: dict) -> Path:
    """保存到 vault/profile.json。"""
    VAULT_DIR.mkdir(parents=True, exist_ok=True)
    new_path = VAULT_PROFILE

    # 加载模板
    template = {}
    if TEMPLATE_PATH.exists():
        with open(TEMPLATE_PATH, "r", encoding="utf-8") as f:
            template = json.load(f)

    save_data = {
        "_profile_id": "current",
        "_创建时间": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "_来源": "confirmed_profile.json",
    }
    for key in ALLOWED_FIELDS:
        if key in template:
            if isinstance(template[key], dict):
                save_data[key] = dict(template[key])
                save_data[key]["value"] = to_save.get(key, "")
            else:
                save_data[key] = to_save.get(key, template[key])
        else:
            save_data[key] = to_save.get(key, "")
    for key in to_save:
        confirm_key = f"{key}_confirmed"
        if confirm_key in template:
            save_data[confirm_key] = True

    custom_to_save = {}
    for key, value in to_save.items():
        if key not in ALLOWED_FIELDS:
            custom_to_save[key] = {
                "value": str(value),
                "confirmed": True,
                "source": "profile_save",
                "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            }
    if custom_to_save:
        save_data["custom_fields"] = custom_to_save

    with open(new_path, "w", encoding="utf-8") as f:
        json.dump(save_data, f, ensure_ascii=False, indent=2)
    return new_path

# ------------------------------------------------------------
# Vault 展示
# ------------------------------------------------------------
VAULT_DISPLAY_ORDER = [
    "name", "gender", "birth_date", "id_number", "phone", "email",
    "organization", "department", "title", "education", "degree",
    "major", "research_area", "address", "photo_path",
    "project_experience", "biography",
]

VAULT_LABELS = {
    "name": "姓名", "gender": "性别", "birth_date": "出生日期",
    "id_number": "身份证号", "phone": "手机号", "email": "邮箱",
    "organization": "工作单位", "department": "部门", "title": "职称",
    "education": "学历", "degree": "学位", "major": "专业",
    "research_area": "研究方向", "address": "通讯地址",
    "photo_path": "证件照", "project_experience": "项目经历",
    "biography": "个人简介",
}

def show_vault_merged_profile():
    """
    读取所有 person_*.json，合并展示为一份完整个人信息表。
    终端完整显示字段值（本地用户主动查看），不脱敏。
    """
    profiles = [VAULT_PROFILE] if VAULT_PROFILE.exists() else []
    if not profiles:
        print("\n当前 vault 资料库为空。\n")
        return

    # 加载所有 profile
    all_data = {}
    all_custom = {}
    for p in profiles:
        try:
            with open(p, "r", encoding="utf-8") as f:
                data = json.load(f)
            fields = {}
            for k in VAULT_DISPLAY_ORDER:
                if k in data:
                    if isinstance(data[k], dict):
                        fields[k] = str(data[k].get("value", ""))
                    elif isinstance(data[k], list):
                        fields[k] = "; ".join(str(v) for v in data[k]) if data[k] else ""
                    else:
                        fields[k] = str(data[k]) if data[k] else ""
                else:
                    fields[k] = ""
            all_data[p.name] = fields
            # 收集自定义字段
            cf = data.get("custom_fields", {})
            if cf:
                all_custom[p.name] = cf
        except Exception:
            pass

    if not all_data:
        print("\n无法读取 vault 资料。\n")
        return

    # 合并
    merged = {}
    conflicts = {}
    for key in VAULT_DISPLAY_ORDER:
        values = set()
        sources = {}
        for fname, fields in all_data.items():
            v = fields.get(key, "").strip()
            if v:
                values.add(v)
                if v not in sources:
                    sources[v] = []
                sources[v].append(fname)
        if len(values) == 0:
            merged[key] = ("(空)", [])
        elif len(values) == 1:
            merged[key] = (values.pop(), [])
        else:
            merged[key] = ("[冲突，需要人工确认]", list(zip(values, [sources[v] for v in values])))

    # 输出
    print(f"\n{'='*55}")
    print(f"  个人信息表")
    print(f"{'='*55}")
    print(f"  {'字段':12s} | 当前合并值")
    print(f"  {'-'*12}-+-{'-'*40}")
    for key in VAULT_DISPLAY_ORDER:
        val, extra = merged[key]
        print(f"  {VAULT_LABELS.get(key, key):12s} | {val}")

    # 冲突
    conflict_keys = [k for k, v in merged.items() if v[0] == "[冲突，需要人工确认]"]
    if conflict_keys:
        print(f"\n  冲突字段：{len(conflict_keys)} 个")
        for ck in conflict_keys:
            print(f"    {VAULT_LABELS.get(ck, ck)}:")
            for val, sources in merged[ck][1]:
                print(f"      {val}  (来自 {', '.join(sources)})")
    else:
        print(f"\n  冲突字段：无")

    # 缺失
    missing = [VAULT_LABELS.get(k, k) for k, v in merged.items() if v[0] == "(空)"]
    if missing:
        print(f"  缺失字段（{len(missing)} 个）：{', '.join(missing)}")

    # 自定义字段
    merged_custom = {}
    for fname, cf in all_custom.items():
        for k, v in cf.items():
            if k not in merged_custom:
                merged_custom[k] = v.get("value", "")
    if merged_custom:
        print(f"\n  --- 自定义信息 ---")
        for k, v in merged_custom.items():
            print(f"  {k}: {v}")
    else:
        print(f"\n  自定义信息：无")

    # 重复提示
    names = [d.get("name", "") for d in all_data.values()]
    non_empty = [n for n in names if n]
    if len(non_empty) >= 2 and len(set(non_empty)) < len(non_empty):
        print(f"\n  [提示] vault 中存在多个姓名相同的资料档案，当前只做合并展示，不会自动删除、覆盖或合并文件。")

    print(f"{'='*55}\n")

def show_vault_summary(full_display: bool = True):
    """兼容旧接口，调用合并展示。"""
    show_vault_merged_profile()

# ------------------------------------------------------------
# 命令模式：update
# ------------------------------------------------------------
def validate_custom_field_name(name: str) -> tuple:
    """校验自定义字段名。返回 (is_valid, reason)。"""
    if not name or not name.strip():
        return False, "字段名为空"
    name = name.strip()
    if len(name) > 30:
        return False, f"字段名过长（{len(name)}>30）"
    for ch in ['/', '\\', '..']:
        if ch in name:
            return False, f"字段名包含非法字符: {ch}"
    name_lower = name.lower()
    if '<script' in name_lower or 'javascript:' in name_lower:
        return False, "字段名包含危险内容"
    return True, ""

def cmd_update(update_path: str):
    """从 profile_update.json 更新 profile.json。支持 custom_fields。"""
    write_log("========== SafeFill-ProfileSave update ==========")
    up = Path(update_path)
    if not up.exists():
        print(f"\n错误：update 文件不存在: {update_path}\n")
        sys.exit(1)
    try:
        with open(up, "r", encoding="utf-8") as f:
            update_data = json.load(f)
    except json.JSONDecodeError as e:
        print(f"\n错误：JSON 格式无效: {e}\n")
        sys.exit(1)

    if not update_data.get("confirmed_by_user", False):
        print("\n[STOP] confirmed_by_user 不为 true，拒绝更新。\n")
        write_log("SECURITY: confirmed_by_user=false，拒绝 update")
        sys.exit(1)

    updates = update_data.get("updates", {})
    if not updates:
        print("\n没有可更新的字段。\n")
        sys.exit(0)

    # 加载 profile
    target = VAULT_DIR / "profile.json"
    if not target.exists():
        print("\nprofile.json 不存在。请先运行 SafeFill-ProfileSave save。\n")
        sys.exit(0)

    with open(target, "r", encoding="utf-8") as f:
        data = json.load(f)

    # 分流：标准字段 vs 自定义字段
    standard = {}
    custom = {}
    rejected = []
    for k, v in updates.items():
        val = str(v) if not isinstance(v, (list, dict)) else v
        if k in ALLOWED_FIELDS:
            standard[k] = val
        else:
            ok, reason = validate_custom_field_name(k)
            if ok:
                if len(str(val)) > 5000:
                    print(f"  跳过 '{k}'：字段值超过 5000 字符")
                    write_log(f"INFO: update 跳过过长自定义字段: {k}")
                    continue
                custom[k] = val
            else:
                rejected.append(f"{k}: {reason}")

    if rejected:
        for r in rejected:
            print(f"  跳过非法字段: {r}")
        write_log(f"INFO: update 跳过非法字段: {rejected}")

    if not standard and not custom:
        print("\n没有可更新的字段。\n")
        sys.exit(0)

    # 合并 proposed
    proposed = {}
    proposed.update(standard)
    proposed.update(custom)

    # 冲突检测
    conflicts = detect_conflicts(proposed, source_label="profile_update.json")
    conflict_items = {k: v for k, v in conflicts.items() if v["status"] == "conflict"}
    new_items = {k: v for k, v in conflicts.items() if v["status"] == "new"}

    if conflict_items:
        print(f"\n[STOP] 检测到 {len(conflict_items)} 个字段与新内容冲突。")
        for k, v in conflict_items.items():
            print(f"  {k}: vault=[{v['existing'][:30]}] vs new=[{v['proposed'][:30]}]")
        jp, mp = generate_conflict_files(conflicts)
        print(f"\n  冲突文件: {jp}")
        print(f"  请创建 profile_conflict_resolution.json 后运行 resolve。\n")
        write_log(f"INFO: update 检测到 {len(conflict_items)} 个冲突，已生成冲突文件")
        sys.exit(0)

    if not new_items:
        print("\n所有字段已存在且相同，无需更新。\n")
        sys.exit(0)

    # 只有新增字段，无冲突 → 直接写入
    print(f"\n修改预览（profile.json）：新增 {len(new_items)} 个字段")
    for k, v in new_items.items():
        print(f"  {k}: (空) -> {v['proposed'][:40]}")

    BACKUP_DIR_ABS = VAULT_DIR / "backups"
    BACKUP_DIR_ABS.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = BACKUP_DIR_ABS / f"profile_backup_{ts}.json"
    shutil.copy2(str(target), str(backup_path))
    write_log(f"INFO: update 备份: {backup_path.name} | 新增: {len(new_items)}")

    for k, v in new_items.items():
        if v.get("is_custom"):
            if "custom_fields" not in data:
                data["custom_fields"] = {}
            data["custom_fields"][k] = {"value": v["proposed"], "confirmed": True, "source": "user_update", "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
        else:
            if k in data and isinstance(data[k], dict):
                data[k]["value"] = v["proposed"]
            else:
                data[k] = v["proposed"]

    with open(target, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    write_log(f"INFO: update 已保存 {len(new_items)} 新增字段 | 备份: {backup_path.name}")
    print(f"\n[OK] 新增 {len(new_items)} 个字段。备份: {backup_path.name}")
    show_vault_merged_profile()
    write_log("========== SafeFill-ProfileSave update 完成 ==========")


# ------------------------------------------------------------
# 冲突检测与 resolve
# ------------------------------------------------------------
def detect_conflicts(proposed: dict, source_label: str = "confirmed_profile.json") -> dict:
    """
    比较 proposed 与 profile.json 的现有值。
    返回 {field: {existing, proposed, status}}。
    status: "new" | "same" | "conflict" | "empty_new"
    """
    target = VAULT_DIR / "profile.json"
    existing_data = {}
    custom_data = {}
    if target.exists():
        with open(target, "r", encoding="utf-8") as f:
            d = json.load(f)
        for k in ALLOWED_FIELDS:
            if k in d:
                existing_data[k] = str(d[k].get("value", "")) if isinstance(d[k], dict) else str(d[k])
        custom_data = d.get("custom_fields", {})

    result = {}
    for k, new_val in proposed.items():
        new_str = str(new_val) if not isinstance(new_val, (list, dict)) else str(new_val)
        if not new_str.strip():
            result[k] = {"status": "empty_new", "existing": "", "proposed": ""}
            continue

        if k in ALLOWED_FIELDS:
            existing = existing_data.get(k, "")
            if not existing:
                result[k] = {"status": "new", "existing": "", "proposed": new_str}
            elif existing.strip() == new_str.strip():
                result[k] = {"status": "same", "existing": existing, "proposed": new_str}
            else:
                result[k] = {"status": "conflict", "existing": existing, "proposed": new_str, "source": source_label}
        else:
            # custom field
            if k in custom_data:
                existing_c = str(custom_data[k].get("value", ""))
                if existing_c.strip() == new_str.strip():
                    result[k] = {"status": "same", "existing": existing_c, "proposed": new_str, "is_custom": True}
                else:
                    result[k] = {"status": "conflict", "existing": existing_c, "proposed": new_str, "is_custom": True, "source": source_label}
            else:
                result[k] = {"status": "new", "existing": "", "proposed": new_str, "is_custom": True}
    return result


def generate_conflict_files(conflicts: dict):
    """生成 profile_conflicts_*.json 和 .md。"""
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    json_path = CANDIDATE_DIR / f"profile_conflicts_{ts}.json"
    md_path = CANDIDATE_DIR / f"profile_conflicts_{ts}.md"

    conflict_items = {k: v for k, v in conflicts.items() if v["status"] == "conflict"}
    new_items = {k: v for k, v in conflicts.items() if v["status"] == "new"}
    same_items = {k: v for k, v in conflicts.items() if v["status"] == "same"}

    # JSON
    json_data = {
        "_说明": "vault 信息冲突确认文件。请创建 profile_conflict_resolution.json 来确认如何处理。",
        "_生成时间": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "_提示": "decisions 可选: keep_existing / overwrite / save_as_custom / skip",
        "conflicts": {},
        "new_fields": {},
        "unchanged": list(same_items.keys()),
    }
    for k, v in conflict_items.items():
        json_data["conflicts"][k] = {
            "existing": v.get("existing", ""),
            "proposed": v.get("proposed", ""),
            "source": v.get("source", ""),
            "is_custom": v.get("is_custom", False),
        }
    for k, v in new_items.items():
        json_data["new_fields"][k] = {
            "proposed": v.get("proposed", ""),
            "is_custom": v.get("is_custom", False),
        }

    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(json_data, f, ensure_ascii=False, indent=2)

    # Markdown
    md = [
        "# vault 信息冲突，请用户确认",
        f"> 生成时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        "",
        "## [STOP] 冲突字段",
        "以下字段 vault 已有内容与新内容不一致，请决定如何处理。",
        "",
    ]
    if conflict_items:
        md.append("| 字段 | vault 原内容 | 新内容 | 来源 |")
        md.append("|------|-----------|--------|------|")
        for k, v in conflict_items.items():
            existing = str(v.get("existing", ""))[:40]
            proposed = str(v.get("proposed", ""))[:40]
            src = v.get("source", "")[:20]
            md.append(f"| {k} | {existing} | {proposed} | {src} |")
        md.append("")
    else:
        md.append("（无）")
        md.append("")

    if new_items:
        md.append("## 新增字段（vault 中原本为空）")
        md.append("| 字段 | 新内容 | 类型 |")
        md.append("|------|--------|------|")
        for k, v in new_items.items():
            proposed = str(v.get("proposed", ""))[:40]
            ct = "自定义" if v.get("is_custom") else "标准"
            md.append(f"| {k} | {proposed} | {ct} |")
        md.append("")

    md.append("---")
    md.append("## 如何处理")
    md.append("")
    md.append("1. 创建 `candidate_reviews\\profile_conflict_resolution.json`")
    md.append("2. 格式：")
    md.append("```json")
    md.append('{ "confirmed_by_user": true, "decisions": {')
    md.append('    "字段名": "keep_existing"   // 保留原内容')
    md.append('    "字段名": "overwrite"      // 用新内容覆盖')
    md.append('    "字段名": "save_as_custom" // 保存到自定义字段')
    md.append('    "字段名": "skip"           // 跳过不处理')
    md.append('  }')
    md.append('}')
    md.append("```")
    md.append(f"3. 运行: `python save_confirmed_profile.py resolve {json_path}`")

    with open(md_path, "w", encoding="utf-8") as f:
        f.write("\n".join(md))

    write_log(f"INFO: 生成冲突文件: {json_path.name}, {md_path.name}")
    return json_path, md_path


def cmd_resolve(resolve_path: str):
    """应用冲突决策。"""
    write_log("========== SafeFill-ProfileSave resolve ==========")
    rp = Path(resolve_path)
    if not rp.exists():
        print(f"\n错误：resolution 文件不存在: {resolve_path}\n")
        sys.exit(1)

    with open(rp, "r", encoding="utf-8") as f:
        resolution = json.load(f)

    if not resolution.get("confirmed_by_user", False):
        print("\n[STOP] confirmed_by_user 不为 true，拒绝执行。\n")
        sys.exit(1)

    decisions = resolution.get("decisions", {})
    if not decisions:
        print("\n没有 decisions。\n")
        sys.exit(0)

    # 找最近冲突文件
    conflict_files = sorted(CANDIDATE_DIR.glob("profile_conflicts_*.json"), reverse=True)
    if not conflict_files:
        print("\n错误：未找到冲突文件。请先运行 save 或 update。\n")
        sys.exit(0)

    with open(conflict_files[0], "r", encoding="utf-8") as f:
        conflict_data = json.load(f)

    all_conflicts = conflict_data.get("conflicts", {})

    target = VAULT_DIR / "profile.json"
    if not target.exists():
        print("\nprofile.json 不存在。\n")
        sys.exit(0)

    with open(target, "r", encoding="utf-8") as f:
        data = json.load(f)

    applied = []
    for k, decision in decisions.items():
        if k not in all_conflicts and decision != "skip":
            print(f"  跳过 '{k}'：不在冲突列表中")
            continue
        ci = all_conflicts.get(k, {})
        if decision == "keep_existing":
            applied.append(f"{k}: keep_existing")
        elif decision == "overwrite":
            new_val = ci.get("proposed", "")
            if k in ALLOWED_FIELDS:
                if k in data and isinstance(data[k], dict):
                    data[k]["value"] = new_val
                else:
                    data[k] = new_val
            else:
                if "custom_fields" not in data:
                    data["custom_fields"] = {}
                data["custom_fields"][k] = {"value": new_val, "confirmed": True, "source": "resolve", "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
            applied.append(f"{k}: overwrite")
        elif decision == "save_as_custom":
            new_val = ci.get("proposed", "")
            if "custom_fields" not in data:
                data["custom_fields"] = {}
            data["custom_fields"][k] = {"value": new_val, "confirmed": True, "source": "resolve_save_as_custom", "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
            applied.append(f"{k}: save_as_custom")
        elif decision == "skip":
            applied.append(f"{k}: skip")
        else:
            print(f"  未知 decision '{decision}'，跳过 '{k}'")

    if not applied:
        print("\n没有应用任何决策。\n")
        sys.exit(0)

    # 备份
    BACKUP_DIR_ABS = VAULT_DIR / "backups"
    BACKUP_DIR_ABS.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = BACKUP_DIR_ABS / f"profile_backup_{ts}.json"
    shutil.copy2(str(target), str(backup_path))
    write_log(f"INFO: resolve 备份: {backup_path.name} | 决策: {applied}")

    with open(target, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    write_log(f"INFO: resolve 已应用 {len(applied)} 个决策")
    print(f"\n[OK] 已应用 {len(applied)} 个决策。备份: {backup_path.name}")
    for a in applied:
        print(f"  - {a}")
    show_vault_merged_profile()

    # 归档冲突文件和 resolution
    SAVED_DIR.mkdir(parents=True, exist_ok=True)
    for cf in conflict_files[:1]:
        dst = SAVED_DIR / cf.name
        if not dst.exists():
            shutil.move(str(cf), str(dst))
    dst_r = SAVED_DIR / rp.name
    if not dst_r.exists():
        shutil.move(str(rp), str(dst_r))
    write_log("========== SafeFill-ProfileSave resolve 完成 ==========")


# ------------------------------------------------------------
# 主流程（dispatch）
# ------------------------------------------------------------
def main():
    print("\nSafeFill-ProfileSave — 管理本地 vault 资料库")
    print("不联网 | 不调用 API\n")
    args = sys.argv[1:]

    if not args:
        # 兼容旧流程：默认 save
        cmd = "save"
    else:
        cmd = args[0]

    if cmd == "show":
        show_vault_merged_profile()

    elif cmd == "fields":
        for k, v in VAULT_LABELS.items():
            print(f"{k} {v}")

    elif cmd == "update":
        if len(args) < 2:
            print("用法: python save_confirmed_profile.py update <profile_update.json>")
            sys.exit(1)
        cmd_update(args[1])

    elif cmd == "save":
        # 解析 --choice 参数（供 ControlCenter 非交互调用）
        choice = None
        if "--choice" in args:
            idx = args.index("--choice")
            if idx + 1 < len(args):
                choice = args[idx + 1]

        write_log("========== SafeFill-ProfileSave save ==========")
        write_log(f"INFO: vault/profile.json 存在={VAULT_PROFILE.exists()}，字段数不记录敏感值")
        if choice:
            write_log(f"INFO: --choice={choice}（非交互模式）")
        show_vault_merged_profile()

        source_path, source_label = select_profile_source()
        if source_path is None:
            write_log("ERROR: 未找到 latest_candidate 或 confirmed_profile.json")
            print("\n未找到可保存的最新提取结果。")
            print("请先运行 SafeFill-ProfileExtract，从旧表提取候选资料。")
            sys.exit(1)

        to_save, issues = load_confirmed_data(source_path)
        write_log(f"INFO: 读取 {source_label}，待保存字段 {len(to_save)} 个")
        if issues:
            print("\n校验：")
            for i in issues: print(f"  - {i}")
            print()
        if not to_save:
            write_log("WARN: 无字段可保存")
            sys.exit(0)

        existing = load_existing_profiles()
        write_log(f"INFO: 已加载 {len(existing)} 个已有 profile")
        dup = check_duplicate(to_save, existing)
        if dup:
            write_log(f"INFO: 检测到重复 — {dup}")
            print(f"\n[STOP] 重复检测：confirmed_profile.json 与 {dup} 内容重复。")
            print(f"  已停止保存，不新增 person 文件。\n")
            sys.exit(0)

        # --choice 非交互模式分支
        if choice == "detect":
            detect_and_output_json(to_save)
            write_log("========== SafeFill-ProfileSave detect 完成 ==========")
            return

        if existing:
            if choice == "replace":
                p1_fields = list(existing.values())[0] if existing else {}
                execute_replace(to_save, p1_fields)
                if source_path.name == "confirmed_profile.json":
                    archived = archive_confirmed(source_path)
                    write_log(f"INFO: confirmed_profile.json 已归档到 {archived.name}")
                else:
                    print("\n提示：本次提取结果仍保留在 candidate_reviews\\，后续可由 SafeFill-Cleaner 清理。")
                write_log("========== SafeFill-ProfileSave replace 完成 ==========")
            elif choice == "fill-empty":
                execute_fill_empty(to_save, existing)
                if source_path.name == "confirmed_profile.json":
                    archived = archive_confirmed(source_path)
                    write_log(f"INFO: confirmed_profile.json 已归档到 {archived.name}")
                else:
                    print("\n提示：本次提取结果仍保留在 candidate_reviews\\，后续可由 SafeFill-Cleaner 清理。")
                write_log("========== SafeFill-ProfileSave fill-empty 完成 ==========")
            elif choice == "stop":
                print("\n已停止，vault 未修改。")
                write_log("INFO: --choice stop，vault 未修改")
                write_log("========== SafeFill-ProfileSave stop 完成 ==========")
            else:
                diff_and_menu(to_save)
                if source_path.name == "confirmed_profile.json":
                    archived = archive_confirmed(source_path)
                    write_log(f"INFO: confirmed_profile.json 已归档到 {archived.name}")
                else:
                    print("\n提示：本次提取结果仍保留在 candidate_reviews\\，后续可由 SafeFill-Cleaner 清理。")
                write_log("========== SafeFill-ProfileSave save 完成 ==========")
        else:
            if choice == "stop":
                print("\n已停止，vault 未修改。")
                write_log("INFO: --choice stop (初次保存)，vault 未修改")
                return
            if choice and choice != "replace":
                print(f"\n[STOP] vault 尚无资料，--choice {choice} 仅适用于已有资料的情况。")
                print("请使用 --choice replace 创建 vault/profile.json，或不传 --choice 进行交互式保存。")
                sys.exit(1)
            if choice == "replace":
                name_new = str(to_save.get("name", ""))
                print(f"\n将创建 vault/profile.json（{name_new}）。")
                new_path = save_to_vault(to_save)
                write_log(f"INFO: --choice replace 已创建 {new_path.name}（{len(to_save)} 字段）")
                if source_path.name == "confirmed_profile.json":
                    archived = archive_confirmed(source_path)
                    write_log(f"INFO: confirmed_profile.json 已归档到 {archived.name}")
                else:
                    print("提示：候选提取文件仍保留在 candidate_reviews\\，后续可由 SafeFill-Cleaner 清理。")
                print(f"\n[OK] 已创建 profile.json（{len(to_save)} 字段）")
                show_vault_merged_profile()
                write_log("========== SafeFill-ProfileSave replace 完成 ==========")
            else:
                if not confirm_initial_save(to_save, source_label):
                    print("\n已停止，vault 未修改。")
                    print("提取结果仍保留在 candidate_reviews\\，后续可由 SafeFill-Cleaner 清理。")
                    write_log("INFO: 用户停止初次保存，vault 未修改")
                    return
                new_path = save_to_vault(to_save)
                write_log(f"INFO: 已保存 {new_path.name}（{len(to_save)} 字段）")
                if source_path.name == "confirmed_profile.json":
                    archived = archive_confirmed(source_path)
                    write_log(f"INFO: confirmed_profile.json 已归档到 {archived.name}")
                    print(f"\n[OK] 已保存 {new_path.name}（{len(to_save)} 字段），归档: {archived.name}")
                else:
                    print(f"\n[OK] 已保存 {new_path}（{len(to_save)} 字段）")
                    print("提示：候选提取文件仍保留在 candidate_reviews\\，后续可由 SafeFill-Cleaner 清理。")
                show_vault_merged_profile()
                write_log("========== SafeFill-ProfileSave save 完成 ==========")

    elif cmd == "resolve":
        if len(args) < 2:
            print("用法: python save_confirmed_profile.py resolve <profile_conflict_resolution.json>")
            sys.exit(1)
        cmd_resolve(args[1])

    else:
        print("用法:")
        print("  python save_confirmed_profile.py             默认 save")
        print("  python save_confirmed_profile.py show        显示个人信息表")
        print("  python save_confirmed_profile.py save        从 confirmed_profile.json 保存")
        print("  python save_confirmed_profile.py fields      列出可用字段")
        print("  python save_confirmed_profile.py update <json>  从 profile_update.json 更新 profile")
        print("  python save_confirmed_profile.py resolve <json>  应用冲突决策")

if __name__ == "__main__":
    main()
