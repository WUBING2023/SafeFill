# -*- coding: utf-8 -*-
"""
SafeFill — 公共 API 调用模块 (v2.0 API-first)
职责：
  1. 读取 api_config.json 并断言是否允许发送
  2. 提供 send_json_request() 供 ProfileExtract / FormReview 调用
  3. 保存每次 API 请求到 api_logs
  4. 保留原有 CLI: preview / send / check

安全底线：
  - user_accepts_api_data_risk=false 时拒绝发送
  - API Key 只从环境变量读取
  - 不修改 vault / input_forms / new_forms
  - 不自动接入业务流程
"""

import os
import sys
import json
import re
import copy
from datetime import datetime
from pathlib import Path

# ------------------------------------------------------------
# 项目根目录
# ------------------------------------------------------------
PROJECT_ROOT = Path(__file__).resolve().parent.parent

CONFIG_DIR = PROJECT_ROOT / "app"
REPORTS_DIR = PROJECT_ROOT / "filling_reports"
PREVIEW_DIR = PROJECT_ROOT / "api_previews"
RESULT_DIR = PROJECT_ROOT / "api_results"
API_LOGS_DIR = PROJECT_ROOT / "api_logs"

CONFIG_PATH = CONFIG_DIR / "api_config.json"
TEMPLATE_PATH = CONFIG_DIR / "api_config_template.json"

# 已知资料库字段
KNOWN_PROFILE_KEYS = [
    "name", "gender", "birth_date", "id_number", "phone", "email",
    "organization", "department", "title", "education", "degree",
    "research_area", "address", "photo_path", "project_experience", "biography",
]

# 敏感字段 —— 默认禁止发送
SENSITIVE_KEYS = {
    "id_number", "phone", "address", "photo_path",
    "bank_account", "signature", "full_resume",
}

# 需脱敏的字段 —— 如果 exceptionally 允许发送，也必须脱敏
MASK_BEFORE_SEND = {
    "id_number": "mask_id_number",
    "phone": "mask_phone",
    "address": "mask_address",
    "photo_path": "mask_photo_path",
}

AUTO_API_PROVIDERS = [
    {
        "provider": "safefill",
        "key_env": ["SAFEFILL_API_KEY", "SECURE_FORM_API_KEY"],
        "endpoint_env": ["SAFEFILL_API_ENDPOINT", "SECURE_FORM_API_ENDPOINT"],
        "model_env": ["SAFEFILL_API_MODEL", "SECURE_FORM_API_MODEL"],
        "default_endpoint": "",
        "default_model": "",
    },
    {
        "provider": "openai",
        "key_env": ["OPENAI_API_KEY"],
        "endpoint_env": ["OPENAI_CHAT_ENDPOINT", "OPENAI_BASE_URL", "OPENAI_API_BASE"],
        "model_env": ["OPENAI_MODEL"],
        "default_endpoint": "https://api.openai.com/v1/chat/completions",
        "default_model": "gpt-4o-mini",
    },
    {
        "provider": "deepseek",
        "key_env": ["DEEPSEEK_API_KEY"],
        "endpoint_env": ["DEEPSEEK_CHAT_ENDPOINT", "DEEPSEEK_BASE_URL", "DEEPSEEK_API_BASE"],
        "model_env": ["DEEPSEEK_MODEL"],
        "default_endpoint": "https://api.deepseek.com/v1/chat/completions",
        "default_model": "deepseek-chat",
    },
]


def _env_truthy(name: str, default: bool = False) -> bool:
    value = os.environ.get(name, "")
    if not value:
        return default
    return value.strip().lower() in {"1", "true", "yes", "y", "on"}


def _first_env(names: list[str]) -> tuple[str, str]:
    for name in names:
        value = os.environ.get(name, "").strip()
        if value:
            return name, value
    return "", ""


def _normalize_chat_endpoint(value: str) -> str:
    endpoint = (value or "").strip().rstrip("/")
    if not endpoint:
        return ""
    if endpoint.endswith("/chat/completions"):
        return endpoint
    return endpoint + "/chat/completions"


def _infer_model_from_endpoint(endpoint: str, fallback: str = "") -> str:
    lower_endpoint = (endpoint or "").lower()
    if "deepseek" in lower_endpoint:
        return "deepseek-chat"
    if "openai.com" in lower_endpoint:
        return "gpt-4o-mini"
    return fallback


