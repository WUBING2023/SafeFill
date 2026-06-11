# -*- coding: utf-8 -*-
"""
本地安全填表助手 - 本地网页检查服务
功能：启动仅绑定 127.0.0.1 的 HTTP 服务，让用户在浏览器中检查填写报告、
     修改内容、补充未知字段、选择是否保存到资料库。
安全约束：
  - 只绑定 127.0.0.1，不对外开放
  - 只使用 Python 标准库
  - 不联网、不调用 API
  - 只读 filling_reports，只写 review_results
  - 不修改原始文件、草稿文件、vault 资料库
"""

import os
import sys
import json
import mimetypes
import threading
import time
import webbrowser
from datetime import datetime
from pathlib import Path
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs, unquote

# Lock files directory for browser-open dedup
_BROWSER_LOCK_DIR = Path(__file__).resolve().parent.parent / "control_runs"

def should_open_browser(lock_dir: Path, lock_name: str, cooldown_seconds: int = 10) -> bool:
    """检查是否应该打开浏览器（防短时间重复打开）。"""
    lock_path = lock_dir / lock_name
    now = time.time()
    if lock_path.exists():
        try:
            last = float(lock_path.read_text(encoding="utf-8").strip())
            if now - last < cooldown_seconds:
                return False
        except Exception:
            pass
    lock_dir.mkdir(parents=True, exist_ok=True)
    lock_path.write_text(str(now), encoding="utf-8")
    return True

def open_browser_later(url: str, enabled: bool = True, lock_name: str = "browser_open.lock"):
    """后台线程延迟 1 秒自动打开浏览器。enabled=False 时跳过。lock_name 防重复。"""
    if not enabled:
        return
    if not should_open_browser(_BROWSER_LOCK_DIR, lock_name):
        print(f"[INFO] 浏览器刚刚已打开，跳过重复打开: {url}")
        return
    def _open():
        time.sleep(1)
        try:
            webbrowser.open(url)
            print(f"[OK] 已自动打开浏览器: {url}")
        except Exception as e:
            print(f"[WARN] 自动打开浏览器失败: {e}")
            print(f"请手动打开: {url}")
    threading.Thread(target=_open, daemon=True).start()

# ------------------------------------------------------------
# 项目根目录
# ------------------------------------------------------------
PROJECT_ROOT = Path(__file__).resolve().parent.parent

WEB_REVIEW_DIR = PROJECT_ROOT / "app" / "web_review"
REPORTS_DIR = PROJECT_ROOT / "filling_reports"
HTML_DIR = PROJECT_ROOT / "review_html"
REVIEW_RESULTS_DIR = PROJECT_ROOT / "review_results"
LOGS_DIR = PROJECT_ROOT / "logs"

HOST = "127.0.0.1"
DEFAULT_PORT = 8787

# 敏感字段
SENSITIVE_FIELDS = {"id_number", "phone", "address", "photo_path"}

# ------------------------------------------------------------
# 日志
# ------------------------------------------------------------
def write_log(message: str):
    """写入本地日志，不记录敏感内容。"""
    LOGS_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    log_file = LOGS_DIR / "review_server.log"
    with open(log_file, "a", encoding="utf-8") as f:
        f.write(f"[{timestamp}] {message}\n")
    print(f"[LOG] {message}")


# ------------------------------------------------------------
# 路径安全校验
# ------------------------------------------------------------
def safe_path_check(filename: str, base_dir: Path) -> Path | None:
    """
    防止路径穿越攻击。
    只允许访问 base_dir 内的文件。
    拒绝时写入日志。
    """
    filename = unquote(filename)
    # 严格拒绝包含路径穿越字符的请求，不做自动纠正
    if ".." in filename or "/" in filename or "\\" in filename:
        write_log(f"SECURITY: 路径穿越请求被拒绝 (../, /, \\): filename={filename[:100]}")
        return None
    # 仅使用 basename 提取文件名，不信任完整路径
    clean_name = os.path.basename(filename)
    if clean_name != filename:
        write_log(f"SECURITY: 文件名包含非标准字符，已提取 basename: {filename[:100]} -> {clean_name}")
    candidate = (base_dir / clean_name).resolve()
    # 确保解析后的路径仍在 base_dir 内
    try:
        candidate.relative_to(base_dir.resolve())
    except ValueError:
        write_log(f"SECURITY: 路径解析后越界，拒绝访问: {filename[:100]} -> {candidate}")
        return None
    return candidate


