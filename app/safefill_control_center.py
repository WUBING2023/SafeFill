# -*- coding: utf-8 -*-
r"""
SafeFill-ControlCenter — 本地网页工作台
绑定 127.0.0.1:8790，提供状态查看和主流程按钮。
所有操作在 D:\SafeFill\ 内执行，不联网，不修改 vault。
"""
import os, sys, json, subprocess, datetime, threading, time, webbrowser, uuid
from pathlib import Path
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs

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
    if not should_open_browser(RUNS_DIR, lock_name):
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

PROJECT = Path(__file__).resolve().parent.parent
WEB_DIR = PROJECT / "app" / "web_control"
RUNS_DIR = PROJECT / "control_runs"
HOST = "127.0.0.1"

ALLOWED_ACTIONS = {
    "project_guard":    ["python", str(PROJECT / "app" / "project_guard.py")],
    "profile_extract":  ["python", str(PROJECT / "app" / "extract_candidates.py")],
    "profile_save":     ["python", str(PROJECT / "app" / "save_confirmed_profile.py")],
    "profile_save_detect":  ["python", str(PROJECT / "app" / "save_confirmed_profile.py"), "save", "--choice", "detect"],
    "profile_save_replace": ["python", str(PROJECT / "app" / "save_confirmed_profile.py"), "save", "--choice", "replace"],
    "profile_save_fill_empty": ["python", str(PROJECT / "app" / "save_confirmed_profile.py"), "save", "--choice", "fill-empty"],
    "profile_save_stop":  ["python", str(PROJECT / "app" / "save_confirmed_profile.py"), "save", "--choice", "stop"],
    "form_review":      ["python", str(PROJECT / "app" / "form_review.py")],
    "final_export":     ["python", str(PROJECT / "app" / "export_final.py")],
    "cleaner_preview":  ["python", str(PROJECT / "app" / "cleaner.py"), "preview"],
    "api_check":        ["python", str(PROJECT / "app" / "api_assist.py"), "check"],
}

jobs = {}

def get_status():
    s = {"api": {}, "vault": {}, "input_forms": {}, "new_forms": {}, "review_results": {}, "final_outputs": {}}
    try:
        with open(PROJECT / "app" / "api_config.json", "r", encoding="utf-8") as f:
            import json as _j; cfg = _j.load(f)
        s["api"] = {
            "enabled": cfg.get("enabled", False),
            "api_first": cfg.get("api_first", False),
            "user_risk": cfg.get("user_accepts_api_data_risk", False),
            "endpoint": (cfg.get("endpoint","") or "")[:60],
            "model": cfg.get("model",""),
            "key_env_set": bool(os.environ.get(cfg.get("api_key_env",""), "") or os.environ.get("OPENAI_API_KEY","")),
        }
    except: s["api"] = {"enabled": False, "api_first": False, "user_risk": False}

    vp = PROJECT / "vault" / "profile.json"
    s["vault"]["exists"] = vp.exists()
    s["vault"]["label"] = "已建立" if vp.exists() else "未建立"

    idir = PROJECT / "input_forms"
    ip_files = list(idir.glob("*")) if idir.exists() else []
    s["input_forms"]["count"] = len(ip_files)
    s["input_forms"]["latest"] = ip_files[-1].name if ip_files else ""
    # PDF / MinerU status
    pdf_count = len(list(idir.glob("*.pdf"))) if idir.exists() else 0
    s["input_forms"]["pdf_count"] = pdf_count
    mineru_ok = False
    mineru_path = ""
    try:
        from pdf_extract import check_mineru
        mineru_ok, _, mineru_path, _ = check_mineru()
    except Exception:
        pass
    s["pdf"] = {"mineru": "installed" if mineru_ok else "not_installed", "pdf_count": pdf_count, "path": mineru_path if mineru_ok else ""}
    s["capabilities"] = {
        "docx": ["paragraphs", "tables", "textboxes"],
        "xlsx": ["tables"],
        "pdf": ["extract_only", "needs_mineru"],
        "textbox_support": {"extract": True, "identify": True, "write_simple": True, "reviewui_show": True},
    }

    ndir = PROJECT / "new_forms"
    nw_files = list(ndir.glob("*")) if ndir.exists() else []
    s["new_forms"]["count"] = len(nw_files)
    s["new_forms"]["latest"] = nw_files[-1].name if nw_files else ""

    rr_dir = PROJECT / "review_results"
    rr_all = sorted(rr_dir.glob("review_result_*.json"), key=lambda f: f.stat().st_mtime, reverse=True) if rr_dir.exists() else []
    s["review_results"]["count"] = len(rr_all)
    s["review_results"]["latest"] = rr_all[0].name if rr_all else ""

    fo_dir = PROJECT / "final_outputs"
    fo_all = sorted(fo_dir.glob("*_最终版*"), key=lambda f: f.stat().st_mtime, reverse=True) if fo_dir.exists() else []
    s["final_outputs"]["count"] = len(fo_all)
    s["final_outputs"]["latest"] = fo_all[0].name if fo_all else ""
    return s