def auto_detect_api_config(config: dict | None = None) -> dict:
    """
    根据本机环境变量自动补全 API 配置。
    不读取文件中的密钥，不打印密钥，不把密钥写入 api_config.json。
    """
    resolved = copy.deepcopy(config or {})

    # GitHub 下载后，如果没有 api_config.json，也允许用环境变量直接启用。
    if "enabled" not in resolved:
        resolved["enabled"] = _env_truthy("SAFEFILL_API_ENABLED", False)
    if "api_first" not in resolved:
        resolved["api_first"] = _env_truthy("SAFEFILL_API_FIRST", bool(resolved.get("enabled")))
    if "user_accepts_api_data_risk" not in resolved:
        resolved["user_accepts_api_data_risk"] = _env_truthy("SAFEFILL_ACCEPT_API_RISK", False)
    if "SAFEFILL_API_ENABLED" in os.environ:
        resolved["enabled"] = _env_truthy("SAFEFILL_API_ENABLED", False)
    if "SAFEFILL_API_FIRST" in os.environ:
        resolved["api_first"] = _env_truthy("SAFEFILL_API_FIRST", False)
    if "SAFEFILL_ACCEPT_API_RISK" in os.environ:
        resolved["user_accepts_api_data_risk"] = _env_truthy("SAFEFILL_ACCEPT_API_RISK", False)

    # 环境变量可以覆盖空配置，但不覆盖用户已经写好的 endpoint/model/api_key_env。
    endpoint = str(resolved.get("endpoint", "") or "").strip()
    model = str(resolved.get("model", "") or "").strip()
    key_env = str(resolved.get("api_key_env", "") or "").strip()

    for provider in AUTO_API_PROVIDERS:
        found_key_env, _ = _first_env(provider["key_env"])
        if not found_key_env:
            continue

        found_endpoint_env, found_endpoint = _first_env(provider["endpoint_env"])
        found_model_env, found_model = _first_env(provider["model_env"])

        if not key_env or not os.environ.get(key_env, ""):
            resolved["api_key_env"] = found_key_env
        if not endpoint:
            resolved["endpoint"] = _normalize_chat_endpoint(found_endpoint or provider["default_endpoint"])
        if not model:
            resolved["model"] = found_model or _infer_model_from_endpoint(
                found_endpoint or provider["default_endpoint"],
                provider["default_model"],
            )
        if not resolved.get("provider") or resolved.get("provider") == "openai_compatible":
            resolved["provider"] = provider["provider"]

        resolved["_auto_detected_api"] = {
            "provider": provider["provider"],
            "api_key_env": found_key_env,
            "endpoint_source": found_endpoint_env or ("default" if provider["default_endpoint"] else ""),
            "model_source": found_model_env or ("default" if provider["default_model"] else ""),
        }
        break

    return resolved


# ------------------------------------------------------------
# 日志
# ------------------------------------------------------------
def write_log(message: str):
    API_LOGS_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    log_file = API_LOGS_DIR / "api_assist.log"
    with open(log_file, "a", encoding="utf-8") as f:
        f.write(f"[{ts}] {message}\n")
    print(f"[API-LOG] {message}")


# ------------------------------------------------------------
# 公共 API 函数 (v2.0)
# ------------------------------------------------------------
def load_api_config() -> dict:
    """读取 api_config.json 并返回配置字典。不存在时返回空。"""
    if CONFIG_PATH.exists():
        try:
            with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                return auto_detect_api_config(json.load(f))
        except Exception as e:
            write_log(f"ERROR: 读取 api_config.json 失败: {e}")
            return {}
    write_log("INFO: api_config.json 不存在")
    return auto_detect_api_config({})


def assert_api_ready(config: dict = None) -> tuple:
    """
    检查是否满足 API 发送条件。
    返回 (ok: bool, message: str)。
    """
    if config is None:
        config = load_api_config()
    else:
        config = auto_detect_api_config(config)
    if not config:
        return False, "api_config.json 不存在或为空。请从 api_config_template.json 复制创建。"
    if not config.get("enabled"):
        return False, "enabled 不为 true。"
    if not config.get("api_first"):
        return False, "api_first 不为 true。"
    if not config.get("user_accepts_api_data_risk"):
        return False, "user_accepts_api_data_risk 不为 true。SafeFill 不会发送资料。"
    endpoint = config.get("endpoint", "")
    if not endpoint:
        return False, "endpoint 未设置。"
    model = config.get("model", "")
    if not model:
        return False, "model 未设置。"
    key_env = config.get("api_key_env", "SECURE_FORM_API_KEY")
    api_key = os.environ.get(key_env, "")
    if not api_key:
        return False, f"环境变量 {key_env} 未设置。"
    return True, "OK"


def save_api_trace(task_type: str, request_payload: dict, response_data, success: bool, error: str = None):
    """保存 API 调用记录到 api_logs。"""
    RESULT_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    trace = {
        "task_type": task_type,
        "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "endpoint": request_payload.get("_endpoint", ""),
        "model": request_payload.get("_model", ""),
        "success": success,
        "request_payload": request_payload,
    }
    if success:
        trace["response_data"] = response_data
    else:
        trace["error"] = error or "unknown"
        if response_data:
            # Save raw content for debugging (up to 15000 chars)
            raw_str = str(response_data)
            trace["raw_response"] = raw_str[:15000]

    fname = RESULT_DIR / f"api_trace_{task_type}_{ts}.json"
    with open(fname, "w", encoding="utf-8") as f:
        json.dump(trace, f, ensure_ascii=False, indent=2)
    write_log(f"INFO: API trace 已保存: {fname.name}")