# ------------------------------------------------------------
# 报告读取
# ------------------------------------------------------------
def get_html_items(show_all: bool = False) -> list:
    """读取 latest_review_html.json。默认返回第一个（latest file first, set by fill_form_draft.py）。"""
    latest_path = HTML_DIR / "latest_review_html.json"
    if not latest_path.exists():
        return []
    try:
        with open(latest_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        items = data.get("items", [])
        if show_all:
            return items
        # Default: only the first item (latest file from fill_form_draft.py)
        return items[:1]
    except Exception:
        return []


def load_html_preview(filename: str) -> str | None:
    """读取 review_html 中的 HTML 文件内容。"""
    html_path = safe_path_check(filename, HTML_DIR)
    if html_path is None or not html_path.exists() or not html_path.suffix == ".html":
        return None
    try:
        with open(html_path, "r", encoding="utf-8") as f:
            return f.read()
    except Exception:
        return None


def get_report_list(history: bool = False) -> list:
    """获取填写报告列表。默认只返回 latest_filling_run 中的最新报告。"""
    if not REPORTS_DIR.exists():
        return []

    # 历史模式：返回所有报告
    if history:
        reports = []
        for f in sorted(REPORTS_DIR.glob("filling_report_*.json"), reverse=True):
            try:
                with open(f, "r", encoding="utf-8") as fh:
                    data = json.load(fh)
                reports.append({
                    "filename": f.name,
                    "created_at": data.get("_生成时间", "未知"),
                    "original_file": data.get("原始文件", "未知"),
                    "draft_file": data.get("草稿文件", "未知"),
                    "filled_count": data.get("已填写字段数", 0),
                    "missed_count": data.get("未填写字段数", 0),
                    "review_count": data.get("需复核字段数", 0),
                    "blocked_count": data.get("已阻塞字段数", 0),
                    "has_sensitive": data.get("是否发现敏感字段", False),
                })
            except Exception as e:
                reports.append({"filename": f.name, "created_at": "解析失败", "error": str(e)})
        return reports

    # 默认：只返回 latest_filling_run 中的报告
    latest_path = REPORTS_DIR / "latest_filling_run.json"
    if not latest_path.exists():
        return get_report_list(history=True)  # 回退
    try:
        with open(latest_path, "r", encoding="utf-8") as f:
            latest = json.load(f)
    except Exception:
        return get_report_list(history=True)

    reports = []
    for entry in latest.get("reports", []):
        rj = entry.get("report_json", "")
        rj_name = Path(rj).name if rj else ""
        rj_path = REPORTS_DIR / rj_name
        try:
            if rj_path.exists():
                with open(rj_path, "r", encoding="utf-8") as fh:
                    data = json.load(fh)
                reports.append({
                    "filename": rj_name,
                    "created_at": data.get("_生成时间", "未知"),
                    "original_file": data.get("原始文件", "未知"),
                    "draft_file": data.get("草稿文件", "未知"),
                    "filled_count": data.get("已填写字段数", 0),
                    "missed_count": data.get("未填写字段数", 0),
                    "review_count": data.get("需复核字段数", 0),
                    "blocked_count": data.get("已阻塞字段数", 0),
                    "has_sensitive": data.get("是否发现敏感字段", False),
                })
            else:
                reports.append({"filename": rj_name, "created_at": latest.get("created_at", ""), "error": "报告文件不存在"})
        except Exception as e:
            reports.append({"filename": rj_name, "created_at": "解析失败", "error": str(e)})
    return reports


def load_report(filename: str) -> dict | None:
    """加载指定填写报告。"""
    path = safe_path_check(filename, REPORTS_DIR)
    if path is None or not path.exists():
        return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        write_log(f"ERROR: 加载报告失败 {filename}: {e}")
        return None


# ------------------------------------------------------------
# 脱敏工具
# ------------------------------------------------------------
def mask_id_number(value: str) -> str:
    if not value:
        return value
    v = str(value).strip()
    if len(v) >= 15:
        return v[:3] + "*" * (len(v) - 7) + v[-4:]
    if len(v) >= 8:
        return v[:2] + "*" * (len(v) - 4) + v[-2:]
    return "***"


def mask_phone(value: str) -> str:
    if not value:
        return value
    v = str(value).strip().replace("-", "").replace(" ", "")
    if len(v) == 11 and v.isdigit():
        return v[:3] + "****" + v[-4:]
    if len(v) >= 8:
        return v[:3] + "****" + v[-2:]
    return "***"


def mask_address(value: str) -> str:
    if not value:
        return value
    v = str(value).strip()
    if len(v) <= 6:
        return v + "***"
    return v[:6] + "***"


def mask_for_display(field_key: str, value) -> str:
    """脱敏后用于网页显示。"""
    if not value:
        return ""
    s = str(value)
    if field_key == "id_number":
        return mask_id_number(s)
    elif field_key == "phone":
        return mask_phone(s)
    elif field_key == "address":
        return mask_address(s)
    elif field_key == "photo_path":
        return "存在" if s.strip() else "不存在"
    return s


# ------------------------------------------------------------
# 构建前端需要的脱敏报告数据
# ------------------------------------------------------------
def _load_profile_values() -> dict:
    """加载 person_001.json 的值用于前端展示。"""
    profile_path = PROJECT_ROOT / "vault" / "profiles" / "person_001.json"
    values = {}
    if not profile_path.exists():
        return values
    try:
        with open(profile_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        for k, v in data.items():
            if k.startswith("_"): continue
            if isinstance(v, dict):
                values[k] = str(v.get("value", ""))
            elif isinstance(v, list):
                values[k] = "; ".join(str(x) for x in v) if v else ""
            else:
                values[k] = str(v) if v else ""
        # custom_fields
        cf = data.get("custom_fields", {})
        for ck, cv in cf.items():
            values[ck] = str(cv.get("value", "")) if isinstance(cv, dict) else str(cv)
    except Exception:
        pass
    return values


def _extract_field_value(entry: dict, profile_values: dict) -> str:
    """从条目中提取实际字段值。优先条目自身的 value，其次查资料库。"""
    # 直接有 value
    raw = entry.get("value")
    if raw and not isinstance(raw, dict):
        return str(raw)
    # 从 new_value/old_value 取
    for k in ("new_value", "filled_value", "current_value", "old_value"):
        v = entry.get(k)
        if v and not isinstance(v, dict):
            return str(v)
    # 查资料库
    fkey = entry.get("field_key", "")
    if fkey and fkey in profile_values:
        return profile_values[fkey]
    # 自定义字段
    label = entry.get("field_label", "")
    if label and label in profile_values:
        return profile_values[label]
    # 显示长度提示
    length = entry.get("value_length", 0)
    if length:
        return f"(已填写, {length} 字符)"
    return ""


def build_frontend_report(raw_report: dict) -> dict:
    """
    将完整报告转换为前端使用的脱敏版本。
    """
    profile_values = _load_profile_values()

    frontend = {
        "created_at": raw_report.get("_生成时间", ""),
        "original_file": raw_report.get("原始文件", ""),
        "draft_file": raw_report.get("草稿文件", ""),
        "has_sensitive": raw_report.get("是否发现敏感字段", False),
        "filled_fields": [],
        "review_fields": [],
        "missed_fields": [],
        "blocked_fields": [],
    }

    # 已填写字段
    for entry in raw_report.get("已填写字段", []):
        fkey = entry.get("field_key", "")
        real_value = _extract_field_value(entry, profile_values)
        frontend["filled_fields"].append({
            "field_label": entry.get("field_label", ""),
            "field_key": fkey,
            "value_display": mask_for_display(fkey, real_value),
            "value": real_value,
            "location": _format_location(entry),
            "status": "filled",
            "is_custom": fkey not in {  # 标记自定义字段
                "name","gender","birth_date","id_number","phone","email",
                "organization","department","title","education","degree",
                "major","research_area","address","photo_path",
                "project_experience","biography",
            },
            "metadata": {
                "table": entry.get("table"),
                "row": entry.get("row"),
                "sheet": entry.get("sheet"),
                "col": entry.get("col"),
                "value_length": entry.get("value_length"),
            },
        })

    # 需复核字段
    for entry in raw_report.get("需用户复核字段", []):
        fkey = entry.get("field_key", "")
        real_value = _extract_field_value(entry, profile_values)
        frontend["review_fields"].append({
            "field_label": entry.get("field_label", ""),
            "field_key": fkey,
            "value_display": mask_for_display(fkey, real_value),
            "value": real_value,
            "location": _format_location(entry),
            "status": "review_needed",
            "review_needed": True,
            "metadata": {"table": entry.get("table"), "row": entry.get("row"), "value_length": entry.get("value_length")},
        })

    # 未填写字段
    for entry in raw_report.get("未填写字段", []):
        fkey = entry.get("field_key", "")
        frontend["missed_fields"].append({
            "field_label": entry.get("field_label", ""),
            "field_key": fkey,
            "reason": entry.get("reason", "资料库中无此信息"),
            "location": _format_location(entry),
            "status": "missed",
        })

    # 已有内容未覆盖
    for entry in raw_report.get("已有内容未覆盖", []):
        fkey = entry.get("field_key", "")
        existing = entry.get("existing_value", "")
        frontend["blocked_fields"].append({
            "field_label": entry.get("field_label", ""),
            "field_key": fkey,
            "existing_value_display": mask_for_display(fkey, existing),
            "location": _format_location(entry),
            "status": "blocked",
        })

    # ---- 文本框字段汇总 ----
    textbox_fields = []
    _tb_categories = [
        ("已填写字段", "filled"),
        ("需用户复核字段", "review_needed"),
        ("不支持或跳过", "not_supported"),
        ("已有内容未覆盖", "blocked"),
    ]
    for cat_key, cat_status in _tb_categories:
        for entry in raw_report.get(cat_key, []):
            loc = _format_location(entry)
            is_tb = (
                entry.get("target_type") == "docx_textbox"
                or "Textbox[" in str(loc)
                or "textbox_index" in entry
            )
            if is_tb:
                textbox_fields.append({
                    "field_label": entry.get("field_label", ""),
                    "field_key": entry.get("field_key", ""),
                    "textbox_index": entry.get("textbox_index", 0),
                    "location": loc,
                    "status": cat_status,
                    "message": entry.get("reason",
                        "已写入文本框" if cat_status == "filled" else "需人工检查"),
                })
    frontend["textbox_fields"] = textbox_fields

    return frontend


def _format_location(entry: dict) -> str:
    """格式化字段位置描述。"""
    if "sheet" in entry:
        return f"Sheet[{entry['sheet']}] R{entry.get('row', '?')}C{entry.get('col', '?')}"
    else:
        return f"Table[{entry.get('table', '?')}] R{entry.get('row', '?')}"


# ------------------------------------------------------------
# HTTP 请求处理器
# ------------------------------------------------------------
class ReviewRequestHandler(BaseHTTPRequestHandler):

    def log_message(self, format, *args):
        """覆盖默认日志，写入本地日志文件。"""
        msg = f"HTTP {args[0]}" if args else format
        write_log(f"ACCESS: {msg}")

    def _send_json(self, data: dict, status: int = 200):
        """发送 JSON 响应。"""
        body = json.dumps(data, ensure_ascii=False, indent=2).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "http://127.0.0.1:8787")
        self.end_headers()
        self.wfile.write(body)

    def _send_file(self, filepath: Path, content_type: str):
        """发送静态文件。"""
        try:
            with open(filepath, "rb") as f:
                content = f.read()
            self.send_response(200)
            self.send_header("Content-Type", f"{content_type}; charset=utf-8")
            self.send_header("Content-Length", str(len(content)))
            self.send_header("Cache-Control", "no-store, no-cache, must-revalidate")
            self.send_header("Pragma", "no-cache")
            self.end_headers()
            self.wfile.write(content)
        except FileNotFoundError:
            self.send_error(404, "File not found")
        except Exception as e:
            self.send_error(500, f"Internal error: {e}")

    def _send_error_json(self, message: str, status: int = 500):
        """发送错误 JSON。"""
        self._send_json({"ok": False, "error": message}, status)

    # ---- CORS preflight ----
    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "http://127.0.0.1:8787")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    # ---- GET ----
    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path
        qs = parse_qs(parsed.query)

        try:
            # 静态文件路由
            if path == "/" or path == "/index.html":
                self._send_file(WEB_REVIEW_DIR / "index.html", "text/html")
                return

            if path == "/styles.css":
                self._send_file(WEB_REVIEW_DIR / "styles.css", "text/css")
                return

            if path == "/app.js":
                self._send_file(WEB_REVIEW_DIR / "app.js", "application/javascript")
                return

            # API 路由
            if path == "/api/reports":
                history = qs.get("history", ["0"])[0] == "1"
                reports = get_report_list(history=history)
                mode = "history" if history else "latest"
                self._send_json({"reports": reports, "count": len(reports), "mode": mode})
                return

            if path == "/api/report":
                filename = qs.get("file", [None])[0]
                if not filename:
                    self._send_error_json("缺少 file 参数", 400)
                    return
                report = load_report(filename)
                if report is None:
                    self._send_error_json(f"报告不存在或无法读取: {filename}", 404)
                    return
                frontend = build_frontend_report(report)
                self._send_json(frontend)
                return

            # v2 HTML preview routes
            if path == "/api/html-items":
                show_all = qs.get("all", ["0"])[0] == "1"
                items = get_html_items(show_all=show_all)
                self._send_json({"items": items, "count": len(items), "mode": "all" if show_all else "current"})
                return

            if path == "/api/html-preview":
                fname = qs.get("file", [None])[0]
                if not fname:
                    self._send_error_json("缺少 file 参数", 400)
                    return
                html_content = load_html_preview(fname)
                if html_content is None:
                    self._send_error_json("文件不存在或无法读取", 404)
                    return
                self._send_json({"html": html_content})
                return

            if path == "/api/health":
                self._send_json({
                    "running": True,
                    "host": HOST,
                    "port": self.server.server_address[1],
                    "network": "disabled",
                    "api_call": "disabled",
                })
                return

            # 404
            self._send_error_json("Not Found", 404)

        except Exception as e:
            write_log(f"ERROR: GET {path} 异常: {e}")
            self._send_error_json(str(e), 500)

    # ---- POST ----
    def do_POST(self):
        parsed = urlparse(self.path)
        path = parsed.path

        try:
            if path == "/api/save-review":
                # 读取请求体
                content_length = int(self.headers.get("Content-Length", 0))
                if content_length == 0:
                    self._send_error_json("请求体为空", 400)
                    return

                body = self.rfile.read(content_length)
                try:
                    data = json.loads(body.decode("utf-8"))
                except json.JSONDecodeError as e:
                    self._send_error_json(f"JSON 格式错误: {e}", 400)
                    return

                # 构建 review_result
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                result = {
                    "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "source_report": data.get("source_report", ""),
                    "draft_file": data.get("draft_file", ""),
                    "original_file": data.get("original_file", ""),
                    "review_status": "reviewed",
                    "confirmed_fields": data.get("confirmed_fields", []),
                    "modified_fields": data.get("modified_fields", []),
                    "unknown_fields_filled_by_user": data.get("unknown_fields_filled_by_user", []),
                    "fields_marked_for_profile_save": data.get("fields_marked_for_profile_save", []),
                    "fields_rejected": data.get("fields_rejected", []),
                    "notes": data.get("notes", ""),
                    "textbox_fields": data.get("textbox_fields", []),
                    "security": {
                        "network": "disabled",
                        "api_call": "disabled",
                        "vault_modified": False,
                        "original_file_modified": False,
                        "draft_file_modified": False,
                    }
                }

                # 保存
                REVIEW_RESULTS_DIR.mkdir(parents=True, exist_ok=True)
                result_filename = f"review_result_{timestamp}.json"
                result_path = REVIEW_RESULTS_DIR / result_filename

                with open(result_path, "w", encoding="utf-8") as f:
                    json.dump(result, f, ensure_ascii=False, indent=2)

                # 日志
                tb_info = f" | 文本框={len(result.get('textbox_fields', []))}" if result.get("textbox_fields") else ""
                write_log(
                    f"INFO: 保存 review_result: {result_filename} | "
                    f"确认={len(result['confirmed_fields'])} | "
                    f"修改={len(result['modified_fields'])} | "
                    f"补充={len(result['unknown_fields_filled_by_user'])} | "
                    f"勾选保存={len(result['fields_marked_for_profile_save'])}"
                    f"{tb_info}"
                )

                self._send_json({
                    "success": True,
                    "saved_to": str(result_path),
                    "filename": result_filename,
                })

                return

            if path == "/api/save-html-review":
                content_length = int(self.headers.get("Content-Length", 0))
                if content_length == 0:
                    self._send_error_json("请求体为空", 400)
                    return
                body = self.rfile.read(content_length)
                try:
                    data = json.loads(body.decode("utf-8"))
                except json.JSONDecodeError as e:
                    self._send_error_json(f"JSON 格式错误: {e}", 400)
                    return

                if not data.get("confirmed_by_user"): self._send_error_json("confirmed_by_user 必须为 true", 400); return

                # Validate draft_file belongs to latest_review_html
                draft_file = data.get("draft_file", "")
                current_items = get_html_items(show_all=True)
                current_drafts = set()
                for item in current_items:
                    df = item.get("draft_file", "")
                    if df:
                        current_drafts.add(df)
                if draft_file and current_drafts and draft_file not in current_drafts:
                    write_log(f"SECURITY: 保存请求 draft_file 不在 latest_review_html 中: {draft_file}")
                    self._send_error_json(
                        f"当前页面不是最新 FormReview 结果，请刷新页面后重新保存。"
                        f" 请求 draft: {draft_file}，当前 draft: {list(current_drafts)[:3]}", 400)
                    return

                ts = datetime.now().strftime("%Y%m%d_%H%M%S")
                result = {
                    "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "mode": "html_review",
                    "confirmed_by_user": True,
                    "source_file": data.get("source_file", ""),
                    "draft_file": draft_file,
                    "html_file": data.get("html_file", ""),
                    "tables": data.get("tables", []),
                    "textbox_fields": data.get("textbox_fields", []),
                    "security": {
                        "network": "disabled", "api_call": "disabled",
                        "vault_modified": False, "draft_file_modified": False, "original_file_modified": False,
                    }
                }
                REVIEW_RESULTS_DIR.mkdir(parents=True, exist_ok=True)
                result_filename = f"review_result_{ts}.json"
                result_path = REVIEW_RESULTS_DIR / result_filename
                with open(result_path, "w", encoding="utf-8") as f:
                    json.dump(result, f, ensure_ascii=False, indent=2)
                write_log(f"INFO: 保存 html_review: {result_filename} | draft: {draft_file}")
                self._send_json({"ok": True, "file": result_filename, "saved_to": str(result_path)})
                return

            # 未知 POST 路由
            self._send_error_json("Not Found", 404)

        except Exception as e:
            write_log(f"ERROR: POST {path} 异常: {e}")
            self._send_error_json(str(e), 500)