class Handler(BaseHTTPRequestHandler):
    def log_message(self, format, *args): pass

    def _send_json(self, data, status=200):
        body = json.dumps(data, ensure_ascii=False, indent=2).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _send_file(self, path, ct):
        try:
            with open(path, "rb") as f: content = f.read()
            self.send_response(200); self.send_header("Content-Type", ct)
            self.send_header("Content-Length", str(len(content)))
            self.end_headers(); self.wfile.write(content)
        except: self.send_error(404)

    def do_GET(self):
        p = urlparse(self.path)
        if p.path == "/": return self._send_file(WEB_DIR / "index.html", "text/html; charset=utf-8")
        if p.path == "/styles.css": return self._send_file(WEB_DIR / "styles.css", "text/css; charset=utf-8")
        if p.path == "/app.js": return self._send_file(WEB_DIR / "app.js", "application/javascript; charset=utf-8")
        if p.path == "/api/status": return self._send_json(get_status())
        if p.path == "/api/job":
            jid = parse_qs(p.query).get("id", [None])[0]
            return self._send_json(jobs.get(jid, {"error": "not found"}))
        return self._send_json({"error": "not found"}, 404)

    def do_POST(self):
        p = urlparse(self.path)

        # 新增：冲突检测端点（同步返回 JSON 给前端弹窗）
        if p.path == "/api/profile-save-detect":
            cl = int(self.headers.get("Content-Length", 0))
            body = json.loads(self.rfile.read(cl).decode("utf-8")) if cl > 0 else {}
            try:
                cmd = ALLOWED_ACTIONS["profile_save_detect"]
                r = subprocess.run(cmd, capture_output=True, text=True, timeout=60, cwd=str(PROJECT))
                stdout = r.stdout.strip()
                stderr = r.stderr.strip()
                # 提取最后一行 JSON（detect 函数通过 print(json.dumps(...)) 输出）
                lines = [l for l in stdout.split("\n") if l.strip().startswith("{")]
                if lines:
                    detect_result = json.loads(lines[-1])
                else:
                    detect_result = {"status": "error", "message": "无法解析检测结果", "stdout": stdout[-500:], "stderr": stderr[-500:]}
                return self._send_json(detect_result)
            except json.JSONDecodeError:
                return self._send_json({"status": "error", "message": "JSON 解析失败", "stdout": stdout[:500] if 'stdout' in dir() else ""}, 500)
            except Exception as e:
                return self._send_json({"status": "error", "message": str(e)}, 500)

        if p.path == "/api/run":
            cl = int(self.headers.get("Content-Length", 0))
            body = json.loads(self.rfile.read(cl).decode("utf-8")) if cl > 0 else {}
            action = body.get("action", "")
            if action not in ALLOWED_ACTIONS:
                return self._send_json({"error": f"未知操作: {action}"}, 400)
            jid = str(uuid.uuid4())[:8]
            ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            log_path = RUNS_DIR / f"run_{action}_{ts}.txt"
            jobs[jid] = {"id": jid, "action": action, "status": "running", "output": "", "log": str(log_path)}

            def _run():
                cmd = ALLOWED_ACTIONS[action]
                try:
                    r = subprocess.run(cmd, capture_output=True, text=True, timeout=300, cwd=str(PROJECT))
                    out = r.stdout + "\n" + r.stderr
                    jobs[jid]["output"] = out[-5000:]
                    jobs[jid]["status"] = "done" if r.returncode == 0 else "failed"
                except Exception as e:
                    jobs[jid]["output"] = str(e)
                    jobs[jid]["status"] = "error"
                with open(log_path, "w", encoding="utf-8") as f:
                    f.write(jobs[jid]["output"])

            threading.Thread(target=_run, daemon=True).start()
            return self._send_json({"job_id": jid, "status": "started"})
        return self._send_json({"error": "not found"}, 404)


def main():
    no_open = "--no-open" in sys.argv
    port = 8790
    for p in [8790, 8791, 8792]:
        try:
            srv = HTTPServer((HOST, p), Handler)
            port = p; break
        except OSError: continue
    url = f"http://{HOST}:{port}/"
    print(f"\n  SafeFill-ControlCenter")
    print(f"  {url}")
    print(f"  绑 127.0.0.1 | 不联网 | 白名单操作\n")
    if no_open:
        print(f"  请手动打开浏览器: {url}\n")
    else:
        open_browser_later(url, enabled=True, lock_name="browser_open_8790.lock")
        print(f"  已自动打开浏览器: {url}\n")
    try: srv.serve_forever()
    except KeyboardInterrupt: print("\n已停止。")

if __name__ == "__main__": main()