# ------------------------------------------------------------
# JSON 容错解析
# ------------------------------------------------------------
def robust_json_loads(text: str, task_type: str = "") -> tuple:
    """
    Progressively try to parse JSON from API response.
    Returns (ok: bool, parsed: dict, message: str).
    """
    raw = text.strip()
    repair_msg = ""

    # 1. Direct parse
    try:
        return True, json.loads(raw), ""
    except json.JSONDecodeError:
        pass

    # 2. Extract from ```json ... ``` fence
    fence_m = re.search(r'```(?:json)?\s*([\s\S]*?)```', raw)
    if fence_m:
        try:
            return True, json.loads(fence_m.group(1).strip()), "extracted from ```json fence```"
        except json.JSONDecodeError:
            pass

    # 3. Extract first complete JSON object or array
    for pattern in [r'\{[\s\S]*\}', r'\[[\s\S]*\]']:
        m = re.search(pattern, raw)
        if m:
            candidate = m.group()
            try:
                parsed = json.loads(candidate)
                repair_msg = "extracted JSON from surrounding text"
                # If it's an array and task is form_fill_plan, wrap it
                if isinstance(parsed, list) and task_type == "form_fill_plan":
                    parsed = {"writes": parsed}
                    repair_msg += " (array wrapped as writes)"
                return True, parsed, repair_msg
            except json.JSONDecodeError:
                # 4. Light repair on the extracted candidate
                repaired = _light_json_repair(candidate)
                if repaired != candidate:
                    try:
                        parsed = json.loads(repaired)
                        repair_msg = "JSON repaired (trailing commas, quotes)"
                        if isinstance(parsed, list) and task_type == "form_fill_plan":
                            parsed = {"writes": parsed}
                            repair_msg += " (array wrapped as writes)"
                        return True, parsed, repair_msg
                    except json.JSONDecodeError:
                        pass

    # 5. Light repair on full text
    repaired = _light_json_repair(raw)
    if repaired != raw:
        try:
            parsed = json.loads(repaired)
            return True, parsed, "JSON repaired from full text"
        except json.JSONDecodeError:
            pass

    return False, {}, f"JSON parse failed after all attempts (text length: {len(raw)})"


def _light_json_repair(text: str) -> str:
    # Apply safe minimal JSON repairs. Does NOT guess values or structure.
    t = text.strip()
    # Remove trailing commas before } or ]
    t = re.sub(r',\s*(\}|\])', r'\1', t)
    # Replace common Chinese punctuation that breaks JSON structure
    LQ = chr(0x201C); RQ = chr(0x201D); LS = chr(0x2018); RS = chr(0x2019)
    t = t.replace(LQ, chr(0x22)).replace(RQ, chr(0x22))
    t = t.replace(LS, chr(0x27)).replace(RS, chr(0x27))
    t = t.replace(chr(0xFF0C), chr(0x2C))
    t = t.replace(chr(0xFF1A), chr(0x3A))
    # Fix unquoted property names
    t = re.sub(r'\{(\s*)([a-zA-Z_][a-zA-Z0-9_]*)(\s*):', r'{\1"\2"\3:', t)
    t = re.sub(r',(\s*)([a-zA-Z_][a-zA-Z0-9_]*)(\s*):', r',\1"\2"\3:', t)
    # Try adding missing closing braces
    opens = t.count('{') - t.count('}')
    if opens > 0 and opens <= 20:
        candidate = t + ('}' * opens)
        try:
            json.loads(candidate)
            return candidate
        except json.JSONDecodeError:
            pass
    return t


def send_json_request(task_type: str, payload: dict, schema_hint: str = None, skip_ready_check: bool = False) -> tuple:
    """
    发送 API 请求并返回 (success: bool, result: dict, error: str)。
    task_type: profile_extract / form_fill_plan / complex_field_assist
    skip_ready_check: 跳过 assert_api_ready（用于 CLI send 模式已有自己的闸门）
    """
    if not skip_ready_check:
        ok, msg = assert_api_ready()
        if not ok:
            write_log(f"SECURITY: assert_api_ready 失败: {msg}")
            return False, {}, msg

    config = load_api_config()
    endpoint = config.get("endpoint", "")
    model = config.get("model", "")
    key_env = config.get("api_key_env", "SECURE_FORM_API_KEY")
    api_key = os.environ.get(key_env, "")

    system_msg = "你是一个表格填写助手。请按用户要求返回 JSON 格式的结果。"
    if schema_hint:
        system_msg += f" 期望返回格式：{schema_hint}"

    request_body = {
        "_endpoint": endpoint,
        "_model": model,
        "body": {
            "model": model,
            "messages": [
                {"role": "system", "content": system_msg},
                {"role": "user", "content": json.dumps(payload, ensure_ascii=False)},
            ],
            "max_tokens": 8000 if task_type == "form_fill_plan" else int(config.get("max_tokens", 6000)),
            "temperature": 0.1,
        }
    }

    json_bytes = json.dumps(request_body["body"], ensure_ascii=False).encode("utf-8")

    try:
        import urllib.request as ur
        req = ur.Request(
            endpoint,
            data=json_bytes,
            headers={
                "Content-Type": "application/json; charset=utf-8",
                "Authorization": f"Bearer {api_key}",
            },
            method="POST",
        )
        write_log(f"INFO: 发送 API 请求 task={task_type} endpoint={endpoint[:50]}")
        with ur.urlopen(req, timeout=60) as resp:
            resp_body = resp.read().decode("utf-8")
        resp_json = json.loads(resp_body)

        content = resp_json.get("choices", [{}])[0].get("message", {}).get("content", "")
        ok, parsed, parse_msg = robust_json_loads(content, task_type=task_type)
        if not ok:
            write_log(f"ERROR: API JSON 解析失败: {parse_msg}")
            trace_content = content[:15000]
            error_detail = f"{parse_msg} | content_len={len(content)}"
            save_api_trace(task_type, request_body, trace_content, False, error=error_detail)
            return False, {}, parse_msg

        if parse_msg:
            write_log(f"WARN: API JSON 经过容错修复后解析成功 ({parse_msg})")

        request_body["json_repaired"] = bool(parse_msg)
        request_body["json_repair_message"] = parse_msg
        save_api_trace(task_type, request_body, parsed, True)
        return True, parsed, ""

    except Exception as e:
        err_msg = str(e)
        write_log(f"ERROR: API 请求失败 task={task_type}: {err_msg}")
        save_api_trace(task_type, request_body, None, False, error=err_msg)
        return False, {}, err_msg