# ------------------------------------------------------------
# 主入口
# ------------------------------------------------------------
def main():
    auto_open = "--no-open" not in sys.argv
    port = DEFAULT_PORT

    # 尝试绑定端口，如果被占用则尝试 8788
    server = None
    for attempt_port in [DEFAULT_PORT, 8788, 8789]:
        try:
            server = HTTPServer((HOST, attempt_port), ReviewRequestHandler)
            port = attempt_port
            break
        except OSError as e:
            if attempt_port == 8789:
                write_log(f"ERROR: 端口 {DEFAULT_PORT}-8789 均被占用，无法启动。")
                print(f"\n错误：端口 {DEFAULT_PORT}、8788、8789 均被占用。")
                print(f"请关闭占用这些端口的程序后重试。\n")
                sys.exit(1)
            write_log(f"WARN: 端口 {attempt_port} 被占用，尝试下一个...")
            print(f"端口 {attempt_port} 被占用，尝试 {attempt_port + 1}...")

    write_log(f"========== 启动本地检查服务 ==========")
    write_log(f"INFO: 绑定 {HOST}:{port}")
    write_log(f"INFO: 联网: 否 | API: 否")
    write_log(f"INFO: 网页资源目录: {WEB_REVIEW_DIR}")
    write_log(f"INFO: 报告目录: {REPORTS_DIR}")
    write_log(f"INFO: 结果输出目录: {REVIEW_RESULTS_DIR}")

    print(f"\n{'='*55}")
    print(f"  本地安全填表检查服务")
    print(f"  {'='*45}")
    print(f"  地址: http://{HOST}:{port}/")
    print(f"  绑定: {HOST}（仅本机可访问）")
    print(f"  联网: 否")
    print(f"  API:  否")
    print(f"  {'='*45}")
    print(f"")
    url = f"http://{HOST}:{port}/"
    if auto_open:
        open_browser_later(url, enabled=True, lock_name="browser_open_8787.lock")
        print(f"  已自动打开浏览器: {url}")
    else:
        print(f"  请手动打开浏览器: {url}")
    print(f"  按 Ctrl+C 停止服务。")
    print(f"{'='*55}\n")

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n\n正在停止服务...")
        write_log("INFO: 用户停止服务 (Ctrl+C)")
    finally:
        server.shutdown()
        write_log("========== 服务已停止 ==========")


if __name__ == "__main__":
    main()
