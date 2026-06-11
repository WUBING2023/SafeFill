# -*- coding: utf-8 -*-
"""
SafeFill-FormReview -- fill form + review in one step
Step 1: run fill_form_draft.py to generate draft and HTML preview
Step 2: background-launch review_server.py for browser review
"""
import os, sys, time, subprocess
from pathlib import Path
import urllib.request as _urllib

PROJECT_ROOT = Path(__file__).resolve().parent.parent
APP_DIR = PROJECT_ROOT / "app"
VAULT_DIR = PROJECT_ROOT / "vault"
NEW_FORMS_DIR = PROJECT_ROOT / "new_forms"
HTML_DIR = PROJECT_ROOT / "review_html"
REVIEW_URL = "http://127.0.0.1:8787"

def _reviewui_is_running() -> bool:
    """Check if ReviewUI is already serving on port 8787."""
    try:
        req = _urllib.Request(REVIEW_URL + "/api/health", method="GET")
        with _urllib.urlopen(req, timeout=2) as resp:
            return resp.status == 200
    except Exception:
        return False

def main():
    process_all = "--all" in sys.argv
    no_open = "--no-open" in sys.argv

    print("\n" + "=" * 55)
    print("  SafeFill-FormReview")
    print("=" * 55)
    print()
    print("  - Reads vault/profile.json")
    if process_all:
        print("  - Batch mode: processes ALL supported files in new_forms/")
    else:
        print("  - Default mode: only the latest file in new_forms/")
    print("  - If API-first is enabled, calls configured LLM for fill plan")
    print("  - Does NOT modify original files or vault")
    print()

    # Pre-check
    if not (VAULT_DIR / "profile.json").exists():
        print("[STOP] profile.json not found. Run SafeFill-ProfileSave first.\n")
        sys.exit(1)

    docx_files = list(NEW_FORMS_DIR.glob("*.docx"))
    xlsx_files = list(NEW_FORMS_DIR.glob("*.xlsx"))
    if not docx_files and not xlsx_files:
        print("[STOP] No .docx or .xlsx files in new_forms/. Add a new form first.\n")
        sys.exit(1)

    print(f"  Vault: profile.json")
    print(f"  New forms: {len(docx_files) + len(xlsx_files)} file(s)")
    if len(docx_files) + len(xlsx_files) > 1 and not process_all:
        print(f"  Hint: use --all to process all files\n")

    # Step 1: DraftFill (foreground -- must complete before review)
    print("-" * 40)
    print(f"  Step 1/2: Generate draft and HTML preview{' [ALL]' if process_all else ' (latest only)'}")
    print("-" * 40)
    draft_script = str(APP_DIR / "fill_form_draft.py")
    draft_args = [sys.executable, draft_script]
    if process_all:
        draft_args.append("--all")
    result = subprocess.run(draft_args, capture_output=False)
    if result.returncode != 0:
        print("\n[STOP] DraftFill failed. ReviewUI will not start.\n")
        sys.exit(1)

    if not (HTML_DIR / "latest_review_html.json").exists():
        print("[WARN] latest_review_html.json not generated. ReviewUI may fall back to legacy mode.")

    # Step 2: ReviewUI (background launch)
    print(f"\n{'-'*40}")
    print(f"  Step 2/2: Start web review")
    print(f"{'-'*40}")

    if _reviewui_is_running():
        print(f"  ReviewUI is already running: {REVIEW_URL}/")
    else:
        review_script = str(APP_DIR / "review_server.py")
        args = [sys.executable, review_script]
        if no_open:
            args.append("--no-open")

        creationflags = 0
        if os.name == "nt":
            creationflags = subprocess.CREATE_NEW_PROCESS_GROUP

        try:
            subprocess.Popen(
                args,
                cwd=str(PROJECT_ROOT),
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                creationflags=creationflags,
            )
            time.sleep(2)
            if _reviewui_is_running():
                print(f"  ReviewUI started in background: {REVIEW_URL}/")
            else:
                print(f"  [WARN] ReviewUI may not have started. Run manually: python app\\review_server.py")
        except Exception as e:
            print(f"  [WARN] Failed to start ReviewUI: {e}")
            print(f"  Run manually: python app\\review_server.py")

    # Done
    print(f"\n{'='*55}")
    print(f"  FormReview complete.")
    print(f"  ReviewUI: {REVIEW_URL}/")
    print(f"  Check the form in your browser and click <Save Review Result>.")
    print(f"  After saving, next step: python D:\\SafeFill\\app\\export_final.py")
    print(f"{'='*55}\n")

if __name__ == "__main__":
    main()