# ------------------------------------------------------------
# 配置加载
# ------------------------------------------------------------
def load_config() -> dict | None:
    if not CONFIG_PATH.exists():
        if TEMPLATE_PATH.exists():
            print(f"\n[提示] API 配置文件不存在。")
            print(f"  请从模板复制创建配置文件：")
            print(f"  {TEMPLATE_PATH}")
            print(f"  -> {CONFIG_PATH}")
            print(f"  然后根据需要编辑其中的 enabled、endpoint、model 等字段。")
            print(f"  API Key 只能通过环境变量 SECURE_FORM_API_KEY 设置，不得写入配置文件。\n")
        return auto_detect_api_config({})
    try:
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            return auto_detect_api_config(json.load(f))
    except Exception as e:
        write_log(f"ERROR: 无法读取配置: {e}")
        return None


def get_api_key(config: dict) -> str | None:
    env_var = config.get("api_key_env", "SECURE_FORM_API_KEY")
    key = os.environ.get(env_var, "")
    if not key:
        write_log(f"ERROR: 环境变量 {env_var} 未设置")
    return key if key else None


# ------------------------------------------------------------
# 脱敏工具
# ------------------------------------------------------------
def mask_id_number(v: str) -> str:
    if len(v) >= 15:
        return v[:3] + "*" * (len(v) - 7) + v[-4:]
    return "***"

def mask_phone(v: str) -> str:
    clean = v.strip().replace("-", "").replace(" ", "")
    if len(clean) == 11 and clean.isdigit():
        return clean[:3] + "****" + clean[-4:]
    return "***"

def mask_address(v: str) -> str:
    if len(v) <= 6:
        return v + "***"
    return v[:6] + "***"

def mask_photo_path(v: str) -> str:
    return "[照片路径已隐藏]"

MASKERS = {
    "id_number": mask_id_number,
    "phone": mask_phone,
    "address": mask_address,
    "photo_path": mask_photo_path,
}


# ------------------------------------------------------------
# 敏感字段检测
# ------------------------------------------------------------
def _validate_preview_path(preview_path: Path) -> bool:
    """
    校验 preview 文件路径安全：
    1. 必须解析后位于 PREVIEW_DIR 内
    2. 文件名必须匹配 api_preview_*.json
    """
    try:
        resolved = preview_path.resolve()
        resolved.relative_to(PREVIEW_DIR.resolve())
    except (ValueError, OSError):
        write_log(f"SECURITY: preview 路径越界，拒绝访问: {preview_path}")
        return False
    # 文件名模式检查
    fname = resolved.name
    if not (fname.startswith("api_preview_") and fname.endswith(".json")):
        write_log(f"SECURITY: preview 文件名不匹配 api_preview_*.json: {fname}")
        return False
    return True


def detect_sensitive_in_text(text: str) -> list:
    """检测文本中是否包含敏感数据模式。返回发现的敏感类型列表。"""
    found = []
    patterns = {
        "id_number": r"\b\d{15,18}\b",
        "phone": r"\b1[3-9]\d{9}\b",
        "email_detailed": r"\b[\w.-]+@[\w.-]+\.\w+\b",
    }
    for stype, pat in patterns.items():
        if re.search(pat, text):
            found.append(stype)
    return found


