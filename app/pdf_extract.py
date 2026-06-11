# -*- coding: utf-8 -*-
r"""
SafeFill PDF extraction module using MinerU CLI.
Extracts plain text from .pdf files in input_forms/ for use by ProfileExtract.
Does NOT modify original PDFs, does NOT send PDF binary to API, does NOT install MinerU.

MinerU detection priority:
  1. MINERU_EXE env var
  2. .venv_mineru\Scripts\mineru.exe (SafeFill isolated venv)
  3. .venv_mineru\Scripts\python.exe -m mineru
  4. System PATH mineru
"""
import os, sys, json, re, shutil, subprocess
from datetime import datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
INPUT_DIR = PROJECT_ROOT / "input_forms"
OUTPUT_DIR = PROJECT_ROOT / "pdf_extract_outputs"

MAX_CHARS = 30000


# ------------------------------------------------------------
# MinerU detection
# ------------------------------------------------------------
def _find_mineru_exe() -> str:
    """Find mineru executable. Returns path or empty string."""
    # 1. MINERU_EXE env var
    env_exe = os.environ.get("MINERU_EXE", "").strip()
    if env_exe and Path(env_exe).exists():
        return env_exe

    # 2. SafeFill isolated venv
    venv_exe = PROJECT_ROOT / ".venv_mineru" / "Scripts" / "mineru.exe"
    if venv_exe.exists():
        return str(venv_exe)

    # 3. Check venv python -m mineru
    venv_py = PROJECT_ROOT / ".venv_mineru" / "Scripts" / "python.exe"
    if venv_py.exists():
        return str(venv_py) + " -m mineru"

    # 4. System PATH
    mineru_path = shutil.which("mineru")
    if mineru_path:
        return mineru_path

    return ""


def check_mineru() -> tuple:
    """
    Check if MinerU CLI is available.
    Priority: MINERU_EXE > .venv_mineru > system PATH.
    Returns (available: bool, version: str, path: str, error: str).
    """
    exe = _find_mineru_exe()
    if not exe:
        return False, "", "", "MinerU not found. Install: .\\tools\\install_mineru.ps1"

    cmd = exe.split() + ["--version"]
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=30, cwd=str(PROJECT_ROOT))
        if r.returncode == 0:
            ver = (r.stdout + r.stderr).strip().split("\n")[0][:80]
            return True, ver, exe, ""
        return False, "", exe, f"MinerU exit {r.returncode}: {(r.stderr or r.stdout)[:200]}"
    except FileNotFoundError:
        return False, "", exe, f"Executable not found: {exe}"
    except Exception as e:
        return False, "", exe, f"Check failed: {e}"


# ------------------------------------------------------------
# PDF text extraction via MinerU
# ------------------------------------------------------------
def extract_pdf(pdf_path: Path, mineru_available: bool = None) -> dict:
    """
    Extract text from a single PDF via MinerU.
    Returns meta dict with extracted_text, success, error, etc.
    """
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    stem = pdf_path.stem
    work_dir = OUTPUT_DIR / f"{stem}_pdf_{ts}"
    result = {
        "source_pdf": str(pdf_path),
        "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "mineru_available": False,
        "mineru_path": "",
        "command": "",
        "output_dir": str(work_dir),
        "extracted_text": "",
        "extracted_chars": 0,
        "truncated": False,
        "original_chars": 0,
        "success": False,
        "error": "",
    }

    if mineru_available is None:
        mineru_available, _, mineru_path, _ = check_mineru()
    else:
        mineru_path = _find_mineru_exe()
    result["mineru_available"] = mineru_available
    result["mineru_path"] = mineru_path

    if not mineru_available:
        result["error"] = "MinerU not installed"
        return result

    work_dir.mkdir(parents=True, exist_ok=True)

    # Use detected mineru path instead of hardcoded "mineru"
    if mineru_path:
        cmd = mineru_path.split() + ["-p", str(pdf_path), "-o", str(work_dir), "-b", "pipeline"]
    else:
        cmd = ["mineru", "-p", str(pdf_path), "-o", str(work_dir), "-b", "pipeline"]
    result["command"] = " ".join(cmd)

    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=300, cwd=str(PROJECT_ROOT))
        if r.returncode != 0:
            result["error"] = f"MinerU exit {r.returncode}: {(r.stderr or r.stdout)[:500]}"
            return result

        # Collect all text from MinerU output
        text_parts = []
        for root, dirs, files in os.walk(str(work_dir)):
            for fname in files:
                fpath = Path(root) / fname
                if fpath.suffix.lower() in (".md", ".txt"):
                    try:
                        text = fpath.read_text(encoding="utf-8")
                        text_parts.append(text)
                    except Exception:
                        pass

        full_text = "\n\n".join(text_parts)
        result["original_chars"] = len(full_text)
        result["success"] = True

        # Truncate if needed
        if len(full_text) > MAX_CHARS:
            result["truncated"] = True
            full_text = full_text[:MAX_CHARS]
        result["extracted_text"] = full_text
        result["extracted_chars"] = len(full_text)

        # Write extracted_text.txt
        txt_path = work_dir / "extracted_text.txt"
        txt_path.write_text(full_text, encoding="utf-8")

        # Write extract_meta.json
        meta_path = work_dir / "extract_meta.json"
        meta_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")

    except subprocess.TimeoutExpired:
        result["error"] = "MinerU timed out (>300s)"
    except Exception as e:
        result["error"] = str(e)

    return result


# ------------------------------------------------------------
# Read extracted text for API (called by extract_candidates.py)
# ------------------------------------------------------------
def get_extracted_text(pdf_path: Path, mineru_available: bool = None) -> tuple:
    """
    Public interface for extract_candidates.py.
    Returns (text: str, meta: dict).
    """
    meta = extract_pdf(pdf_path, mineru_available=mineru_available)
    return meta.get("extracted_text", ""), meta


# ------------------------------------------------------------
# CLI entry
# ------------------------------------------------------------
def main():
    print("\nSafeFill PDF Extraction (MinerU)")
    print("=" * 50)

    available, version, path, err = check_mineru()
    if not available:
        print(f"\n  MinerU not installed.")
        print(f"  {err}")
        print(f"\n  Install via: .\\tools\\install_mineru.ps1")
        print(f"  Or continue using .docx/.xlsx files.\n")
        return

    print(f"  MinerU: {version}")
    if path:
        print(f"  Path:    {path}")

    pdf_files = sorted(INPUT_DIR.glob("*.pdf")) if INPUT_DIR.exists() else []
    if not pdf_files:
        print(f"\n  No .pdf files found in {INPUT_DIR}")
        return

    print(f"\n  Found {len(pdf_files)} PDF file(s):")
    for pf in pdf_files:
        print(f"    - {pf.name}")

    print(f"\n  Extracting...")
    for pf in pdf_files:
        print(f"\n  Processing: {pf.name}")
        meta = extract_pdf(pf, mineru_available=available)
        if meta["success"]:
            print(f"    OK: {meta['extracted_chars']} chars"
                  f"{' (truncated from ' + str(meta['original_chars']) + ')' if meta['truncated'] else ''}")
            print(f"    Output: {meta['output_dir']}")
        else:
            print(f"    FAIL: {meta['error']}")

    print(f"\n  Done. Output in: {OUTPUT_DIR}\n")


if __name__ == "__main__":
    main()