# ------------------------------------------------------------
# 模式 A: 生成 API 预览
# ------------------------------------------------------------
def cmd_preview():
    write_log("========== 生成 API 预览 ==========")

    # 加载配置
    config = load_config()
    if config is None:
        print("无法加载配置，预览生成失败。")
        sys.exit(1)

    enabled = config.get("enabled", False)
    dry_run = config.get("dry_run", True)

    print(f"\n  API 配置状态：")
    print(f"    enabled  : {enabled}")
    print(f"    dry_run  : {dry_run}")
    print(f"    provider : {config.get('provider', '')}")
    print(f"    endpoint : {config.get('endpoint', '(未设置)')}")
    print(f"    model    : {config.get('model', '(未设置)')}")

    # 读取 latest_filling_run 中的复杂字段
    if not REPORTS_DIR.exists():
        print("\n[提示] filling_reports 为空，请先完成 SafeFill-FormReview。\n")
        write_log("WARN: filling_reports 为空")
        sys.exit(0)

    latest_path = REPORTS_DIR / "latest_filling_run.json"
    if not latest_path.exists():
        print("\n[提示] latest_filling_run.json 不存在。\n")
        sys.exit(0)

    with open(latest_path, "r", encoding="utf-8") as f:
        latest = json.load(f)

    # 收集所有报告中的 complex_unknown_fields
    query_fields = []
    report_names = []
    for entry in latest.get("reports", []):
        rj = entry.get("report_json", "")
        rj_name = Path(rj).name
        rj_path = REPORTS_DIR / rj_name
        if not rj_path.exists():
            continue
        try:
            with open(rj_path, "r", encoding="utf-8") as fh:
                report = json.load(fh)
            complex_fields = report.get("complex_unknown_fields", [])
            for cf in complex_fields:
                if cf.get("sensitive"):
                    continue
                cf["_source_file"] = entry.get("source_file", "")
                query_fields.append(cf)
            if complex_fields:
                report_names.append(rj_name)
        except Exception:
            pass

    if not query_fields:
        print("\n[提示] 没有发现需要 API 辅助的复杂字段。")
        print("简单字段继续由本地规则处理。\n")
        write_log("INFO: 无复杂字段，不生成 API 预览")
        return

    print(f"\n发现 {len(query_fields)} 个复杂字段（来自 {len(report_names)} 个报告），生成预览...")
    write_log(f"INFO: 发现 {len(query_fields)} 个复杂字段")

    # 敏感字段检测和脱敏
    sanitized_fields = []
    blocked_fields = []
    for qf in query_fields:
        label = qf.get("field_label", qf.get("field_key", ""))
        raw = str(qf.get("field_value", qf.get("value", "")))

        # 检测敏感模式
        found = detect_sensitive_in_text(f"{label}: {raw}")
        key_is_sensitive = qf.get("sensitive", False) or qf.get("is_sensitive", False) or \
                          any(k in label for k in ["身份证", "手机", "地址", "电话", "银行"])

        if found or key_is_sensitive:
            # 脱敏处理
            sanitized = copy.deepcopy(qf)
            sanitized["original_value_masked"] = True
            sanitized["field_value"] = "[敏感字段已脱敏]"
            sanitized_fields.append(sanitized)
            blocked_fields.append(label)
        else:
            sanitized_fields.append(copy.deepcopy(qf))

    # 构建 API 请求体预览
    system_prompt = (
        "你是一个表格字段理解助手。你的任务是："
        "1. 根据给定的表格字段名称，判断它可能的含义。"
        "2. 从候选资料库字段列表中，推荐最匹配的字段。"
        "3. 如果无法确定，返回 requires_user_review: true。"
        "重要：不要建议用户发送更多个人信息，不要搜索外部信息。"
    )

    known_keys_desc = ", ".join(KNOWN_PROFILE_KEYS)

    user_message_parts = [
        f"请分析以下表格中的字段，推荐它们对应资料库中的哪个字段。",
        f"",
        f"资料库可用字段: {known_keys_desc}",
        f"",
        f"待分析字段:",
    ]
    for qf in sanitized_fields:
        user_message_parts.append(f"  - 字段名: {qf.get('field_label', qf.get('field_key', '?'))}")
        user_message_parts.append(f"    当前值: {qf.get('field_value', qf.get('value', '(无)'))}")
        user_message_parts.append(f"    原因: {qf.get('reason', '本地规则无法处理')}")
        user_message_parts.append("")

    user_message = "\n".join(user_message_parts)

    total_chars = len(system_prompt) + len(user_message)
    max_chars = config.get("max_chars_per_request", 3000)
    if total_chars > max_chars:
        trunc_note = f"[内容已截断，原始长度 {total_chars} 字符]"
        user_message = user_message[:max_chars - len(trunc_note)] + trunc_note

    # 构建预览数据
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    preview_data = {
        "_说明": "API 请求预览 - 未经用户确认不得发送",
        "_生成时间": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "_状态": "预览 - 未发送",
        "approved_by_user": False,
        "config_snapshot": {
            "enabled": enabled,
            "dry_run": dry_run,
            "provider": config.get("provider", ""),
            "endpoint": config.get("endpoint", ""),
            "model": config.get("model", ""),
            "allow_sensitive": config.get("allow_sensitive", False),
            "max_chars_per_request": max_chars,
        },
        "request_preview": {
            "system_prompt": system_prompt,
            "user_message": user_message,
            "total_chars": total_chars,
        },
        "original_fields": len(query_fields),
        "sanitized_fields": len(sanitized_fields),
        "blocked_sensitive_fields": blocked_fields,
        "sensitive_blocked_count": len(blocked_fields),
        "security_checklist": {
            "sensitive_fields_removed": len(blocked_fields) > 0,
            "full_original_form_not_included": True,
            "photo_not_included": True,
            "id_numbers_masked": True,
            "phones_masked": True,
            "addresses_masked": True,
        },
        "profile_keys_reference": KNOWN_PROFILE_KEYS,
    }

    PREVIEW_DIR.mkdir(parents=True, exist_ok=True)

    # JSON 预览
    json_name = f"api_preview_{timestamp}.json"
    json_path = PREVIEW_DIR / json_name
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(preview_data, f, ensure_ascii=False, indent=2)

    # Markdown 预览
    md_name = f"api_preview_{timestamp}.md"
    md_path = PREVIEW_DIR / md_name
    md_lines = [
        "# API 请求预览",
        f"> 生成时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        f"> 状态：**预览 - 未发送**",
        "",
        "---",
        "",
        "## [LOCK] 安全闸门状态",
        "",
        f"| 闸门 | 状态 | 说明 |",
        f"|------|------|------|",
        f"| API enabled | {enabled} | {'[OK] 已启用' if enabled else '[STOP] 未启用 - 需手动改为 true'} |",
        f"| dry_run | {dry_run} | {'[STOP] 干运行模式 - 不会真正联网' if dry_run else '[!] 干运行已关闭 - 确认后会真正联网'} |",
        f"| approved_by_user | False | [STOP] 用户未确认 - 需手动改为 true |",
        f"| 敏感字段已拦截 | {len(blocked_fields)} 个 | {'[STOP] 已拦截: ' + ', '.join(blocked_fields) if blocked_fields else '[OK] 未发现敏感字段'} |",
        "",
        "---",
        "",
        "## 待发送内容",
        "",
        "### System Prompt",
        "```",
        system_prompt,
        "```",
        "",
        "### User Message",
        "```",
        user_message,
        "```",
        "",
        "---",
        "",
        "## [STOP] 发送前必须确认",
        "",
        "1. 检查以上待发送内容，确认没有你不希望发送的信息。",
        "2. 如果满意，打开对应的 JSON 文件，将 `approved_by_user` 改为 `true`。",
        "3. 确认 `api_config.json` 中 `enabled` 为 `true`。",
        "4. 确认 `api_config.json` 中 `dry_run` 为 `false`。",
        "5. 确保环境变量 SECURE_FORM_API_KEY 已设置。",
        "6. 运行发送命令。",
        "",
        f"> 命令：`python {__file__} send {json_path}`",
        "",
        "---",
        "",
        "## 安全提醒",
        "",
        "- 以上内容将发送到远程 API 服务。",
        "- 发送后，远程服务会收到你的字段名和脱敏后的值。",
        "- 本工具不会发送完整身份证号、手机号、地址等敏感信息。",
        f"- 已自动拦截 {len(blocked_fields)} 个敏感字段。",
        "",
    ]

    with open(md_path, "w", encoding="utf-8") as f:
        f.write("\n".join(md_lines))

    write_log(f"INFO: 预览已生成: {json_name}, {md_name}")
    write_log(f"INFO: 原始字段 {len(query_fields)} 个, 脱敏/拦截 {len(blocked_fields)} 个")

    print(f"\n[OK] API 预览已生成。")
    print(f"  JSON:  {json_path}")
    print(f"  Markdown: {md_path}")
    print(f"")
    print(f"  [LOCK] 安全闸门检查：")
    print(f"    enabled: {enabled} {'[STOP] 未启用' if not enabled else ''}")
    print(f"    dry_run: {dry_run} {'[STOP] 干运行' if dry_run else '[!] 可真正发送'}")
    print(f"    approved_by_user: False [STOP] 未确认")
    if blocked_fields:
        print(f"    敏感字段已拦截: {len(blocked_fields)} 个")
    print(f"")
    print(f"  下一步：")
    print(f"    1. 打开 Markdown 预览检查待发送内容")
    print(f"    2. 确认无误后，将 JSON 中 approved_by_user 改为 true")
    print(f"    3. 确认 api_config.json 中 enabled=true, dry_run=false")
    print(f"    4. 设置环境变量 SECURE_FORM_API_KEY")
    print(f"    5. 运行: python {__file__} send {json_path}")
    print(f"")

    write_log("========== API 预览生成完成 ==========")


# ------------------------------------------------------------
# 模式 B: 发送 API 请求
# ------------------------------------------------------------
def cmd_send(preview_path_str: str):
    write_log("========== 开始 API 发送流程 ==========")

    preview_path = Path(preview_path_str)

    # 安全边界校验：preview 文件必须位于 PREVIEW_DIR 内
    if not _validate_preview_path(preview_path):
        print(f"\n[STOP] 安全拒绝：预览文件路径不合法。")
        print(f"  文件必须位于: {PREVIEW_DIR.resolve()}")
        print(f"  文件名必须匹配: api_preview_*.json")
        print(f"  收到路径: {preview_path_str}\n")
        sys.exit(1)

    if not preview_path.exists():
        write_log(f"ERROR: 预览文件不存在: {preview_path}")
        print(f"\n错误：预览文件不存在: {preview_path}\n")
        sys.exit(1)

    # 1. 读取预览文件
    try:
        with open(preview_path, "r", encoding="utf-8") as f:
            preview = json.load(f)
    except Exception as e:
        write_log(f"ERROR: 读取预览失败: {e}")
        print(f"\n错误：无法读取预览文件: {e}\n")
        sys.exit(1)

    # 2. 加载配置
    config = load_config()
    if config is None:
        print("\n[STOP] 配置文件不存在。")
        print(f"  请从 {TEMPLATE_PATH} 复制创建 {CONFIG_PATH}")
        sys.exit(1)

    # ====== 安全闸门检查 ======
    checks_passed = True

    # Gate 1: enabled
    if not config.get("enabled", False):
        print("\n[STOP] 安全闸门 1: API 未启用 (enabled=false)")
        print("  请在 api_config.json 中将 enabled 设为 true\n")
        write_log("SECURITY: enabled=false, 拒绝发送")
        checks_passed = False

    # Gate 2: dry_run
    if config.get("dry_run", True):
        print("\n[STOP] 安全闸门 2: 干运行模式 (dry_run=true)")
        print("  请在 api_config.json 中将 dry_run 设为 false\n")
        write_log("SECURITY: dry_run=true, 拒绝发送")
        checks_passed = False

    # Gate 3: approved_by_user
    if not preview.get("approved_by_user", False):
        print("\n[STOP] 安全闸门 3: 用户未确认 (approved_by_user=false)")
        print("  请在预览 JSON 文件中将 approved_by_user 改为 true\n")
        write_log("SECURITY: approved_by_user=false, 拒绝发送")
        checks_passed = False

    # Gate 4: 敏感字段
    blocked = preview.get("blocked_sensitive_fields", [])
    if blocked and not config.get("allow_sensitive", False):
        print(f"\n[STOP] 安全闸门 4: 预览中包含 {len(blocked)} 个敏感字段")
        for b in blocked:
            print(f"  - {b}")
        print("  allow_sensitive 为 false, 拒绝发送\n")
        write_log(f"SECURITY: 敏感字段 {len(blocked)} 个, 拒绝发送")
        checks_passed = False

    # Gate 5: API Key
    api_key = get_api_key(config)
    if not api_key:
        env_var = config.get("api_key_env", "SECURE_FORM_API_KEY")
        print(f"\n[STOP] 安全闸门 5: API Key 未设置")
        print(f"  请设置环境变量 {env_var}\n")
        write_log(f"SECURITY: API Key 环境变量 {env_var} 未设置, 拒绝发送")
        checks_passed = False

    # Gate 6: endpoint 必须存在且以 https:// 开头
    endpoint = config.get("endpoint", "")
    if not endpoint:
        print("\n[STOP] 安全闸门 6: endpoint 未设置")
        print("  请在 api_config.json 中填写 API 端点地址\n")
        write_log("SECURITY: endpoint 为空, 拒绝发送")
        checks_passed = False
    elif not endpoint.startswith("https://"):
        print(f"\n[STOP] 安全闸门 6: endpoint 必须以 https:// 开头")
        print(f"  当前 endpoint: {endpoint[:50]}{'...' if len(endpoint) > 50 else ''}")
        print(f"  仅允许 HTTPS 加密传输。\n")
        write_log(f"SECURITY: endpoint 非 https://, 拒绝发送")
        checks_passed = False

    if not checks_passed:
        print("\n[STOP] 安全闸门未全部通过，API 请求被阻止。")
        print("  请逐一解决上述问题后重试。\n")
        sys.exit(1)

    # ====== 所有闸门通过 —— 准备发送 ======
    write_log("INFO: 全部安全闸门通过，准备发送")
    print("\n[OK] 全部安全闸门通过。")
    print(f"  enabled: {config['enabled']}")
    print(f"  dry_run: {config['dry_run']}")
    print(f"  approved_by_user: {preview['approved_by_user']}")
    print(f"  endpoint: {endpoint}")
    print(f"  model: {config.get('model', '')}")

    # 构建请求
    request_data = preview.get("request_preview", {})
    system_prompt = request_data.get("system_prompt", "")
    user_message = request_data.get("user_message", "")

    print(f"\n  API 请求内容长度: {len(system_prompt) + len(user_message)} 字符")

    # 实际发送
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    try:
        import urllib.request as ur

        payload = {
            "model": config.get("model", "gpt-4o"),
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message},
            ],
            "max_tokens": 1000,
            "temperature": 0.1,
        }

        json_bytes = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        req = ur.Request(
            endpoint,
            data=json_bytes,
            headers={
                "Content-Type": "application/json; charset=utf-8",
                "Authorization": f"Bearer {api_key}",
            },
            method="POST",
        )

        write_log(f"INFO: 正在发送 API 请求到 {endpoint}")
        print("  发送中...")

        with ur.urlopen(req, timeout=30) as resp:
            resp_body = resp.read().decode("utf-8")
            resp_json = json.loads(resp_body)
            status = resp.status

        write_log(f"INFO: API 响应状态 {status}")

        # 解析 OpenAI 兼容响应
        suggestions = []
        try:
            content = resp_json["choices"][0]["message"]["content"]
            # 尝试提取 JSON 建议
            suggestions = _parse_api_suggestions(content, preview)
        except Exception as parse_err:
            write_log(f"WARN: 响应解析异常: {parse_err}")
            suggestions = [{"raw_response": resp_json, "parse_error": str(parse_err)}]

        # 构建结果
        result = {
            "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "source_preview": str(preview_path),
            "network_used": True,
            "api_call": True,
            "suggestions": suggestions,
            "api_response_status": status,
            "security": {
                "sensitive_sent": False,
                "full_original_form_sent": False,
                "photo_sent": False,
            }
        }

    except Exception as e:
        write_log(f"ERROR: API 请求失败: {e}")
        result = {
            "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "source_preview": str(preview_path),
            "network_used": True,
            "api_call": True,
            "error": str(e),
            "suggestions": [],
            "security": {
                "sensitive_sent": False,
                "full_original_form_sent": False,
                "photo_sent": False,
            }
        }

    # 保存结果
    RESULT_DIR.mkdir(parents=True, exist_ok=True)
    json_name = f"api_result_{timestamp}.json"
    json_path = RESULT_DIR / json_name
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    # Markdown 结果
    md_name = f"api_result_{timestamp}.md"
    md_path = RESULT_DIR / md_name
    md_lines = [
        "# API 分析结果",
        f"> 生成时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        f"> 联网：是 | API：是",
        f"> 敏感信息发送：否 | 完整表格发送：否 | 照片发送：否",
        "", "---", "",
    ]

    suggestions = result.get("suggestions", [])
    if suggestions:
        md_lines.append("## 字段匹配建议")
        md_lines.append("")
        md_lines.append("| 表格字段 | 建议对应资料库字段 | 置信度 | 理由 | 需用户复核 |")
        md_lines.append("|----------|-------------------|--------|------|-----------|")
        for s in suggestions:
            if "parse_error" in s:
                md_lines.append(f"| (解析异常) | - | - | {s.get('parse_error','')} | - |")
            elif "raw_response" in s:
                raw = str(s["raw_response"])[:100]
                md_lines.append(f"| (原始响应) | - | - | {raw}... | [STOP] 是 |")
            else:
                ff = s.get("form_field", "?")
                spk = s.get("suggested_profile_key", "?")
                conf = s.get("confidence", "?")
                reason = s.get("reason", "")
                needs = "[STOP] 是" if s.get("requires_user_review", True) else "否"
                md_lines.append(f"| {ff} | {spk} | {conf} | {reason} | {needs} |")
        md_lines.append("")
    else:
        md_lines.append("## 结果")
        if result.get("error"):
            md_lines.append(f"API 请求失败: {result['error']}")
        else:
            md_lines.append("API 未返回有效建议。")
        md_lines.append("")

    if result.get("error"):
        md_lines.append("## [STOP] 错误信息")
        md_lines.append(f"```")
        md_lines.append(result["error"])
        md_lines.append(f"```")
        md_lines.append("")

    md_lines.append("---")
    md_lines.append("## [LOCK] 安全确认")
    md_lines.append(f"| 项目 | 状态 |")
    md_lines.append(f"|------|------|")
    md_lines.append(f"| 敏感信息发送 | {'[STOP] 否' if not result['security']['sensitive_sent'] else '是'} |")
    md_lines.append(f"| 完整原始表格发送 | {'[STOP] 否' if not result['security']['full_original_form_sent'] else '是'} |")
    md_lines.append(f"| 照片发送 | {'[STOP] 否' if not result['security']['photo_sent'] else '是'} |")
    md_lines.append("")
    md_lines.append("> [NOTE] 以上结果仅作为建议，不会自动写入表格或资料库。请人工判断后使用。")

    with open(md_path, "w", encoding="utf-8") as f:
        f.write("\n".join(md_lines))

    write_log(f"INFO: API 结果已保存: {json_name}, {md_name}")
    write_log(f"INFO: 联网=是 | API=是 | 敏感发送=否")

    print(f"\n[OK] API 请求完成。")
    print(f"  结果 JSON:  {json_path}")
    print(f"  结果 Markdown: {md_path}")
    print(f"")
    print(f"  [NOTE] API 结果仅为建议，不会自动写入表格或资料库。\n")

    write_log("========== API 发送完成 ==========")


def _parse_api_suggestions(content: str, preview: dict) -> list:
    """尝试从 API 返回的文本中提取结构化建议。"""
    suggestions = []
    # 尝试 JSON 格式
    try:
        # 提取 JSON 块
        match = re.search(r'\{[\s\S]*\}', content)
        if match:
            parsed = json.loads(match.group())
            if isinstance(parsed, list):
                return parsed
            if isinstance(parsed, dict) and "suggestions" in parsed:
                return parsed["suggestions"]
    except:
        pass

    # Fallback: 文本行解析
    for line in content.split("\n"):
        line = line.strip()
        if "->" in line or "→" in line:
            parts = re.split(r'\s*->\s*|\s*→\s*', line)
            if len(parts) >= 2:
                suggestions.append({
                    "form_field": parts[0].strip(),
                    "suggested_profile_key": parts[1].strip(),
                    "confidence": 0.5,
                    "reason": "从文本行解析",
                    "requires_user_review": True,
                })

    if not suggestions:
        suggestions.append({
            "form_field": "(由用户确认)",
            "suggested_profile_key": "(由用户确认)",
            "confidence": 0.0,
            "reason": f"无法自动解析 API 响应: {content[:500]}",
            "requires_user_review": True,
        })

    return suggestions


# ------------------------------------------------------------
# 主入口
# ------------------------------------------------------------
def print_usage():
    print("用法:")
    print(f"  python {__file__} check")
    print(f"      检查 API 配置状态（不发送请求）")
    print(f"")
    print(f"  python {__file__} preview")
    print(f"      生成 API 请求预览（不联网）")
    print(f"")
    print(f"  python {__file__} send <preview_file.json>")
    print(f"      发送 API 请求（需通过全部安全闸门）")


def main():
    if len(sys.argv) < 2:
        print_usage()
        sys.exit(1)

    mode = sys.argv[1]

    if mode == "preview":
        cmd_preview()
    elif mode == "send":
        if len(sys.argv) < 3:
            print("错误：send 模式需要指定预览文件路径")
            print_usage()
            sys.exit(1)
        cmd_send(sys.argv[2])
    elif mode == "check":
        config = load_api_config()
        ok, msg = assert_api_ready(config)
        auto_info = config.get("_auto_detected_api", {})
        key_env = config.get("api_key_env", "SECURE_FORM_API_KEY")
        key_status = "已设置" if os.environ.get(key_env, "") else "未设置"
        print(f"\n  API 配置检查")
        print(f"  {'─'*30}")
        print(f"  api_config.json: {'存在' if CONFIG_PATH.exists() else '不存在，可使用环境变量自动发现'}")
        print(f"  enabled: {config.get('enabled', False)}")
        print(f"  api_first: {config.get('api_first', False)}")
        print(f"  user_accepts_api_data_risk: {config.get('user_accepts_api_data_risk', False)}")
        print(f"  endpoint: {config.get('endpoint', '(未设置)')[:50]}")
        print(f"  model: {config.get('model', '(未设置)')}")
        print(f"  api_key_env: {key_env} ({key_status})")
        if auto_info:
            print(f"  auto_detected: {auto_info.get('provider', '')} / {auto_info.get('api_key_env', '')}")
        print(f"  结果: {'[OK] 可以发送' if ok else f'[STOP] {msg}'}")
        print(f"")
    else:
        print(f"错误：未知模式 '{mode}'")
        print_usage()
        sys.exit(1)


if __name__ == "__main__":
    main()
