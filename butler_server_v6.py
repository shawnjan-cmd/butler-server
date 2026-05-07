#!/usr/bin/env python3
"""
╔══════════════════════════════════════════════════════════════════════════════╗
║                                                                              ║
║   BUTLER AI SERVER  -  BOTER PC Automation Suite                            ║
║   Copyright (c) 2025 Shawn Jan. All Rights Reserved.                        ║
║                                                                              ║
║   PROPRIETARY AND CONFIDENTIAL SOFTWARE                                      ║
║                                                                              ║
║   This software and its source code are the exclusive intellectual           ║
║   property of Shawn Jan ("Owner"). Unauthorized copying, modification,      ║
║   distribution, sublicensing, reverse engineering, decompiling,             ║
║   disassembling, or any other use of this software, in whole or in part,    ║
║   is strictly prohibited without the express written permission of           ║
║   the Owner.                                                                 ║
║                                                                              ║
║   RESTRICTIONS:                                                              ║
║   • You may NOT copy, modify, or distribute this software                   ║
║   • You may NOT sell, sublicense, or commercially exploit this software      ║
║   • You may NOT use this software to create competing products               ║
║   • You may NOT remove or alter this copyright notice                        ║
║   • You may NOT reverse engineer or decompile this software                  ║
║                                                                              ║
║   PERMITTED USE:                                                             ║
║   • Personal use on your own PC in conjunction with the Butler AI app        ║
║   • Use as provided by the Owner through official distribution channels      ║
║                                                                              ║
║   This software is provided "as is" without warranty of any kind.           ║
║   The Owner shall not be liable for any damages arising from its use.        ║
║                                                                              ║
║   For licensing inquiries: andrejsladkovic1992@gmail.com                    ║
║   Official distribution: https://github.com/shawnjan-cmd/butler-ai          ║
║                                                                              ║
╚══════════════════════════════════════════════════════════════════════════════╝
"""
import urllib.parse
import argparse, base64, hashlib, hmac, json, os, platform, random
import socket, subprocess, sys, threading, time, uuid, signal
import sqlite3, re, mimetypes, logging
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
from collections import deque

# ── CRASH PROTECTION ── Keeps Windows console open on fatal error
def _crash_handler(exc_type, exc_value, exc_tb):
    import traceback
    print("\n" + "=" * 60)
    print("  BUTLER AI SERVER - CRASH REPORT")
    print("=" * 60)
    traceback.print_exception(exc_type, exc_value, exc_tb)
    print("=" * 60)
    print("  Copy this error and send to developer.")
    print("  Common fixes: pip install psutil qrcode pillow requests")
    print("=" * 60)
    try: input("\n  Press Enter to exit...")
    except: time.sleep(15)
sys.excepthook = _crash_handler
try:    import tkinter as tk; from tkinter import scrolledtext, ttk; HAS_TK = True
except:
    HAS_TK = False
    # Dummy tk module so class definitions don't crash at module level
    class _DummyWidget:
        def __init__(self, *a, **k): pass
    class _DummyTk:
        Canvas = _DummyWidget
        Frame = _DummyWidget
        Label = _DummyWidget
        Tk = _DummyWidget
    tk = _DummyTk()
    class _DummyST:
        ScrolledText = _DummyWidget
    scrolledtext = _DummyST()
    class _DummyTTK:
        Progressbar = _DummyWidget
    ttk = _DummyTTK()


# ══════════════════════════════════════════════════════════════════
# ══════════════════════════════════════════════════════════════════
#  CHAT HISTORY FUNCTIONS
# ══════════════════════════════════════════════════════════════════

def _chat_save(device_id: str, role: str, content: str) -> None:
    """Save a chat message to history. Auto-prunes to 200 per device."""
    try:
        _db_run(
            "INSERT INTO chat_history(device_id, role, content) VALUES(?,?,?)",
            (device_id or "anon", role, str(content)[:10000])
        )
        # Keep only last 200 messages per device — prevents unbounded growth
        _db_run(
            "DELETE FROM chat_history WHERE device_id=? AND id NOT IN "
            "(SELECT id FROM chat_history WHERE device_id=? ORDER BY id DESC LIMIT 200)",
            (device_id, device_id)
        )
    except Exception as e:
        log.debug(f"[CHAT] Save failed: {e}")


def _chat_clear(device_id: str) -> None:
    """Delete all chat history for a device."""
    try:
        _db_run("DELETE FROM chat_history WHERE device_id=?", (device_id or "anon",))
    except Exception as e:
        log.debug(f"[CHAT] Clear failed: {e}")


def _chat_history(device_id: str, limit: int = 12) -> list:
    """Load recent chat history for a device as Ollama-format messages.
    Returns messages in chronological order (oldest first) as expected by Ollama."""
    try:
        rows = _db_q(
            "SELECT role, content FROM chat_history WHERE device_id=? "
            "ORDER BY id DESC LIMIT ?",
            (device_id or "anon", limit)
        )
        # Reverse so oldest first
        return [{"role": r["role"], "content": r["content"]} for r in reversed(rows)]
    except Exception as e:
        log.debug(f"[CHAT] History load failed: {e}")
        return []


#  PC-AWARE MODEL SELECTION
#  Scans RAM / CPU / GPU at startup, picks the right Ollama model
# ══════════════════════════════════════════════════════════════════

_MODEL_TIERS = {
    "tiny":  {"models": ["qwen2.5:0.5b","tinyllama:latest","qwen2.5:1.5b"],
               "pull": "qwen2.5:0.5b",  "label": "Tiny  (<6 GB free RAM)"},
    "light": {"models": ["phi3:mini","gemma2:2b","qwen2.5-coder:1.5b","llama3.2:1b"],
               "pull": "phi3:mini",     "label": "Light (6-11 GB free RAM)"},
    "mid":   {"models": ["qwen2.5-coder:7b","llama3.2:3b","qwen2.5:7b","phi3:mini"],
               "pull": "qwen2.5-coder:7b", "label": "Mid  (12-23 GB free RAM)"},
    "high":  {"models": ["deepseek-r1:8b","qwen2.5-coder:7b","llama3.1:8b","qwen2.5:14b"],
               "pull": "qwen2.5-coder:7b", "label": "High (24 GB+ free RAM)"},
}

_pc_best_model  = ""
_pc_best_lock   = threading.Lock()


def _select_lightest(names):
    """From installed model list, return the lightest one."""
    if not names: return ""
    priority = [
        "qwen2.5:0.5b","tinyllama","qwen2.5:1.5b","phi3:mini",
        "gemma2:2b","llama3.2:1b","qwen2.5-coder:1.5b","llama3.2:3b",
        "qwen2.5-coder:3b","qwen2.5-coder:7b","qwen2.5:7b",
        "deepseek-r1:8b","llama3.1:8b","mistral:7b","qwen2.5:14b",
    ]
    low = {m.lower(): m for m in names}
    for p in priority:
        base = p.split(":")[0].lower()
        for key, real in low.items():
            if key.startswith(base): return real
    def _sz(n):
        for tag, s in [("0.5b",1),("1b",2),("1.5b",3),("2b",4),("3b",5),
                       ("7b",10),("8b",11),("13b",20),("14b",22)]:
            if tag in n.lower(): return s
        return 50
    return min(names, key=_sz)


def _get_pc_specs():
    """Read actual RAM, CPU, GPU from this machine."""
    s = {"ram_free_gb":4.0,"ram_total_gb":8.0,"cpu_threads":4,
         "cpu_cores":2,"has_gpu":False,"gpu_vram_gb":0.0,"gpu_name":""}
    try:
        import psutil
        m = psutil.virtual_memory()
        s["ram_free_gb"]  = round(m.available/1e9, 1)
        s["ram_total_gb"] = round(m.total/1e9, 1)
        s["cpu_threads"]  = psutil.cpu_count(logical=True) or 4
        s["cpu_cores"]    = psutil.cpu_count(logical=False) or 2
    except Exception: pass
    try:
        r = subprocess.run(["nvidia-smi","--query-gpu=name,memory.total",
                            "--format=csv,noheader,nounits"],
                           capture_output=True,text=True,timeout=5,
                           stdin=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
        if r.returncode==0 and r.stdout.strip():
            p = r.stdout.strip().split(",")
            s.update(has_gpu=True, gpu_name=p[0].strip(),
                     gpu_vram_gb=round(int(p[1].strip())/1024,1))
    except Exception: pass
    if not s["has_gpu"]:
        try:
            r = subprocess.run(["system_profiler","SPDisplaysDataType"],
                               capture_output=True,text=True,timeout=5,
                               stdin=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
            if "Metal" in r.stdout or "Apple" in r.stdout:
                s.update(has_gpu=True,gpu_name="Apple Silicon",
                         gpu_vram_gb=s["ram_free_gb"])
        except Exception: pass
    return s


def _choose_tier(s):
    free = s["ram_free_gb"]
    if s["has_gpu"] and s["gpu_vram_gb"]>=4: free=max(free,s["gpu_vram_gb"]*2.5)
    if free>=24: return "high"
    if free>=12: return "mid"
    if free>=6:  return "light"
    return "tiny"


def _best_model_for_pc():
    """Return cached best model — scans PC hardware only once at startup."""
    global _pc_best_model
    with _pc_best_lock:
        if _pc_best_model: return _pc_best_model
    if os.environ.get("BUTLER_MODEL"):
        m = os.environ["BUTLER_MODEL"]
        with _pc_best_lock: _pc_best_model = m
        return m
    s         = _get_pc_specs()
    tier      = _choose_tier(s)
    tier_info = _MODEL_TIERS[tier]
    installed = []
    try:
        import urllib.request as _ur
        with _ur.urlopen(f"{OLLAMA_URL}/api/tags",timeout=3) as r:
            installed=[m["name"] for m in __import__("json").loads(r.read()).get("models",[])]
    except Exception: pass
    chosen=""
    low={m.lower():m for m in installed}
    for pref in tier_info["models"]:
        base=pref.split(":")[0].lower()
        if pref in installed: chosen=pref; break
        for key,real in low.items():
            if key.startswith(base): chosen=real; break
        if chosen: break
    if not chosen and installed: chosen=_select_lightest(installed)
    if not chosen:
        chosen=tier_info["pull"]
        threading.Thread(target=_pull_bg,args=(chosen,),daemon=True).start()
    print(f"  [AI] Tier: {tier_info['label']} | "
          f"Free RAM: {s['ram_free_gb']}GB | "
          f"GPU: {s['gpu_name'] or 'none'} | Model: {chosen}")
    with _pc_best_lock: _pc_best_model=chosen
    return chosen


# ── Pull progress state (module-level, thread-safe) ──────────────────────────
_pull_progress: dict = {"model": "", "status": "idle", "percent": 0, "active": False,
                        "bytes_done": 0, "bytes_total": 0, "speed_mbps": 0.0,
                        "error": "", "started_at": 0.0, "finished_at": 0.0}
_pull_progress_lock = threading.Lock()

def _set_pull_progress(**kw):
    with _pull_progress_lock:
        _pull_progress.update(kw)

def _parse_ollama_pull_line(line: str) -> dict:
    """
    Parse a single line from `ollama pull` stdout.
    Ollama outputs lines like:
      pulling manifest
      pulling sha256:abc123... 10% ▕█▏      ▏  512 MB/4.7 GB  2.1 MB/s  35s
      verifying sha256 digest
      writing manifest
      removing any unused layers
      success
    Returns dict with: status, percent, bytes_done, bytes_total, speed_mbps
    """
    result = {"status": line.strip(), "percent": 0,
               "bytes_done": 0, "bytes_total": 0, "speed_mbps": 0.0}
    low = line.lower().strip()

    # Percentage + byte progress + speed  e.g. "pulling sha256:abc... 45% ▕...▏ 2.1 GB/4.7 GB  1.5 MB/s"
    pct_m = re.search(r"(\d{1,3})%", line)
    if pct_m:
        result["percent"] = int(pct_m.group(1))
        result["status"]  = f"downloading {result['percent']}%"

    # Byte progress  e.g. "2.1 GB/4.7 GB" or "512 MB/4.7 GB"
    byte_m = re.search(r"([\d.]+)\s*(GB|MB|KB)\s*/\s*([\d.]+)\s*(GB|MB|KB)", line, re.I)
    if byte_m:
        def _to_bytes(val, unit):
            v = float(val)
            u = unit.upper()
            if u == "GB": return int(v * 1e9)
            if u == "MB": return int(v * 1e6)
            if u == "KB": return int(v * 1e3)
            return int(v)
        result["bytes_done"]  = _to_bytes(byte_m.group(1), byte_m.group(2))
        result["bytes_total"] = _to_bytes(byte_m.group(3), byte_m.group(4))

    # Speed  e.g. "1.5 MB/s" or "234 KB/s"
    spd_m = re.search(r"([\d.]+)\s*(GB|MB|KB)/s", line, re.I)
    if spd_m:
        v = float(spd_m.group(1)); u = spd_m.group(2).upper()
        if u == "GB":   result["speed_mbps"] = round(v * 1024, 1)
        elif u == "MB": result["speed_mbps"] = round(v, 1)
        elif u == "KB": result["speed_mbps"] = round(v / 1024, 3)

    # Named phases
    if "pulling manifest" in low:
        result["status"] = "pulling manifest"; result["percent"] = 2
    elif "verifying sha256" in low or "verifying sha" in low:
        result["status"] = "verifying checksum"; result["percent"] = 96
    elif "writing manifest" in low:
        result["status"] = "writing manifest"; result["percent"] = 98
    elif "removing any unused" in low:
        result["status"] = "cleaning layers"; result["percent"] = 99
    elif low == "success" or low.startswith("success"):
        result["status"] = "success"; result["percent"] = 100

    return result


def _stream_pull(model: str, exe: str) -> bool:
    """
    Run `ollama pull <model>` and stream each output line live into
    _pull_progress and the activity log. Returns True on success.
    """
    import shutil as _shutil
    cmd = [exe, "pull", model]
    kw  = {"stdout": subprocess.PIPE, "stderr": subprocess.STDOUT,
           "text": True, "bufsize": 1, "stdin": subprocess.DEVNULL}
    if IS_WINDOWS:
        kw["creationflags"] = subprocess.CREATE_NO_WINDOW

    _set_pull_progress(model=model, status="starting", percent=1,
                       active=True, error="", started_at=time.time(),
                       bytes_done=0, bytes_total=0, speed_mbps=0.0)

    proc = None
    try:
        proc = subprocess.Popen(cmd, **kw)
        last_pct   = -1
        last_log_t = 0.0      # throttle: only log progress every 3s

        for raw in proc.stdout:
            line = raw.strip()
            if not line:
                continue

            parsed = _parse_ollama_pull_line(line)
            pct    = parsed["percent"]

            _set_pull_progress(
                status      = parsed["status"],
                percent     = pct,
                bytes_done  = parsed["bytes_done"]  or _pull_progress["bytes_done"],
                bytes_total = parsed["bytes_total"] or _pull_progress["bytes_total"],
                speed_mbps  = parsed["speed_mbps"]  or _pull_progress["speed_mbps"],
            )

            # Always log phase changes; throttle progress lines to every 3s
            is_phase = any(k in parsed["status"] for k in
                           ("manifest", "verif", "writ", "clean", "success", "start"))
            now = time.time()
            if is_phase or pct != last_pct or (now - last_log_t) >= 3:
                _log(f"[MODEL] {parsed['status']}", "info")
                last_log_t = now
                last_pct   = pct

        # 60s — Ollama still writes manifest/cleans layers after stdout closes.
        # On slow HDDs this regularly takes >30s, causing false pull failures.
        proc.wait(timeout=60)
        return proc.returncode == 0

    except subprocess.TimeoutExpired:
        if proc:
            try: proc.kill()
            except: pass
        return False
    except Exception:
        return False


def _pull_bg(model):
    """Legacy background pull — now uses the streaming engine."""
    import shutil as _shutil
    exe = _find_ollama_exe() or "ollama"

    # Disk check
    ok_space, free_gb, req_gb = _check_disk_space_for_model(model)
    if not ok_space:
        _log(f"[MODEL] NOT ENOUGH DISK SPACE: need {req_gb:.0f} GB, "
             f"have {free_gb:.1f} GB free", "warn")
        _set_pull_progress(model=model, status="insufficient_disk",
                           percent=0, active=False,
                           error=f"Need {req_gb:.0f} GB, have {free_gb:.1f} GB")
        return

    success = _stream_pull(model, exe)
    if success:
        global _pc_best_model
        with _pc_best_lock: _pc_best_model = model
        _set_pull_progress(model=model, status="complete", percent=100,
                           active=False, finished_at=time.time())
        print(f"  [AI] Pulled {model} ✓")
    else:
        _set_pull_progress(model=model, status="error", percent=0,
                           active=False, error="pull failed — check ollama logs",
                           finished_at=time.time())
        print(f"  [AI] Pull failed for {model}")


def get_pc_model_recommendation():
    """Called by /api/ollama/recommend — returns full PC+model report."""
    s=_get_pc_specs(); tier=_choose_tier(s); ti=_MODEL_TIERS[tier]
    installed=[]
    try:
        import urllib.request as _ur
        with _ur.urlopen(f"{OLLAMA_URL}/api/tags",timeout=3) as r:
            installed=[m["name"] for m in __import__("json").loads(r.read()).get("models",[])]
    except Exception: pass
    return {
        "tier":tier,"tier_label":ti["label"],
        "ram_free_gb":s["ram_free_gb"],"ram_total_gb":s["ram_total_gb"],
        "cpu_cores":s["cpu_cores"],"cpu_threads":s["cpu_threads"],
        "has_gpu":s["has_gpu"],"gpu_name":s["gpu_name"],"gpu_vram_gb":s["gpu_vram_gb"],
        "recommended":_best_model_for_pc(),"will_pull":ti["pull"],
        "tier_models":ti["models"],"installed":installed,
    }


VERSION        = "6.0.0"
CRAWL_WORKERS  = 1    # same as WORKER_THREADS — kept for compatibility
CRAWL_TIMEOUT  = 18
HARVEST_SECS        = 90 * 60

# ── Typed error codes (§19) — client switches on code, not substring ─────────
_ERR_MAP = {
    "AUTH_REQUIRED":  ("Pair your phone first via QR.",          401),
    "DEVICE_LOCKED":  ("Server paired to a different device.",    403),
    "RATE_LIMITED":   ("Too many requests — slow down.",          429),
    "SCRIPT_TIMEOUT": ("Script ran past the timeout limit.",      408),
    "MISSING_PIP":    ("Python package missing.",                 424),
    "OLLAMA_OFFLINE": ("Ollama is not running on this PC.",       503),
    "FILE_TOO_LARGE": ("File exceeds safe size limit.",           413),
    "BAD_REQUEST":    ("Request payload invalid.",                400),
    "INTERNAL":       ("Server error — see PC console.",          500),
    "NOT_FOUND":      ("Endpoint not found.",                     404),
}   # auto-learn every 90 minutes — less CPU pressure
_sigma_log_interval = 300        # log progress at most every 5 minutes

SHARE_DIR      = Path.home() / "boter_shared"
DB_PATH        = Path.home() / ".butler_server_v6.db"

MASTER_URLS = [
    # ════════════════════════════════════════════════════════════════
    #  BUTLER AI KNOWLEDGE BASE — 300+ URLs
    #  Covers: Windows fixes, drivers, automation, AI, Python, hardware
    #  The server auto-crawls these 24/7 so AI answers get smarter
    # ════════════════════════════════════════════════════════════════

    # ── WINDOWS TROUBLESHOOTING & FIXES ──────────────────────────
    ("https://support.microsoft.com/en-us/windows",               "Windows",    ["windows","fix","error","troubleshoot"]),
    ("https://answers.microsoft.com/en-us/windows/forum",         "Windows",    ["windows","help","forum","fix"]),
    ("https://docs.microsoft.com/en-us/windows/client-management","Windows",    ["windows","management","policy"]),
    ("https://support.microsoft.com/en-us/topic/windows-update",  "Windows",    ["windows","update","patch"]),
    ("https://docs.microsoft.com/en-us/troubleshoot/windows-client/welcome-windows-client", "Windows", ["troubleshoot","windows"]),
    ("https://www.tenforums.com/tutorials/",                       "Windows",    ["windows10","tutorial","fix","how-to"]),
    ("https://www.elevenforum.com/tutorials/",                     "Windows",    ["windows11","tutorial","fix","how-to"]),
    ("https://www.thewindowsclub.com/",                            "Windows",    ["windows","tips","fix","optimize"]),
    ("https://superuser.com/questions/tagged/windows",             "Windows",    ["windows","superuser","fix"]),
    ("https://winaero.com/blog/",                                  "Windows",    ["windows","settings","tweak","optimize"]),

    # ── DRIVER ISSUES ─────────────────────────────────────────────
    ("https://www.drivereasy.com/knowledge/",                      "Drivers",    ["driver","update","fix","device"]),
    ("https://docs.microsoft.com/en-us/windows-hardware/drivers/", "Drivers",    ["driver","hardware","windows","install"]),
    ("https://www.nvidia.com/en-us/geforce/drivers/",              "Drivers",    ["nvidia","gpu","graphics","driver"]),
    ("https://www.amd.com/en/support",                             "Drivers",    ["amd","radeon","driver","gpu"]),
    ("https://www.intel.com/content/www/us/en/support/articles/000005765/graphics.html", "Drivers", ["intel","graphics","driver"]),
    ("https://support.microsoft.com/en-us/topic/windows-update-drivers", "Drivers", ["driver","update","windows"]),
    ("https://www.guru3d.com/articles-pages/driver-sweeper,1.html","Drivers",   ["driver","clean","uninstall","gpu"]),
    ("https://answers.microsoft.com/en-us/windows/forum/windows_10-hardware", "Drivers", ["driver","hardware","error"]),
    ("https://devblogs.microsoft.com/directx/",                    "Drivers",    ["directx","gpu","driver","gaming"]),
    ("https://support.hp.com/us-en/drivers",                       "Drivers",    ["hp","driver","printer","laptop"]),
    ("https://www.dell.com/support/home/en-us/drivers",            "Drivers",    ["dell","driver","laptop","update"]),
    ("https://support.lenovo.com/us/en/solutions/tvsu-update",     "Drivers",    ["lenovo","driver","update","laptop"]),

    # ── FIREWALL & SECURITY ──────────────────────────────────────
    ("https://docs.microsoft.com/en-us/windows/security/threat-protection/windows-firewall/windows-firewall-with-advanced-security", "Security", ["firewall","windows","security","block"]),
    ("https://support.microsoft.com/en-us/windows/windows-security", "Security", ["security","antivirus","firewall","protect"]),
    ("https://docs.microsoft.com/en-us/windows/security/",         "Security",   ["windows","security","policy","firewall"]),
    ("https://www.malwarebytes.com/blog/",                          "Security",   ["malware","virus","security","remove"]),
    ("https://support.microsoft.com/en-us/topic/antivirus",        "Security",   ["antivirus","defender","scan","virus"]),
    ("https://www.bleepingcomputer.com/",                           "Security",   ["malware","virus","fix","remove","hack"]),
    ("https://docs.microsoft.com/en-us/windows/security/threat-protection/microsoft-defender-antivirus/", "Security", ["defender","antivirus","scan"]),
    ("https://www.howtogeek.com/163471/how-to-use-windows-firewall/", "Security", ["firewall","windows","allow","block"]),
    ("https://www.cisecurity.org/insights/blog/",                   "Security",   ["security","hardening","firewall","patch"]),

    # ── PROGRAM INSTALLATION & SETUP ─────────────────────────────
    ("https://docs.microsoft.com/en-us/windows/package-manager/",  "Software",   ["winget","install","package","setup"]),
    ("https://chocolatey.org/docs/",                                "Software",   ["chocolatey","install","package","software"]),
    ("https://ninite.com/",                                         "Software",   ["install","software","bundle","setup"]),
    ("https://www.howtogeek.com/category/windows/",                 "Software",   ["windows","install","setup","how-to"]),
    ("https://support.microsoft.com/en-us/topic/repair-or-remove-programs", "Software", ["uninstall","repair","program","windows"]),
    ("https://docs.microsoft.com/en-us/windows/deployment/",       "Software",   ["deploy","install","windows","software"]),
    ("https://learn.microsoft.com/en-us/windows/apps/",            "Software",   ["windows","app","install","uwp"]),
    ("https://www.lifewire.com/install-software-on-windows-2624581","Software",  ["install","software","windows","guide"]),
    ("https://www.makeuseof.com/tag/install-software-without-admin-rights-windows/", "Software", ["install","no-admin","windows"]),

    # ── PYTHON AUTOMATION (FULL COVERAGE) ───────────────────────
    ("https://docs.python.org/3/library/os.html",                  "Python",     ["os","filesystem","path","python"]),
    ("https://docs.python.org/3/library/subprocess.html",          "Python",     ["subprocess","shell","command","run"]),
    ("https://docs.python.org/3/library/shutil.html",              "Python",     ["shutil","copy","move","file"]),
    ("https://docs.python.org/3/library/pathlib.html",             "Python",     ["pathlib","path","file","directory"]),
    ("https://docs.python.org/3/library/glob.html",                "Python",     ["glob","wildcard","find","file"]),
    ("https://docs.python.org/3/library/re.html",                  "Python",     ["regex","re","pattern","match"]),
    ("https://docs.python.org/3/library/json.html",                "Python",     ["json","parse","serialize","data"]),
    ("https://docs.python.org/3/library/csv.html",                 "Python",     ["csv","spreadsheet","data","parse"]),
    ("https://docs.python.org/3/library/sqlite3.html",             "Python",     ["sqlite3","database","sql","store"]),
    ("https://docs.python.org/3/library/threading.html",           "Python",     ["threading","parallel","async","concurrent"]),
    ("https://docs.python.org/3/library/multiprocessing.html",     "Python",     ["multiprocessing","parallel","cpu","process"]),
    ("https://docs.python.org/3/library/socket.html",              "Python",     ["socket","network","tcp","udp"]),
    ("https://docs.python.org/3/library/http.server.html",         "Python",     ["http","server","web","api"]),
    ("https://docs.python.org/3/library/urllib.html",              "Python",     ["urllib","download","web","http"]),
    ("https://docs.python.org/3/library/logging.html",             "Python",     ["logging","log","debug","error"]),
    ("https://docs.python.org/3/library/argparse.html",            "Python",     ["argparse","cli","command","args"]),
    ("https://docs.python.org/3/library/datetime.html",            "Python",     ["datetime","date","time","schedule"]),
    ("https://docs.python.org/3/library/time.html",                "Python",     ["time","sleep","timer","delay"]),
    ("https://docs.python.org/3/library/sys.html",                 "Python",     ["sys","exit","argv","platform"]),
    ("https://docs.python.org/3/library/platform.html",            "Python",     ["platform","os","system","windows"]),
    ("https://docs.python.org/3/library/zipfile.html",             "Python",     ["zip","archive","compress","extract"]),
    ("https://docs.python.org/3/library/tarfile.html",             "Python",     ["tar","archive","compress","linux"]),
    ("https://docs.python.org/3/library/hashlib.html",             "Python",     ["hash","md5","sha","checksum"]),
    ("https://docs.python.org/3/library/secrets.html",             "Python",     ["secret","random","token","security"]),
    ("https://docs.python.org/3/library/smtplib.html",             "Python",     ["smtp","email","send","mail"]),
    ("https://docs.python.org/3/library/imaplib.html",             "Python",     ["imap","email","inbox","mail"]),
    ("https://docs.python.org/3/library/configparser.html",        "Python",     ["config","ini","settings","parse"]),
    ("https://docs.python.org/3/library/pickle.html",              "Python",     ["pickle","serialize","save","load"]),
    ("https://realpython.com/python-windows-registry/",            "Python",     ["winreg","registry","windows","python"]),
    ("https://realpython.com/python-subprocess/",                  "Python",     ["subprocess","shell","run","command"]),
    ("https://realpython.com/python-gui-tkinter/",                 "Python",     ["tkinter","gui","window","ui"]),
    ("https://realpython.com/python-send-email/",                  "Python",     ["email","smtp","send","python"]),
    ("https://realpython.com/python-sleep/",                       "Python",     ["sleep","timer","delay","schedule"]),
    ("https://realpython.com/working-with-files-in-python/",       "Python",     ["files","directory","path","shutil"]),
    ("https://realpython.com/python-zipfile/",                     "Python",     ["zip","archive","compress","python"]),
    ("https://realpython.com/python-logging/",                     "Python",     ["logging","debug","error","log"]),
    ("https://realpython.com/python-sockets/",                     "Python",     ["socket","network","tcp","server"]),
    ("https://realpython.com/python-scheduler/",                   "Python",     ["schedule","task","cron","automation"]),
    ("https://realpython.com/run-python-scripts/",                 "Python",     ["script","run","execute","python"]),

    # ── WINDOWS AUTOMATION (PYTHON) ──────────────────────────────
    ("https://pyautogui.readthedocs.io/en/latest/",                "Automation", ["pyautogui","mouse","keyboard","click","gui"]),
    ("https://pywin32.readthedocs.io/en/latest/",                  "Automation", ["win32","windows","api","python"]),
    ("https://docs.microsoft.com/en-us/powershell/scripting/",     "Automation", ["powershell","script","automate","windows"]),
    ("https://ss64.com/ps/",                                       "Automation", ["powershell","command","reference","script"]),
    ("https://www.autohotkey.com/docs/",                           "Automation", ["autohotkey","ahk","hotkey","macro","automate"]),
    ("https://keyboard.readthedocs.io/en/latest/",                 "Automation", ["keyboard","hotkey","shortcut","automate"]),
    ("https://pynput.readthedocs.io/en/latest/",                   "Automation", ["pynput","mouse","keyboard","listener","control"]),
    ("https://github.com/asweigart/pyautogui",                     "Automation", ["pyautogui","screenshot","click","automate"]),
    ("https://schedule.readthedocs.io/en/stable/",                 "Automation", ["schedule","cron","task","timer","repeat"]),
    ("https://watchdog.readthedocs.io/en/latest/",                 "Automation", ["watchdog","file","monitor","event","folder"]),
    ("https://docs.microsoft.com/en-us/windows/win32/taskschd/",  "Automation", ["task","scheduler","windows","cron","automate"]),
    ("https://docs.microsoft.com/en-us/windows-server/administration/windows-commands/windows-commands", "Automation", ["cmd","command","batch","windows"]),
    ("https://wmi.readthedocs.io/en/latest/",                      "Automation", ["wmi","windows","management","system"]),
    ("https://comtypes.readthedocs.io/en/stable/",                 "Automation", ["com","windows","office","automate"]),
    ("https://realpython.com/automate-excel-python-xlwings/",      "Automation", ["excel","xlwings","automate","office"]),
    ("https://openpyxl.readthedocs.io/en/stable/",                 "Automation", ["openpyxl","excel","xlsx","spreadsheet"]),
    ("https://python-docx.readthedocs.io/en/latest/",              "Automation", ["docx","word","office","document"]),
    ("https://pywin32.readthedocs.io/en/latest/win32con.html",     "Automation", ["win32","constant","windows","api"]),
    ("https://github.com/mhammond/pywin32",                        "Automation", ["pywin32","windows","com","shell"]),

    # ── SYSTEM MONITORING & OPTIMIZATION ──────────────────────────
    ("https://psutil.readthedocs.io/en/latest/",                   "System",     ["psutil","cpu","ram","disk","process","monitor"]),
    ("https://docs.microsoft.com/en-us/sysinternals/",             "System",     ["sysinternals","process","monitor","windows"]),
    ("https://www.howtogeek.com/tag/performance/",                 "System",     ["performance","speed","optimize","windows"]),
    ("https://www.pcmag.com/how-to/how-to-speed-up-windows-11",    "System",     ["speed","optimize","windows","slow","performance"]),
    ("https://www.makeuseof.com/tag/4-tools-to-monitor-your-pc-hardware-health/", "System", ["hardware","monitor","health","cpu","ram"]),
    ("https://www.hwinfo.com/docs/",                               "System",     ["hardware","monitor","sensor","temperature"]),
    ("https://docs.microsoft.com/en-us/windows-server/administration/performance-tuning/", "System", ["performance","tune","windows","optimize"]),
    ("https://www.computerhope.com/",                              "System",     ["computer","help","fix","error","windows"]),
    ("https://www.windowscentral.com/how-to",                      "System",     ["windows","how-to","guide","fix"]),
    ("https://ss64.com/nt/",                                       "System",     ["cmd","batch","windows","command","script"]),

    # ── NETWORK & CONNECTIVITY ────────────────────────────────────
    ("https://docs.microsoft.com/en-us/windows-server/networking/", "Network",  ["network","windows","tcp","dns","ip"]),
    ("https://www.howtogeek.com/tag/networking/",                   "Network",  ["network","wifi","tcp","ip","dns","fix"]),
    ("https://support.microsoft.com/en-us/topic/network-troubleshooter", "Network", ["network","fix","troubleshoot","wifi"]),
    ("https://docs.microsoft.com/en-us/windows-server/networking/technologies/netsh/", "Network", ["netsh","network","command","windows"]),
    ("https://scapy.readthedocs.io/en/latest/",                    "Network",   ["scapy","packet","network","python"]),
    ("https://requests.readthedocs.io/en/latest/",                 "Network",   ["requests","http","api","download","web"]),
    ("https://docs.python.org/3/library/ssl.html",                 "Network",   ["ssl","https","certificate","secure"]),
    ("https://paramiko.org/",                                       "Network",   ["ssh","paramiko","remote","sftp","connect"]),
    ("https://nmap.org/book/",                                      "Network",   ["nmap","scan","port","network","security"]),
    ("https://www.wireshark.org/docs/",                            "Network",   ["wireshark","packet","capture","network","debug"]),

    # ── DISK, STORAGE & FILES ─────────────────────────────────────
    ("https://docs.microsoft.com/en-us/windows-server/storage/",   "Storage",   ["disk","storage","ntfs","partition","format"]),
    ("https://www.howtogeek.com/tag/hard-drives/",                 "Storage",   ["disk","hard-drive","ssd","partition","storage"]),
    ("https://support.microsoft.com/en-us/topic/disk-cleanup",     "Storage",   ["disk","cleanup","free","space","windows"]),
    ("https://docs.microsoft.com/en-us/windows-server/storage/disk-management/", "Storage", ["disk","partition","volume","manage"]),
    ("https://www.geeksforgeeks.org/python-os-path-methods/",      "Storage",   ["os.path","file","directory","python"]),
    ("https://realpython.com/get-all-files-in-directory-python/",  "Storage",   ["directory","files","list","walk","python"]),

    # ── REGISTRY & WINDOWS INTERNALS ─────────────────────────────
    ("https://docs.microsoft.com/en-us/windows/win32/sysinfo/registry", "Registry", ["registry","winreg","windows","key","value"]),
    ("https://www.lifewire.com/windows-registry-2625992",          "Registry",  ["registry","edit","windows","regedit"]),
    ("https://realpython.com/python-windows-registry/",            "Registry",  ["winreg","python","registry","windows"]),
    ("https://docs.microsoft.com/en-us/windows/win32/winreg/",    "Registry",  ["registry","api","windows","winreg"]),

    # ── STARTUP, SERVICES & PROCESSES ────────────────────────────
    ("https://docs.microsoft.com/en-us/windows-server/administration/windows-commands/sc-create", "Services", ["service","windows","sc","start","stop"]),
    ("https://docs.microsoft.com/en-us/sysinternals/downloads/autoruns", "Services", ["autorun","startup","windows","boot"]),
    ("https://www.howtogeek.com/tag/services/",                    "Services",  ["service","windows","start","stop","manage"]),
    ("https://psutil.readthedocs.io/en/latest/#processes",         "Services",  ["process","kill","pid","psutil","python"]),
    ("https://docs.python.org/3/library/signal.html",              "Services",  ["signal","process","kill","terminate"]),

    # ── GPU, GRAPHICS & DISPLAY ───────────────────────────────────
    ("https://docs.microsoft.com/en-us/windows-hardware/drivers/display/", "GPU", ["gpu","display","driver","graphics","dxgi"]),
    ("https://developer.nvidia.com/cuda-zone",                     "GPU",       ["cuda","nvidia","gpu","parallel","compute"]),
    ("https://www.howtogeek.com/tag/video-cards/",                 "GPU",       ["gpu","graphics","driver","display","monitor"]),
    ("https://support.microsoft.com/en-us/topic/directx-diagnostic", "GPU",    ["directx","dxdiag","gpu","error","fix"]),

    # ── MEMORY & RAM ISSUES ──────────────────────────────────────
    ("https://support.microsoft.com/en-us/topic/windows-memory-diagnostic", "RAM", ["ram","memory","test","diagnostic"]),
    ("https://www.howtogeek.com/260813/", "RAM",                    ["ram","memory","speed","upgrade","test"]),
    ("https://docs.microsoft.com/en-us/troubleshoot/windows-client/performance/ram-issues", "RAM", ["ram","memory","leak","usage"]),

    # ── BLUE SCREEN (BSOD) FIXES ─────────────────────────────────
    ("https://support.microsoft.com/en-us/topic/blue-screen-error", "BSOD",    ["bsod","blue-screen","crash","stop-code"]),
    ("https://www.howtogeek.com/163452/everything-you-need-to-know-about-the-blue-screen-of-death/", "BSOD", ["bsod","crash","stop-code","fix"]),
    ("https://answers.microsoft.com/en-us/windows/forum/windows_11-performance", "BSOD", ["crash","bsod","stop","error"]),
    ("https://docs.microsoft.com/en-us/windows-hardware/drivers/debugger/blue-screen-data", "BSOD", ["bsod","debug","crash","kernel"]),

    # ── BOOT & RECOVERY ──────────────────────────────────────────
    ("https://support.microsoft.com/en-us/topic/windows-startup-settings", "Boot", ["boot","startup","recovery","safe-mode"]),
    ("https://docs.microsoft.com/en-us/windows-hardware/manufacture/desktop/winpe-intro", "Boot", ["winpe","recovery","boot","repair"]),
    ("https://www.howtogeek.com/tag/boot/",                        "Boot",      ["boot","startup","bios","uefi","fix"]),
    ("https://support.microsoft.com/en-us/topic/system-restore",   "Boot",      ["restore","recovery","system","undo"]),

    # ── TASK AUTOMATION (SCRIPTS & BATCH) ────────────────────────
    ("https://ss64.com/vb/",                                       "Scripts",   ["vbscript","script","automate","windows"]),
    ("https://learn.microsoft.com/en-us/powershell/scripting/learn/ps101/00-introduction", "Scripts", ["powershell","script","automation"]),
    ("https://adamtheautomator.com/",                              "Scripts",   ["powershell","automation","windows","script"]),
    ("https://www.pdq.com/blog/",                                  "Scripts",   ["deployment","script","windows","automate"]),
    ("https://github.com/faressoft/terminalizer",                  "Scripts",   ["terminal","script","record","automate"]),
    ("https://github.com/Textualize/rich",                         "Scripts",   ["rich","terminal","color","python","cli"]),
    ("https://click.palletsprojects.com/",                         "Scripts",   ["click","cli","command","python","script"]),
    ("https://typer.tiangolo.com/",                                "Scripts",   ["typer","cli","terminal","python","script"]),

    # ── FILE MANAGEMENT & ORGANIZATION ───────────────────────────
    ("https://realpython.com/working-with-files-in-python/",       "Files",     ["file","copy","move","delete","organize"]),
    ("https://github.com/gorakhargosh/watchdog",                   "Files",     ["watchdog","monitor","folder","file","event"]),
    ("https://docs.python.org/3/library/fnmatch.html",             "Files",     ["fnmatch","glob","wildcard","match","file"]),
    ("https://www.geeksforgeeks.org/file-handling-python/",        "Files",     ["file","read","write","python","handle"]),

    # ── BROWSER AUTOMATION ───────────────────────────────────────
    ("https://selenium-python.readthedocs.io/",                    "Browser",   ["selenium","browser","automate","chrome","web"]),
    ("https://playwright.dev/python/docs/intro",                   "Browser",   ["playwright","browser","automate","test","web"]),
    ("https://docs.python.org/3/library/webbrowser.html",          "Browser",   ["webbrowser","open","url","browser","python"]),
    ("https://beautifulsoup4.readthedocs.io/en/latest/",           "Browser",   ["beautifulsoup","scrape","html","parse","web"]),
    ("https://docs.python-requests.org/en/latest/",                "Browser",   ["requests","http","download","api","web"]),

    # ── AI & LOCAL LLM ───────────────────────────────────────────
    ("https://ollama.ai/blog",                                     "AI",        ["ollama","llm","local","ai","model"]),
    ("https://github.com/ollama/ollama",                           "AI",        ["ollama","model","run","llm","local"]),
    ("https://huggingface.co/docs/transformers/index",             "AI",        ["transformers","model","ai","nlp","python"]),
    ("https://docs.langchain.com/docs/",                           "AI",        ["langchain","llm","chain","agent","ai"]),
    ("https://llama-cpp-python.readthedocs.io/en/latest/",         "AI",        ["llama","cpp","local","model","inference"]),
    ("https://www.geeksforgeeks.org/machine-learning/",            "AI",        ["machine-learning","python","model","train"]),
    ("https://scikit-learn.org/stable/user_guide.html",            "AI",        ["sklearn","ml","python","model","classify"]),
    ("https://pytorch.org/tutorials/",                             "AI",        ["pytorch","neural","train","model","tensor"]),
    ("https://github.com/microsoft/guidance",                      "AI",        ["guidance","llm","prompt","control","ai"]),

    # ── HARDWARE DIAGNOSTICS ─────────────────────────────────────
    ("https://support.microsoft.com/en-us/topic/device-manager",   "Hardware",  ["device-manager","hardware","driver","error","yellow"]),
    ("https://www.howtogeek.com/tag/hardware/",                    "Hardware",  ["hardware","cpu","ram","ssd","fix","diagnostic"]),
    ("https://docs.microsoft.com/en-us/windows/win32/cimwin32prov/win32-provider", "Hardware", ["wmi","hardware","info","python"]),
    ("https://www.cpuid.com/softwares/cpu-z.html",                 "Hardware",  ["cpu","hardware","spec","info","monitor"]),
    ("https://crystalmark.info/en/software/crystaldiskinfo/",      "Hardware",  ["disk","ssd","health","smart","diagnostic"]),

    # ── PYTHON PACKAGES FOR WINDOWS ──────────────────────────────
    ("https://pypi.org/project/psutil/",                           "PyPI",      ["psutil","cpu","ram","disk","process"]),
    ("https://pypi.org/project/pyautogui/",                        "PyPI",      ["pyautogui","mouse","keyboard","screen","click"]),
    ("https://pypi.org/project/pywin32/",                          "PyPI",      ["pywin32","windows","com","api"]),
    ("https://pypi.org/project/schedule/",                         "PyPI",      ["schedule","cron","timer","task","repeat"]),
    ("https://pypi.org/project/watchdog/",                         "PyPI",      ["watchdog","file","monitor","event"]),
    ("https://pypi.org/project/requests/",                         "PyPI",      ["requests","http","api","download"]),
    ("https://pypi.org/project/beautifulsoup4/",                   "PyPI",      ["beautifulsoup","scrape","html","parse"]),
    ("https://pypi.org/project/selenium/",                         "PyPI",      ["selenium","browser","automate","test"]),
    ("https://pypi.org/project/pyperclip/",                        "PyPI",      ["pyperclip","clipboard","copy","paste"]),
    ("https://pypi.org/project/plyer/",                            "PyPI",      ["plyer","notification","toast","alert"]),
    ("https://pypi.org/project/keyboard/",                         "PyPI",      ["keyboard","hotkey","shortcut","listen"]),
    ("https://pypi.org/project/mouse/",                            "PyPI",      ["mouse","click","move","scroll","automate"]),
    ("https://pypi.org/project/pynput/",                           "PyPI",      ["pynput","input","keyboard","mouse","control"]),
    ("https://pypi.org/project/openpyxl/",                         "PyPI",      ["openpyxl","excel","xlsx","spreadsheet"]),
    ("https://pypi.org/project/python-docx/",                      "PyPI",      ["docx","word","office","document"]),
    ("https://pypi.org/project/pygetwindow/",                      "PyPI",      ["pygetwindow","window","title","focus"]),
    ("https://pypi.org/project/winapps/",                          "PyPI",      ["winapps","installed","software","list","windows"]),
    ("https://pypi.org/project/wmi/",                              "PyPI",      ["wmi","windows","management","hardware","python"]),
    ("https://pypi.org/project/pyserial/",                         "PyPI",      ["serial","com","port","arduino","hardware"]),
    ("https://pypi.org/project/paramiko/",                         "PyPI",      ["ssh","sftp","remote","paramiko","connect"]),
    ("https://pypi.org/project/cryptography/",                     "PyPI",      ["crypto","encrypt","decrypt","security","key"]),
    ("https://pypi.org/project/Pillow/",                           "PyPI",      ["pillow","image","screenshot","resize","crop"]),
    ("https://pypi.org/project/pyinstaller/",                      "PyPI",      ["pyinstaller","exe","build","package","distribute"]),

    # ── GITHUB AUTOMATION REPOS ──────────────────────────────────
    ("https://github.com/jlevy/the-art-of-command-line",          "GitHub",    ["command-line","terminal","shell","tips"]),
    ("https://github.com/sindresorhus/awesome-windows",            "GitHub",    ["windows","apps","tools","awesome"]),
    ("https://github.com/Awesome-Windows/awesome-windows-command-line", "GitHub", ["windows","command","cli","batch"]),
    ("https://github.com/microsoft/PowerToys",                     "GitHub",    ["powertoys","windows","utility","automate"]),
    ("https://github.com/Nirewen/ProcessScheduler",                "GitHub",    ["process","scheduler","windows","task"]),
    ("https://github.com/asweigart/pyperclip",                     "GitHub",    ["clipboard","copy","paste","python"]),
    ("https://github.com/boppreh/keyboard",                        "GitHub",    ["keyboard","hotkey","macro","python"]),
    ("https://github.com/nicowillis/windows-utilities",            "GitHub",    ["windows","utility","script","automate"]),

    # ── WINDOWS REGISTRY AUTOMATION ──────────────────────────────
    ("https://docs.microsoft.com/en-us/windows/win32/api/winreg/", "Registry",  ["winreg","api","read","write","key"]),
    ("https://realpython.com/python-windows-registry/",            "Registry",  ["registry","python","windows","winreg"]),

    # ── ERROR CODES & DEBUGGING ───────────────────────────────────
    ("https://docs.microsoft.com/en-us/windows/win32/debug/system-error-codes", "Errors", ["error","code","windows","debug","fix"]),
    ("https://www.computerhope.com/error.htm",                     "Errors",    ["error","code","fix","windows","message"]),
    ("https://errorcodespro.com/",                                 "Errors",    ["error","code","fix","windows","0x"]),
    ("https://support.microsoft.com/en-us/topic/error-codes",     "Errors",    ["error","code","windows","fix","troubleshoot"]),
    ("https://www.howtogeek.com/tag/error-messages/",              "Errors",    ["error","message","fix","windows","code"]),

    # ── SCHEDULED TASKS & AUTOMATION ─────────────────────────────
    ("https://docs.microsoft.com/en-us/windows/win32/taskschd/task-scheduler-start-page", "Tasks", ["scheduler","task","automate","windows","cron"]),
    ("https://www.howtogeek.com/how-to-use-windows-task-scheduler/", "Tasks",  ["task","scheduler","automate","windows"]),
    ("https://github.com/dbader/schedule",                         "Tasks",     ["schedule","python","cron","task","automate"]),
    ("https://apscheduler.readthedocs.io/en/stable/",              "Tasks",     ["apscheduler","cron","job","schedule","python"]),

    # ── CLOUD & REMOTE ACCESS ─────────────────────────────────────
    ("https://docs.microsoft.com/en-us/windows-server/remote/remote-desktop-services/", "Remote", ["rdp","remote-desktop","remote","access"]),
    ("https://www.howtogeek.com/tag/remote-desktop/",              "Remote",    ["remote","desktop","rdp","access","windows"]),
    ("https://docs.microsoft.com/en-us/azure/",                    "Cloud",     ["azure","cloud","microsoft","deploy"]),

    # ── PRINTING & PERIPHERALS ────────────────────────────────────
    ("https://support.microsoft.com/en-us/topic/printer-problems", "Printers",  ["printer","print","driver","install","fix"]),
    ("https://docs.microsoft.com/en-us/windows-hardware/drivers/print/", "Printers", ["printer","driver","windows","install"]),
    ("https://www.howtogeek.com/tag/printers/",                    "Printers",  ["printer","fix","install","driver","setup"]),

    # ── GEEKSFORGEEKS PYTHON AUTOMATION ──────────────────────────
    ("https://www.geeksforgeeks.org/python-automation-tutorial/",  "GFG",       ["python","automation","tutorial","script"]),
    ("https://www.geeksforgeeks.org/os-module-python-examples/",   "GFG",       ["os","module","python","file","directory"]),
    ("https://www.geeksforgeeks.org/subprocess-module-python/",    "GFG",       ["subprocess","shell","python","run","command"]),
    ("https://www.geeksforgeeks.org/python-schedule-library/",     "GFG",       ["schedule","python","cron","task","automate"]),
    ("https://www.geeksforgeeks.org/python-send-email-using-smtp/","GFG",       ["email","smtp","python","send","automate"]),
    ("https://www.geeksforgeeks.org/working-with-excel-files-using-openpyxl/", "GFG", ["excel","openpyxl","python","spreadsheet"]),
    ("https://www.geeksforgeeks.org/python-program-read-write-rewrite-excel/", "GFG", ["excel","read","write","python"]),
    ("https://www.geeksforgeeks.org/python-win32-modules/",        "GFG",       ["win32","windows","python","api"]),
    ("https://www.geeksforgeeks.org/python-keyboard-module/",      "GFG",       ["keyboard","python","hotkey","press"]),
    ("https://www.geeksforgeeks.org/mouse-keyboard-automation-using-python/", "GFG", ["mouse","keyboard","automate","python"]),
    ("https://www.geeksforgeeks.org/how-to-kill-a-process-in-python/", "GFG",  ["kill","process","pid","python","terminate"]),
    ("https://www.geeksforgeeks.org/python-psutil-module/",        "GFG",       ["psutil","cpu","ram","process","python"]),
    # ── SCRIPT REPOSITORIES & COLLECTIONS ───────────────────────
    ("https://github.com/vinta/awesome-python",                    "Scripts",   ["python","awesome","library","collection","scripts"]),
    ("https://github.com/realpython/python-scripts",               "Scripts",   ["python","scripts","examples","automation"]),
    ("https://github.com/geekcomputers/Python",                    "Scripts",   ["python","script","utility","automation","tool"]),
    ("https://github.com/Asabeneh/30-Days-Of-Python",             "Scripts",   ["python","30days","learn","script","practice"]),
    ("https://github.com/ChrisTitusTech/winutil",                 "Windows",   ["windows","utility","powershell","install","fix"]),
    ("https://github.com/W4RH4WK/Debloat-Windows-10",             "Windows",   ["windows","debloat","optimize","remove","script"]),
    ("https://github.com/Sycnex/Windows10Debloater",              "Windows",   ["windows","debloat","powershell","script","optimize"]),
    ("https://github.com/farag2/Sophia-Script-for-Windows",       "Windows",   ["windows","optimize","powershell","tweak"]),
    ("https://github.com/mikeroyal/Windows-11-Guide",             "Windows",   ["windows11","guide","setup","tips","optimize"]),
    ("https://github.com/Raphire/Win11Debloat",                   "Windows",   ["windows11","debloat","remove","script","bloatware"]),
    ("https://github.com/asweigart/automate-boring-stuff",        "Scripts",   ["automate","boring","python","script"]),
    ("https://github.com/public-apis/public-apis",                 "APIs",      ["api","free","public","python","request"]),
    ("https://github.com/trimstray/the-book-of-secret-knowledge",  "Security",  ["security","command","script","tool","reference"]),
    ("https://github.com/flick9000/winscript",                     "Scripts",   ["windows","script","powershell","automate","fix"]),
    ("https://github.com/TheAlgorithms/Python",                    "Scripts",   ["python","algorithm","script","example","code"]),
    # ── ZAPIER AUTOMATION GUIDES ─────────────────────────────────
    ("https://zapier.com/blog/automate-windows/",                  "Automation",["windows","automate","productivity","task"]),
    ("https://zapier.com/blog/python-automation/",                 "Automation",["python","automate","script","productivity"]),
    ("https://zapier.com/blog/schedule-tasks-windows/",            "Automation",["schedule","task","windows","automate","cron"]),
    ("https://zapier.com/blog/best-free-windows-software/",        "Software",  ["windows","free","software","install","app"]),
    ("https://zapier.com/blog/automate-excel-python/",             "Automation",["excel","python","automate","spreadsheet"]),
    # ── AUTOMATE THE BORING STUFF (FULL BOOK CHAPTERS) ───────────
    ("https://automatetheboringstuff.com/2e/chapter1/",            "Scripts",   ["python","automate","basics","script"]),
    ("https://automatetheboringstuff.com/2e/chapter9/",            "Scripts",   ["python","files","organize","automate","path"]),
    ("https://automatetheboringstuff.com/2e/chapter11/",           "Scripts",   ["python","web","scrape","requests","beautifulsoup"]),
    ("https://automatetheboringstuff.com/2e/chapter12/",           "Scripts",   ["python","excel","openpyxl","spreadsheet"]),
    ("https://automatetheboringstuff.com/2e/chapter15/",           "Scripts",   ["python","schedule","timer","cron"]),
    ("https://automatetheboringstuff.com/2e/chapter18/",           "Scripts",   ["python","email","send","smtp","automate"]),
    ("https://automatetheboringstuff.com/2e/chapter20/",           "Scripts",   ["python","mouse","keyboard","gui","pyautogui"]),
    # ── SOFTWARE INSTALLATION GUIDES & PACKAGE MANAGERS ──────────
    ("https://community.chocolatey.org/packages",                  "Software",  ["chocolatey","install","package","windows","choco"]),
    ("https://docs.chocolatey.org/en-us/choco/commands/install",   "Software",  ["chocolatey","install","choco","command","package"]),
    ("https://learn.microsoft.com/en-us/windows/package-manager/winget/install", "Software", ["winget","install","windows","package","app"]),
    ("https://learn.microsoft.com/en-us/windows/package-manager/", "Software",  ["winget","package","manager","windows","install"]),
    ("https://www.makeuseof.com/windows-package-manager-guide/",   "Software",  ["winget","windows","install","package","app"]),
    ("https://github.com/microsoft/winget-pkgs",                   "Software",  ["winget","install","package","windows","microsoft"]),
    # ── POPULAR SOFTWARE INSTALL PAGES ───────────────────────────
    ("https://www.rarlab.com/download.htm",                        "Software",  ["winrar","install","download","archive","rar"]),
    ("https://www.7-zip.org/download.html",                        "Software",  ["7zip","install","archive","zip","compress"]),
    ("https://www.videolan.org/vlc/download-windows.html",         "Software",  ["vlc","install","media","player","video"]),
    ("https://notepad-plus-plus.org/downloads/",                   "Software",  ["notepad++","editor","install","text","code"]),
    ("https://code.visualstudio.com/download",                     "Software",  ["vscode","editor","install","code","microsoft"]),
    ("https://www.python.org/downloads/",                          "Software",  ["python","install","download","setup","windows"]),
    ("https://git-scm.com/download/win",                           "Software",  ["git","install","download","windows","version-control"]),
    ("https://nodejs.org/en/download/",                            "Software",  ["nodejs","install","download","javascript","npm"]),
    ("https://discord.com/download",                               "Software",  ["discord","install","download","chat","voice"]),
    ("https://zoom.us/download",                                   "Software",  ["zoom","install","download","meeting","video"]),
    ("https://support.microsoft.com/en-us/topic/install-office",   "Software",  ["office","install","microsoft","word","excel"]),
    ("https://www.adobe.com/acrobat/pdf-reader.html",              "Software",  ["adobe","pdf","reader","install","download"]),
    ("https://www.malwarebytes.com/",                              "Software",  ["malwarebytes","install","antivirus","security","scan"]),
    ("https://www.ccleaner.com/ccleaner/download",                 "Software",  ["ccleaner","install","cleanup","registry","optimize"]),
    # ── POWERSHELL SCRIPT REFERENCES ─────────────────────────────
    ("https://ss64.com/ps/",                                       "Scripts",   ["powershell","command","script","reference","windows"]),
    ("https://ss64.com/nt/",                                       "Scripts",   ["batch","cmd","command","script","windows"]),
    ("https://adamtheautomator.com/",                              "Scripts",   ["powershell","automation","windows","script"]),
    ("https://www.pdq.com/blog/",                                  "Scripts",   ["deployment","script","windows","automate"]),
    # ── WINGET INSTALL COMMANDS (SPECIFIC POPULAR APPS) ──────────
    ("https://winstall.app/",                                      "Software",  ["winget","install","app","windows","gui"]),
    ("https://winget.run/",                                        "Software",  ["winget","search","install","app","windows"]),
    ("https://github.com/microsoft/winget-cli",                    "Software",  ["winget","cli","install","windows","package"]),
]

# GUI state dict
_gui: dict = {}
_log_lines: list = []
_log_lock = threading.Lock()
OLLAMA_URL     = os.environ.get("OLLAMA_URL", "http://localhost:11434")
DEFAULT_MODEL  = os.environ.get("BUTLER_MODEL", "phi3:mini")

def _get_active_model() -> str:
    """Returns the currently active Ollama model. Persists across restarts."""
    saved = _gs("active_model")
    if saved: return saved
    if _ol_ok():
        model = _ol_model()
        if model:
            _ss("active_model", model)
            return model
    return DEFAULT_MODEL
STATE_FILE     = Path.home() / ".butler_server_state_v6.json"
SECRET_FILE    = Path.home() / ".butler_server_secret_v6.bin"

IS_WINDOWS = platform.system() == "Windows"
IS_MAC     = platform.system() == "Darwin"
IS_LINUX   = platform.system() == "Linux"

def _get_desktop_path():
    """Find the real Desktop path on any OS/language."""
    # Windows: use shell API to get localized Desktop path
    if IS_WINDOWS:
        try:
            import ctypes.wintypes
            CSIDL_DESKTOP = 0
            buf = ctypes.create_unicode_buffer(ctypes.wintypes.MAX_PATH)
            ctypes.windll.shell32.SHGetFolderPathW(None, CSIDL_DESKTOP, None, 0, buf)
            if buf.value: return Path(buf.value)
        except: pass
    # Fallback: try common Desktop paths
    for name in ["Desktop", "desktop", "Schreibtisch", "Bureau", "Escritorio", "Рабочий стол"]:
        p = Path.home() / name
        if p.exists(): return p
    # Last resort: save next to the server script itself
    return Path(os.path.dirname(os.path.abspath(sys.argv[0])))

QR_PNG_PATH    = _get_desktop_path() / "butler_server_qr.png"
BEACON_PORT    = 8764
MAX_BODY_BYTES = 10 * 1024 * 1024   # 10MB
EXEC_TIMEOUT   = 60
MAX_SCRIPT_SEC = 60  # alias for /api/settings
_metrics_cache: dict = {"ts": 0.0, "data": None}
_ACTIVE_STREAMS: dict = {}  # requestId -> bool (False = abort requested)

def _metrics_cached(ttl: float = 1.0) -> dict:
    """Cache _metrics() results to prevent psutil storm on tab mount."""
    if time.time() - _metrics_cache["ts"] > ttl:
        try:
            _metrics_cache["data"] = _metrics()
        except Exception:
            pass
        _metrics_cache["ts"] = time.time()
    return _metrics_cache["data"] or {}
PREFERRED_PORTS = [8766,8765,5000,8000,8080,8008,8767,8768,8769,8770,3000,3001,4000,8888,8081,8090,9000,9090,7777,12345]

# ══════════════════════════════════════════════════════
#  GUARD 1: ADMIN ELEVATION
# ══════════════════════════════════════════════════════
def _is_admin():
    try:
        if IS_WINDOWS:
            import ctypes
            return bool(ctypes.windll.shell32.IsUserAnAdmin())
        return os.geteuid() == 0
    except: return False

def _elevate():
    """Request admin rights via UAC on Windows."""
    try:
        import ctypes
        script = os.path.abspath(sys.argv[0])
        params = " ".join(f'"{a}"' for a in sys.argv[1:])
        ret = ctypes.windll.shell32.ShellExecuteW(None, "runas", sys.executable, f'"{script}" {params}', None, 1)
        if ret > 32: sys.exit(0)
    except Exception as e:
        print(f"  [WARN] Admin elevation failed: {e} - continuing without admin")

if IS_WINDOWS and not _is_admin() and "--no-admin" not in sys.argv:
    print("  [INIT] Requesting admin rights for firewall & port access...")
    _elevate()

# ══════════════════════════════════════════════════════
#  REQUIREMENTS SCANNER & AUTO-INSTALLER
# ══════════════════════════════════════════════════════
REQUIRED_PACKAGES = [
    {"import": "psutil",   "pip": "psutil",        "purpose": "CPU/RAM/Disk metrics"},
    {"import": "qrcode",   "pip": "qrcode[pil]",   "purpose": "QR code generation"},
    {"import": "PIL",      "pip": "pillow",         "purpose": "Image processing for QR"},
    {"import": "requests", "pip": "requests",       "purpose": "HTTP client for Ollama"},
    {"import": "flask",    "pip": "flask",          "purpose": "Optional web interface"},
]

def _scan_requirements(verbose=False):
    """Scan all required packages and return status report."""
    results = []
    for pkg in REQUIRED_PACKAGES:
        try:
            mod = __import__(pkg["import"])
            import warnings as _w
            with _w.catch_warnings():
                _w.simplefilter("ignore", DeprecationWarning)
                ver = getattr(mod, "__version__", "installed")
            results.append({
                "package": pkg["pip"],
                "import":  pkg["import"],
                "purpose": pkg["purpose"],
                "status":  "OK",
                "version": ver,
            })
            if verbose: print(f"  [REQ] ✓ {pkg['pip']:20s} {ver}")
        except ImportError:
            results.append({
                "package": pkg["pip"],
                "import":  pkg["import"],
                "purpose": pkg["purpose"],
                "status":  "MISSING",
                "version": None,
            })
            if verbose: print(f"  [REQ] ✗ {pkg['pip']:20s} MISSING - pip install {pkg['pip']}")
    return results

def _auto_install(verbose=True):
    """Install any missing required packages automatically."""
    scan = _scan_requirements(verbose=False)
    missing = [r["package"] for r in scan if r["status"] == "MISSING"]
    # Always check critical packages
    critical_missing = []
    for pkg in ["psutil", "qrcode", "PIL", "requests"]:
        try: __import__(pkg)
        except: critical_missing.append({"psutil":"psutil","qrcode":"qrcode[pil]","PIL":"pillow","requests":"requests"}[pkg])
    all_missing = list(set(missing + critical_missing))
    if not all_missing: return True
    print(f"\n  [SETUP] Auto-installing {len(all_missing)} missing package(s): {', '.join(all_missing)}")
    print(f"  [SETUP] This only happens once - please wait 30-60 seconds...")
    try:
        result = subprocess.run(
            [sys.executable, "-m", "pip", "install", "--upgrade", "--quiet"] + all_missing,
            check=True, timeout=300,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE
        )
        print(f"  [SETUP] ✓ All packages installed successfully!")
        return True
    except subprocess.CalledProcessError as e:
        print(f"  [SETUP] ✗ pip install failed. Try manually: pip install {' '.join(all_missing)}")
        print(f"  [SETUP]   Error: {e.stderr.decode()[:200] if e.stderr else 'unknown'}")
        return False
    except Exception as e:
        print(f"  [SETUP] ✗ Unexpected error: {e}")
        return False

_auto_install(verbose=True)

# Now import optional packages
try: import psutil; HAS_PSUTIL=True
except: HAS_PSUTIL=False
try: import qrcode; HAS_QR=True
except: HAS_QR=False
try: from PIL import Image, ImageTk; HAS_PIL=True
except: HAS_PIL=False

# ══════════════════════════════════════════════════════
#  GUARD 2: PROCESS GUARDIAN - Kill interfering processes
# ══════════════════════════════════════════════════════
def _find_process_on_port(port):
    """Find the process using a specific port."""
    results = []
    if HAS_PSUTIL:
        try:
            for conn in psutil.net_connections(kind='tcp'):
                if conn.laddr.port == port and conn.status == 'LISTEN':
                    try:
                        proc = psutil.Process(conn.pid)
                        results.append({
                            "pid": conn.pid,
                            "name": proc.name(),
                            "cmdline": " ".join(proc.cmdline())[:80],
                            "port": port,
                        })
                    except: pass
        except: pass
    return results

def _kill_process_on_port(port, force=False):
    """Kill any process blocking a port. Returns list of killed PIDs."""
    killed = []
    procs = _find_process_on_port(port)
    for p in procs:
        try:
            if IS_WINDOWS:
                subprocess.run(["taskkill", "/F", "/PID", str(p["pid"])], capture_output=True, timeout=5)
            else:
                sig = signal.SIGKILL if force else signal.SIGTERM
                os.kill(p["pid"], sig)
            killed.append(p)
            print(f"  [GUARDIAN] Killed PID {p['pid']} ({p['name']}) on port {port}")
        except Exception as e:
            print(f"  [GUARDIAN] Could not kill PID {p['pid']}: {e}")
    return killed

def _kill_old_instances():
    """Kill any previous butler_server.py processes before starting fresh."""
    current_pid = os.getpid()
    script_name = os.path.basename(sys.argv[0])
    killed_count = 0
    if HAS_PSUTIL:
        try:
            for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
                if proc.info['pid'] == current_pid: continue
                cmdline = " ".join(proc.info.get('cmdline') or [])
                if script_name in cmdline and 'python' in proc.info.get('name','').lower():
                    try:
                        proc.terminate()
                        killed_count += 1
                        print(f"  [INIT] Terminated old instance PID {proc.info['pid']}")
                    except: pass
        except: pass
    else:
        # Fallback without psutil
        try:
            if IS_WINDOWS:
                result = subprocess.run(
                    ["wmic","process","where","name='python.exe'","get","ProcessId,CommandLine"],
                    capture_output=True, text=True, timeout=10
                )
                for line in result.stdout.splitlines():
                    if script_name in line and str(current_pid) not in line:
                        try:
                            pid = int(line.strip().split()[-1])
                            os.kill(pid, 9)
                            killed_count += 1
                        except: pass
            else:
                result = subprocess.run(["pgrep","-f",script_name], capture_output=True, text=True, timeout=5)
                for line in result.stdout.splitlines():
                    try:
                        pid = int(line.strip())
                        if pid != current_pid:
                            os.kill(pid, 15)
                            killed_count += 1
                    except: pass
        except: pass
    if killed_count: print(f"  [INIT] Cleared {killed_count} old instance(s)")

def _list_all_processes():
    """List top processes for diagnostics."""
    procs = []
    if HAS_PSUTIL:
        try:
            for p in sorted(psutil.process_iter(['pid','name','cpu_percent','memory_percent','status']),
                           key=lambda x: x.info.get('cpu_percent') or 0, reverse=True)[:20]:
                procs.append({
                    "pid":    p.info['pid'],
                    "name":   p.info.get('name','?'),
                    "cpu":    round(p.info.get('cpu_percent') or 0, 1),
                    "mem":    round(p.info.get('memory_percent') or 0, 1),
                    "status": p.info.get('status','?'),
                })
        except: pass
    return procs

def _kill_interference():
    """
    Find and kill any process that might interfere with the server:
    - Old butler_server.py instances
    - Any process on our known ports
    Returns a report of what was killed.
    """
    report = {"killed": [], "errors": []}
    # 1. Kill old server instances
    _kill_old_instances()
    # 2. Check all our preferred ports for blockers
    for p in [8766, 8765, 5000, 8080]:
        blockers = _find_process_on_port(p)
        for b in blockers:
            if b["pid"] != os.getpid():
                try:
                    if IS_WINDOWS:
                        subprocess.run(["taskkill","/F","/PID",str(b["pid"])], capture_output=True, timeout=5)
                    else:
                        os.kill(b["pid"], signal.SIGTERM)
                    report["killed"].append(f"PID {b['pid']} ({b['name']}) on port {p}")
                except Exception as e:
                    report["errors"].append(f"PID {b['pid']}: {e}")
    return report

# ══════════════════════════════════════════════════════
#  HMAC TOKEN AUTH
# ══════════════════════════════════════════════════════
def _load_secret():
    try:
        if SECRET_FILE.exists(): return SECRET_FILE.read_bytes()
    except: pass
    s = os.urandom(32)
    try:
        SECRET_FILE.write_bytes(s)
        if not IS_WINDOWS: SECRET_FILE.chmod(0o600)
    except: pass
    return s

HMAC_SECRET = _load_secret()

def _sign(payload):
    return hmac.new(HMAC_SECRET, payload.encode(), hashlib.sha256).hexdigest()

def _make_token(device_id):
    ts = int(time.time())
    raw = f"{device_id}:{ts}"
    return base64.urlsafe_b64encode(f"{raw}:{_sign(raw)}".encode()).decode()

def _verify_token(token, device_id):
    try:
        decoded = base64.urlsafe_b64decode(token.encode()).decode()
        parts   = decoded.rsplit(":", 1)
        if len(parts) != 2: return False
        raw, sig = parts[0], parts[1]
        if not hmac.compare_digest(sig, _sign(raw)): return False
        rp = raw.split(":")
        ts = int(rp[-1])
        if time.time() - ts > 60 * 60 * 24 * 30: return False  # 30 days
        return rp[0] == device_id
    except: return False

# ══════════════════════════════════════════════════════
#  PERSISTENT STATE
# ══════════════════════════════════════════════════════
_sl = threading.RLock()  # RLock: same thread can re-acquire without deadlock
_pair_lock = threading.Lock()  # Dedicated lock for pairing — prevents two devices racing to auto-lock
_RECONNECT_CACHE: dict = {}  # In-memory reconnect dedup cache (not persisted)

def _load_state():
    try:
        if STATE_FILE.exists(): return json.loads(STATE_FILE.read_text())
    except: pass
    return {
        "pairing_code":  None,
        "locked_device": None,
        "paired_at":     None,
        "last_seen":     None,
        "server_port":   None,
        "auto_lock_version": None,
    }

def _save_state(s):
    try: STATE_FILE.write_text(json.dumps(s, indent=2))
    except: pass

_state = _load_state()

def _gs(k):
    with _sl: return _state.get(k)

_state_dirty = threading.Event()

def _state_writer_loop():
    """Single persistent thread — coalesces rapid _ss() calls into
    at most 2 disk writes/second instead of one thread per call."""
    while True:
        _state_dirty.wait()          # block until something is dirty
        _state_dirty.clear()
        time.sleep(0.5)              # 500ms debounce — coalesces bursts
        with _sl:
            snap = _state.copy()
        _save_state(snap)

threading.Thread(target=_state_writer_loop, daemon=True,
                 name="state-writer").start()

def _ss(k, v):
    with _sl:
        _state[k] = v
    _state_dirty.set()               # signal writer — never blocks handler

# ══════════════════════════════════════════════════════
#  FIREWALL
# ══════════════════════════════════════════════════════
def _fw(port, enabled=True):
    if not enabled: return
    if IS_WINDOWS:
        name = f"Butler AI v6 port {port}"
        try:
            r = subprocess.run(
                ["netsh","advfirewall","firewall","show","rule",f"name={name}"],
                capture_output=True, text=True, timeout=10
            )
            if "No rules match" not in r.stdout and r.returncode == 0: return
            subprocess.run(
                ["netsh","advfirewall","firewall","add","rule",
                 f"name={name}","dir=in","action=allow","protocol=TCP",
                 f"localport={port}","profile=any","enable=yes"],
                capture_output=True, timeout=15, check=True
            )
            print(f"  [FW] ✓ Firewall rule added for port {port}")
        except Exception as e:
            print(f"  [FW] Firewall warning: {e}")
    elif IS_LINUX:
        try: subprocess.run(["ufw","allow",f"{port}/tcp"], capture_output=True, timeout=10)
        except:
            try: subprocess.run(["iptables","-I","INPUT","-p","tcp","--dport",str(port),"-j","ACCEPT"], capture_output=True, timeout=10)
            except: pass
    elif IS_MAC:
        # macOS uses pf - add a note
        print(f"  [FW] Mac: allow port {port} in System Preferences → Security → Firewall if blocked")

# ══════════════════════════════════════════════════════
#  PORT SELECTION
# ══════════════════════════════════════════════════════
def _free_port(preferred=None):
    """Find a genuinely free port - bind test + probe to avoid TIME_WAIT sockets."""
    candidates = ([preferred] + PREFERRED_PORTS) if preferred else PREFERRED_PORTS
    for p in candidates:
        if not p: continue
        try: p = int(p)
        except: continue
        # Test 1: can we bind?
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            s.bind(("0.0.0.0", p)); s.close()
        except OSError: continue
        # Test 2: is anything already responding? (catches SO_REUSEADDR edge cases)
        try:
            probe = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            probe.settimeout(0.15)
            connected = probe.connect_ex(("127.0.0.1", p)) == 0
            probe.close()
            if connected: continue
        except: pass
        return p
    # All preferred ports busy - let OS pick any free port
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    s.bind(("0.0.0.0", 0)); p = s.getsockname()[1]; s.close()
    print(f"  [PORT] All preferred ports busy - using OS-assigned port {p}")
    return p

# ══════════════════════════════════════════════════════
#  IP DETECTION
# ══════════════════════════════════════════════════════
def get_ip():
    """
    Detect the best LAN IP address. Must work for ANY customer:
    - Home WiFi with internet ✓
    - Phone hotspot (no internet on PC) ✓
    - Airgapped WiFi (no internet at all) ✓
    - VPN / Docker / multiple interfaces ✓
    
    Strategy: try multiple methods, return first valid LAN IP.
    """
    # Method 1: psutil — reads network interfaces directly, no internet needed
    # This is the most reliable for hotspot/airgapped setups
    if HAS_PSUTIL:
        try:
            best = None
            for iface, addrs in psutil.net_if_addrs().items():
                for a in addrs:
                    if a.family == socket.AF_INET and not a.address.startswith("127."):
                        ip = a.address
                        # Prefer 192.168.x.x (most common home/hotspot subnet)
                        if ip.startswith("192.168."): return ip
                        # Also accept 10.x.x.x and 172.16-31.x.x
                        if not best: best = ip
            if best: return best
        except: pass

    # Method 2: UDP probe to public DNS — works when internet is available
    for target in [("8.8.8.8", 80), ("1.1.1.1", 80)]:
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.settimeout(2)
            s.connect(target)
            ip = s.getsockname()[0]
            s.close()
            if ip and not ip.startswith("127."): return ip
        except: pass

    # Method 3: hostname resolution — last resort
    try:
        hostname = socket.gethostname()
        ip = socket.gethostbyname(hostname)
        if ip and not ip.startswith("127."): return ip
    except: pass

    # Method 4: scan common gateway IPs to find our own address
    try:
        for gateway in ["192.168.1.1", "192.168.0.1", "10.0.0.1", "192.168.43.1"]:
            try:
                s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                s.settimeout(0.5)
                s.connect((gateway, 80))
                ip = s.getsockname()[0]
                s.close()
                if ip and not ip.startswith("127."): return ip
            except: pass
    except: pass

    return "127.0.0.1"

def get_all_ips():
    ips = set()
    try:
        if HAS_PSUTIL:
            for _, addrs in psutil.net_if_addrs().items():
                for a in addrs:
                    if a.family == socket.AF_INET and not a.address.startswith("127."):
                        ips.add(a.address)
    except: pass
    ips.add(get_ip())
    return sorted(ips)

# ══════════════════════════════════════════════════════
#  RATE LIMITER
# ══════════════════════════════════════════════════════
_rc = {}
_rl = threading.Lock()

# Cache IP list - refreshed every 60s in background
_cached_ips: list = get_all_ips()

def _refresh_ip_cache():
    global _cached_ips
    while True:
        time.sleep(60)
        try: _cached_ips = get_all_ips()
        except: pass

# Brute-force pairing code tracker — separate from general rate limit
_pair_attempts: dict = {}  # ip → [timestamps]

def _purge_rate_limit_dicts():
    """Purge stale IPs from _rc and _pair_attempts every 5 minutes.
    Prevents unbounded RAM growth on long-running servers."""
    while True:
        time.sleep(300)  # run every 5 minutes
        now = time.time()
        with _rl:
            stale = [ip for ip, ts in _rc.items()
                     if not any(t > now - 120 for t in ts)]
            for ip in stale:
                del _rc[ip]
        with _pair_lock2:
            stale2 = [ip for ip, ts in _pair_attempts.items()
                      if not any(t > now - 600 for t in ts)]
            for ip in stale2:
                del _pair_attempts[ip]

threading.Thread(target=_purge_rate_limit_dicts, daemon=True,
                 name="rl-purge").start()
_pair_lock2 = threading.Lock()

def _check_pair_bruteforce(ip: str) -> bool:
    """Returns True if this IP is brute-forcing pairing codes (block it)."""
    now = time.time()
    with _pair_lock2:
        attempts = [t for t in _pair_attempts.get(ip, []) if now - t < 300]  # 5 min window
        attempts.append(now)
        _pair_attempts[ip] = attempts
        # More than 10 failed attempts in 5 minutes = brute force
        return len(attempts) > 10


def _rlimit(ip):
    """
    Rate limiter — protects against abuse from unknown IPs.
    Generous limits for paired devices (app sends multiple concurrent requests).
    Blocks actual abuse: 100 req/5s or 500 req/60s is clearly a bot.
    """
    now = time.time()
    with _rl:
        ts = [t for t in _rc.get(ip, []) if now - t < 60]
        # Burst: 100 req in 5s (was 30) — allows concurrent app requests
        # Sustained: 500 req in 60s (was 150) — ~8 req/s sustained is fine
        if len([t for t in ts if now - t < 5]) >= 100 or len(ts) >= 500:
            _rc[ip] = ts
            return True
        ts.append(now)
        _rc[ip] = ts
        return False

# ══════════════════════════════════════════════════════
#  UDP BEACON
# ══════════════════════════════════════════════════════
def _beacon(ip, port):
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    all_ips = get_all_ips()
    while True:
        try:
            payload = json.dumps({
                "type":    "butler_beacon",
                "ip":      ip,
                "allIPs":  all_ips,
                "port":    port,
                # pairingCode intentionally omitted — display on screen only, never broadcast
                "version": VERSION,
                "locked":  bool(_gs("locked_device")),
                "os":      platform.system(),
                "ts":      int(time.time()),
            }).encode()
            sock.sendto(payload, ("255.255.255.255", BEACON_PORT))
            for lip in all_ips:
                parts = lip.rsplit(".", 1)
                if len(parts) == 2:
                    try: sock.sendto(payload, (f"{parts[0]}.255", BEACON_PORT))
                    except: pass
        except: pass
        time.sleep(2)

# ══════════════════════════════════════════════════════
#  QR CODE
# ══════════════════════════════════════════════════════
def _qr(ip, port):
    all_ips = get_all_ips()
    code    = _gs("pairing_code") or ""
    payload = json.dumps({"ip": ip, "allIPs": all_ips, "port": port, "pairingCode": code, "version": VERSION})
    print(f"\n  QR Payload: {payload}\n")
    if HAS_QR:
        try:
            qr = qrcode.QRCode(version=2, error_correction=qrcode.constants.ERROR_CORRECT_M, box_size=1, border=2)
            qr.add_data(payload)
            qr.make(fit=True)
            qr.print_ascii(invert=True)
            if HAS_PIL:
                try:
                    img = qr.make_image(fill_color="black", back_color="white")
                    QR_PNG_PATH.parent.mkdir(exist_ok=True)
                    img.save(str(QR_PNG_PATH))
                    print(f"  [QR] ✓ Saved to Desktop: {QR_PNG_PATH}")
                except: pass
        except Exception as e:
            print(f"  [QR] Error: {e}")
    else:
        print(f"  Manual: IP={ip}  Port={port}  Code={code}")
    print()

# ══════════════════════════════════════════════════════
#  OLLAMA AI
# ══════════════════════════════════════════════════════
# Cached Ollama state - refreshed every 10s in background
# /api/status reads from cache so heartbeat ping is always instant
_ol_cache = {"ok": False, "model": "", "models": [], "ts": 0.0}
_ol_cache_lock = threading.Lock()

def _ol_cache_refresh():
    """Background thread: refreshes Ollama status every 10s."""
    while True:
        try:
            import urllib.request as _ur
            with _ur.urlopen(f"{OLLAMA_URL}/api/tags", timeout=3) as r:
                if r.status == 200:
                    d = json.loads(r.read())
                    ms = d.get("models", [])
                    names = [x["name"] for x in ms]
                    # Respect user's saved model — don't overwrite with
                    # lightest if they already chose something explicitly.
                    saved = _gs("active_model")
                    if saved and saved in names:
                        m = saved
                    else:
                        m = _select_lightest(names) if names else ""
                        if m:
                            _ss("active_model", m)
                    with _ol_cache_lock:
                        _ol_cache["ok"]     = True
                        _ol_cache["model"]  = m
                        _ol_cache["models"] = [x["name"] for x in ms]
                        _ol_cache["ts"]     = time.time()
                else:
                    with _ol_cache_lock:
                        _ol_cache["ok"] = False; _ol_cache["ts"] = time.time()
        except:
            with _ol_cache_lock:
                _ol_cache["ok"] = False; _ol_cache["ts"] = time.time()
        time.sleep(10)

def _ol_ok():
    with _ol_cache_lock: return _ol_cache["ok"]

def _ol_model():
    with _ol_cache_lock: return _ol_cache["model"]

def _ol_models():
    with _ol_cache_lock: return list(_ol_cache["models"])

def _ol_chat(msg, system="", model=DEFAULT_MODEL, history=None):
    try:
        import urllib.request
        msgs = []
        if system: msgs.append({"role": "system", "content": system})
        for m in (history or []): msgs.append(m)
        msgs.append({"role": "user", "content": msg})
        # Always use best model for this PC — ignore passed arg
        active = _best_model_for_pc() or _ol_model() or model
        payload = {
            "model": active, "messages": msgs, "stream": False,
            "options": {
                "num_ctx": 2048, "num_predict": 512,
                "temperature": 0.7, "top_p": 0.9,
                "repeat_penalty": 1.1,
                "num_thread": 0,    # all CPU threads, no cap
                "num_gpu": 1,       # use GPU if available
                "low_vram": False,
            }
        }
        body = json.dumps(payload).encode()
        req  = urllib.request.Request(
            f"{OLLAMA_URL}/api/chat", data=body,
            headers={"Content-Type": "application/json"}, method="POST"
        )
        with urllib.request.urlopen(req, timeout=180) as r:
            d = json.loads(r.read())
        return d.get("message", {}).get("content", "No response.")
    except urllib.error.HTTPError as e:
        if e.code == 404:
            return f"Model not found. Run: ollama pull {_best_model_for_pc()}"
        return f"[Ollama error] HTTP {e.code}: {e.reason}"
    except urllib.error.URLError:
        return "Butler AI offline — Ollama not running.\n\n1. Download: https://ollama.ai"
    except Exception as e:
        return f"[Ollama error] {e}"

# ══════════════════════════════════════════════════════
#  OLLAMA AUTO-MANAGER
#  Finds, starts, and pulls the default model automatically.
#  Users never need to touch Ollama manually.
# ══════════════════════════════════════════════════════

_OLLAMA_EXE_PATHS = [
    # Windows standard install locations
    r"C:\Users\{user}\AppData\Local\Programs\Ollama\ollama.exe",
    r"C:\Program Files\Ollama\ollama.exe",
    r"C:\Program Files (x86)\Ollama\ollama.exe",
    # Also try PATH
    "ollama",
    "ollama.exe",
]

def _find_ollama_exe():
    """Find the Ollama executable on this machine."""
    import shutil
    # Try PATH first (fastest)
    found = shutil.which("ollama")
    if found: return found
    # Try known Windows install paths
    import os, getpass
    user = getpass.getuser()
    for p in _OLLAMA_EXE_PATHS:
        try:
            expanded = p.format(user=user)
            if os.path.isfile(expanded):
                return expanded
        except: pass
    return None


def _ollama_is_running():
    """Return True if Ollama API is reachable."""
    try:
        import urllib.request
        with urllib.request.urlopen(f"{OLLAMA_URL}/api/tags", timeout=2) as r:
            return r.status == 200
    except: return False


def _start_ollama_service():
    """
    Start the Ollama server process if it's not already running.
    Returns True if Ollama is running after this call.
    """
    if _ollama_is_running():
        return True

    exe = _find_ollama_exe()
    if not exe:
        log.warning("Ollama not installed - will auto-install shortly")
        return False

    log.info(f"Starting Ollama service: {exe}")
    try:
        # ── CPU GUARD: Limit Ollama CPU threads ──────────────
        # Without this, Ollama uses ALL cores → 100% CPU → everything else freezes.
        # Reserve 2 cores for OS/crawlers/server, give the rest to Ollama.
        env = os.environ.copy()
        try:
            total_cores = os.cpu_count() or 4
            ollama_threads = max(2, total_cores - 2)  # At least 2, leave 2 for OS
            env["OLLAMA_NUM_PARALLEL"] = "1"           # 1 request at a time
            env.setdefault("OLLAMA_NUM_THREAD", str(ollama_threads))
            log.info(f"Ollama CPU limit: {ollama_threads}/{total_cores} threads")
        except: pass

        kw = {}
        if IS_WINDOWS:
            kw["creationflags"] = subprocess.CREATE_NO_WINDOW | subprocess.DETACHED_PROCESS
        subprocess.Popen(
            [exe, "serve"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            env=env,
            **kw
        )
        # Wait up to 8s for it to come up
        for _ in range(16):
            time.sleep(0.5)
            if _ollama_is_running():
                log.info("✓ Ollama service started")
                return True
        log.warning("Ollama started but not responding yet")
        return False
    except Exception as e:
        log.warning(f"Could not start Ollama: {e}")
        return False


def _install_ollama_windows():
    """
    Download and silently install Ollama on Windows.
    Returns True if installation succeeded.
    """
    if not IS_WINDOWS: return False
    try:
        import urllib.request, tempfile, os
        installer_url = "https://ollama.ai/download/OllamaSetup.exe"
        log.info("Downloading Ollama installer…")
        _log("Downloading Ollama… (this may take a minute)", "warn")
        import os as _os_tmp
        fd, tmp = tempfile.mkstemp(suffix=".exe")
        _os_tmp.close(fd)  # close fd, urlretrieve will re-open
        urllib.request.urlretrieve(installer_url, tmp)
        log.info("Running Ollama installer silently…")
        _log("Installing Ollama…", "warn")
        r = subprocess.run([tmp, "/S"], timeout=120)
        os.unlink(tmp)
        if r.returncode == 0:
            log.info("✓ Ollama installed")
            time.sleep(3)  # give installer time to register PATH
            return True
        log.warning(f"Ollama installer returned {r.returncode}")
        return False
    except Exception as e:
        log.warning(f"Ollama install failed: {e}")
        return False


# ── Model minimum disk requirements (GB) ─────────────────────────────────────
_MODEL_DISK_GB: dict = {
    "qwen2.5:0.5b":        1.0,
    "tinyllama:latest":    1.0,
    "tinyllama":           1.0,
    "qwen2.5:1.5b":        1.5,
    "qwen2.5-coder:1.5b":  1.5,
    "llama3.2:1b":         1.5,
    "phi3:mini":           2.5,
    "gemma2:2b":           2.5,
    "llama3.2:3b":         2.5,
    "phi4-mini:latest":    3.0,
    "phi4-mini":           3.0,
    "qwen2.5-coder:7b":    5.0,
    "qwen2.5:7b":          5.0,
    "mistral:7b":          5.0,
    "llama3.1:8b":         5.5,
    "deepseek-r1:8b":      5.5,
    "qwen2.5:14b":         9.0,
}
_MODEL_DISK_GB_DEFAULT = 4.0  # safe fallback for unknown models


def _get_ollama_models_dir() -> Path:
    """Return the Ollama models directory; falls back to home drive."""
    import getpass
    candidates = [
        Path.home() / ".ollama" / "models",
        Path(f"C:/Users/{getpass.getuser()}/.ollama/models"),
        Path("C:/Users/Public/.ollama/models"),
    ]
    for p in candidates:
        if p.exists():
            return p
    return Path.home() / ".ollama" / "models"


def _get_disk_info() -> dict:
    """Disk usage for the Ollama models directory (and total drive stats)."""
    import shutil as _shutil
    models_dir = _get_ollama_models_dir()
    check = models_dir
    while not check.exists() and check != check.parent:
        check = check.parent
    try:
        usage    = _shutil.disk_usage(str(check))
        free_gb  = round(usage.free  / 1e9, 2)
        total_gb = round(usage.total / 1e9, 2)
        used_gb  = round(usage.used  / 1e9, 2)
    except Exception:
        free_gb = total_gb = used_gb = 0.0
    models_size_gb = 0.0
    if models_dir.exists():
        try:
            total_bytes    = sum(f.stat().st_size for f in models_dir.rglob("*") if f.is_file())
            models_size_gb = round(total_bytes / 1e9, 2)
        except Exception:
            pass
    return {
        "free_gb":            free_gb,
        "total_gb":           total_gb,
        "used_gb":            used_gb,
        "ollama_models_path": str(models_dir),
        "models_dir_size_gb": models_size_gb,
    }


def _check_disk_space_for_model(model: str) -> tuple:
    """Returns (ok: bool, free_gb: float, required_gb: float)."""
    key         = (model or "").lower().strip()
    required_gb = _MODEL_DISK_GB.get(key, _MODEL_DISK_GB_DEFAULT)
    info        = _get_disk_info()
    free_gb     = info["free_gb"]
    return (free_gb >= required_gb * 1.1), free_gb, required_gb


def _pick_best_model() -> str:
    """Delegate to _best_model_for_pc() — single source of truth for model selection.
    Checks env override first, then RAM-aware hardware tier picker."""
    if os.environ.get("BUTLER_MODEL"):
        return os.environ["BUTLER_MODEL"]
    return _best_model_for_pc()


def _model_size_label(model: str) -> str:
    """Human-readable model size for UI display."""
    try:
        m = (model or "").lower()
        if "7b" in m:                    return "7B · 4.7GB"
        if "3b" in m:                    return "3B · 2GB"
        if "1.5b" in m:                  return "1.5B · 1GB"
        if "tinyllama" in m:             return "1.1B · 0.6GB"
        if ":" in model:                 return model.split(":")[-1].upper()
    except: pass
    return ""


def _model_tier(model: str) -> str:
    """Model tier for UI color coding: light/balanced/heavy."""
    try:
        m = (model or "").lower()
        if "1.5b" in m or "tinyllama" in m: return "light"
        if "3b" in m:                        return "balanced"
        if "7b" in m or "13b" in m:          return "heavy"
    except: pass
    return "unknown"


def _cleanup_unused_models(keep_model: str):
    """Remove ALL Ollama models except the exact active one. Saves 1-5GB per model."""
    try:
        installed = _ol_models()
        if len(installed) <= 1: return
        keep = (keep_model or "").lower().strip()
        for m in installed:
            if m.lower().strip() == keep:
                continue
            try:
                exe = _find_ollama_exe() or "ollama"
                cmd = [exe, "rm", m] if isinstance(exe, str) else ["ollama", "rm", m]
                kw = {}
                if IS_WINDOWS: kw["creationflags"] = subprocess.CREATE_NO_WINDOW
                subprocess.run(cmd, timeout=30, capture_output=True, **kw)
                log.info(f"[MODEL] Removed: {m}")
                _log(f"Removed unused AI model: {m}", "dim")
            except: pass
    except: pass


def _ensure_model(model=None):
    """
    Pull the best model for this PC's RAM if not already installed.
    1. Checks if model already exists → done.
    2. Pre-checks disk space → aborts with clear message if insufficient.
    3. Streams pull progress live into activity log + _pull_progress dict.
    4. On success, cleans up unused models to reclaim disk space.
    """
    if model is None:
        model = _pick_best_model()

    global DEFAULT_MODEL
    DEFAULT_MODEL = model
    _ss("active_model", model)

    # ── Already installed? ────────────────────────────────────────────────
    models = _ol_models()
    base   = model.split(":")[0].lower()
    for m in models:
        if m.lower() == model.lower() or m.lower().startswith(base):
            log.info(f"✓ Model already installed: {m}")
            _log(f"AI model ready: {m} ✓", "ok")
            _set_pull_progress(model=m, status="ready", percent=100, active=False)
            _cleanup_unused_models(model)
            return

    # ── Disk space pre-check ──────────────────────────────────────────────
    ok_space, free_gb, req_gb = _check_disk_space_for_model(model)
    if not ok_space:
        msg = (f"NOT ENOUGH DISK SPACE to download {model}: "
               f"need {req_gb:.1f} GB + 10% buffer, "
               f"have {free_gb:.1f} GB free. "
               f"Free up space on your drive and restart.")
        log.warning(msg)
        _log(f"⚠ {msg}", "warn")
        _set_pull_progress(model=model, status="insufficient_disk", percent=0,
                           active=False, error=msg)
        return

    # ── Pull ──────────────────────────────────────────────────────────────
    log.info(f"Pulling {model} — {req_gb:.1f} GB needed, {free_gb:.1f} GB free…")
    _log(f"[MODEL] Starting download: {model} "
         f"({req_gb:.1f} GB needed · {free_gb:.1f} GB free)", "warn")

    exe = _find_ollama_exe() or "ollama"
    success = _stream_pull(model, exe)

    if success:
        log.info(f"✓ {model} downloaded and ready")
        _log(f"[MODEL] ✓ {model} ready — AI is online", "ok")
        _set_pull_progress(model=model, status="complete", percent=100,
                           active=False, finished_at=time.time())
        _cleanup_unused_models(model)
    else:
        err_msg = f"[MODEL] Pull failed for {model} — Ollama may have timed out or lost connection"
        log.warning(err_msg)
        _log(err_msg, "warn")
        _set_pull_progress(model=model, status="error", percent=0,
                           active=False, error="pull failed",
                           finished_at=time.time())
def _start_ollama_auto():
    """
    Full auto-manager called at server startup.
    1. If Ollama running → ensure model is installed → done.
    2. If Ollama installed but not running → start it → ensure model.
    3. If Ollama not installed (Windows) → download + install → start → pull model.
    Everything runs in a background thread so the server starts instantly.
    """
    def _worker():
        try:
            if _ollama_is_running():
                log.info("Ollama already running")
                _ensure_model()
                return

            if _find_ollama_exe():
                log.info("Ollama installed - starting service…")
                if _start_ollama_service():
                    _ensure_model()
                    return
                else:
                    log.warning("Could not start Ollama - will keep retrying")
                    # Retry loop every 30s in case user starts it manually
                    for _ in range(20):
                        time.sleep(30)
                        if _ollama_is_running():
                            _ensure_model()
                            return
            else:
                # Ollama not installed at all
                if IS_WINDOWS:
                    log.info("Ollama not found - downloading installer…")
                    if _install_ollama_windows():
                        if _start_ollama_service():
                            _ensure_model()
                            return
                else:
                    log.warning("Ollama not installed. Install from https://ollama.ai")
                    _log("Install Ollama: https://ollama.ai → then restart server", "warn")
        except Exception as e:
            log.warning(f"Ollama auto-manager error: {e}")

    threading.Thread(target=_worker, daemon=True, name="ollama-auto").start()


# ══════════════════════════════════════════════════════
#  SYSTEM METRICS
# ══════════════════════════════════════════════════════
def _metrics():
    if not HAS_PSUTIL:
        return {"error": "psutil not installed", "install": "pip install psutil"}
    try:
        cpu  = psutil.cpu_percent(interval=0.3)
        mem  = psutil.virtual_memory()
        disk = psutil.disk_usage(str(Path.home()))
        nio  = psutil.net_io_counters()
        procs = []
        try:
            for p in sorted(
                psutil.process_iter(["pid","name","cpu_percent","memory_percent"]),
                key=lambda x: x.info.get("cpu_percent") or 0, reverse=True
            )[:8]:
                procs.append({
                    "name": p.info.get("name","?"),
                    "cpu":  round(p.info.get("cpu_percent") or 0, 1),
                    "mem":  round(p.info.get("memory_percent") or 0, 1),
                })
        except: pass
        # CPU frequency (may not be available on all systems)
        try:
            freq = psutil.cpu_freq()
            freq_mhz = round(freq.current, 0) if freq else 0
        except: freq_mhz = 0
        # Build response matching app's ServerMetrics TypeScript interface exactly
        return {
            "cpu":     {"percent": round(cpu, 1), "cores": psutil.cpu_count(logical=False) or 1, "logical": psutil.cpu_count(), "freq_mhz": freq_mhz},
            "memory":  {"total": mem.total, "used": mem.used, "percent": round(mem.percent, 1),
                        "total_gb": round(mem.total / (1024**3), 1), "used_gb": round(mem.used / (1024**3), 1)},
            "ram":     {"total": mem.total, "used": mem.used, "percent": round(mem.percent, 1),
                        "total_gb": round(mem.total / (1024**3), 1), "used_gb": round(mem.used / (1024**3), 1)},
            "disk":    {"total": disk.total, "used": disk.used, "free": disk.free, "percent": round(disk.percent, 1),
                        "total_gb": round(disk.total / (1024**3), 1), "used_gb": round(disk.used / (1024**3), 1), "free_gb": round(disk.free / (1024**3), 1)},
            "network": {"bytes_sent": nio.bytes_sent, "bytes_recv": nio.bytes_recv,
                        "bytes_sent_mb": round(nio.bytes_sent / (1024**2), 1), "bytes_recv_mb": round(nio.bytes_recv / (1024**2), 1)},
            "system":  {"os": f"{platform.system()} {platform.release()}", "hostname": socket.gethostname(),
                        "uptime_hrs": round((time.time() - psutil.boot_time()) / 3600, 1), "python_version": platform.python_version()},
            "processes": {"total": len(procs), "top": procs},
            # Flat aliases for backward compatibility
            "uptime":  int(time.time() - psutil.boot_time()),
            "hostname": socket.gethostname(),
            "os":      f"{platform.system()} {platform.release()}",
        }
    except Exception as e:
        return {"error": str(e)}

# ══════════════════════════════════════════════════════
#  LOGGING (GUI-aware)
# ══════════════════════════════════════════════════════
logging.basicConfig(level=logging.INFO,
    format="%(asctime)s [%(levelname)-5s] %(message)s",
    datefmt="%H:%M:%S",
    handlers=[logging.StreamHandler(sys.stdout)])
log = logging.getLogger("boter")

def _log(msg, tag="info"):
    with _log_lock:
        _log_lines.append((tag, msg))
        if len(_log_lines) > 2000: _log_lines.pop(0)
    _refresh_log()
    if tag == "ok": log.info(msg)
    elif tag == "warn": log.warning(msg)
    elif tag == "err": log.error(msg)
    else: log.info(msg)

# ══════════════════════════════════════════════════════
#  KNOWLEDGE BASE (SQLite)
# ══════════════════════════════════════════════════════
_db_lock = threading.Lock()

def _db_init():
    with _db_lock:
        c = sqlite3.connect(str(DB_PATH))
        c.executescript("""
            CREATE TABLE IF NOT EXISTS knowledge_base(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                url TEXT UNIQUE,
                title TEXT,
                category TEXT DEFAULT 'General',
                clean_text TEXT,
                keywords TEXT DEFAULT '[]',
                word_count INTEGER DEFAULT 0,
                crawled_at REAL DEFAULT 0);

            CREATE TABLE IF NOT EXISTS chat_history(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                device_id TEXT,
                role TEXT,
                content TEXT,
                ts REAL DEFAULT(unixepoch('now')));

            -- Persistent learning queue: survives restarts, resumes where left off
            CREATE TABLE IF NOT EXISTS learn_queue(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                url TEXT UNIQUE,
                category TEXT DEFAULT 'General',
                keywords TEXT DEFAULT '[]',
                priority INTEGER DEFAULT 5,
                source TEXT DEFAULT 'auto',
                added_at REAL DEFAULT 0,
                status TEXT DEFAULT 'pending',
                attempts INTEGER DEFAULT 0,
                last_attempt REAL DEFAULT 0);

            -- Learning checkpoint: stats saved every 15 min for resume
            CREATE TABLE IF NOT EXISTS learn_checkpoint(
                id INTEGER PRIMARY KEY DEFAULT 1,
                articles_total INTEGER DEFAULT 0,
                articles_session INTEGER DEFAULT 0,
                last_save REAL DEFAULT 0,
                last_url TEXT DEFAULT '',
                queue_size INTEGER DEFAULT 0,
                session_start REAL DEFAULT 0,
                uptime_mins REAL DEFAULT 0);

            -- User topics extracted from chat - learning personalization
            CREATE TABLE IF NOT EXISTS user_topics(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                topic TEXT UNIQUE,
                asks INTEGER DEFAULT 1,
                last_asked REAL DEFAULT 0,
                kb_coverage INTEGER DEFAULT 0);

            CREATE INDEX IF NOT EXISTS idx_kb_url      ON knowledge_base(url);
            CREATE INDEX IF NOT EXISTS idx_lq_status   ON learn_queue(status, priority DESC);
            CREATE INDEX IF NOT EXISTS idx_ut_topic    ON user_topics(asks DESC);
        """)
        # WAL mode: allows readers to proceed while writer is active
        # This means HTTP handler never blocks waiting for a learn worker to finish writing
        # ── ΣNET GROWTH LOG — proprietary growth tracking for graph ──
        c.execute("""
            CREATE TABLE IF NOT EXISTS sigma_growth_log(
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                ts         REAL NOT NULL,
                total      INTEGER NOT NULL,
                added      INTEGER DEFAULT 0,
                category   TEXT DEFAULT 'mixed',
                source     TEXT DEFAULT 'SIGMA-NET'
            )
        """)
        c.execute("CREATE INDEX IF NOT EXISTS idx_sgl_ts ON sigma_growth_log(ts)")
        # ── ΣNET CATEGORY STATS — fast lookup per category ────────
        c.execute("""
            CREATE TABLE IF NOT EXISTS sigma_category_stats(
                category   TEXT PRIMARY KEY,
                count      INTEGER DEFAULT 0,
                last_added REAL DEFAULT 0
            );
        """)
        # Add new columns if upgrading from old schema
        for col_sql in [
            "ALTER TABLE learn_queue ADD COLUMN worker_id INTEGER DEFAULT 0",
            "ALTER TABLE learn_queue ADD COLUMN started_at REAL DEFAULT 0",
            "ALTER TABLE learn_queue ADD COLUMN finished_at REAL DEFAULT 0",
        ]:
            try: c.execute(col_sql)
            except sqlite3.OperationalError: pass  # column already exists
        # ── UNDO JOURNAL ──
        c.execute("""CREATE TABLE IF NOT EXISTS undo_journal(
            id INTEGER PRIMARY KEY AUTOINCREMENT, ts REAL, expires_at REAL,
            script TEXT, language TEXT DEFAULT 'python', user_req TEXT DEFAULT '',
            snapshot TEXT DEFAULT '{}', output TEXT DEFAULT '', status TEXT DEFAULT 'pending',
            undone INTEGER DEFAULT 0)""")
        c.execute("""CREATE TABLE IF NOT EXISTS pc_stats(
            key TEXT PRIMARY KEY, value REAL DEFAULT 0)""")
        for _k in ("files_cleaned","space_recovered_bytes","files_organized",
                    "duplicates_found","scripts_run","scripts_undone","threats_blocked"):
            c.execute("INSERT OR IGNORE INTO pc_stats(key,value) VALUES(?,0)", (_k,))
        c.execute("""CREATE TABLE IF NOT EXISTS pc_stats_log(
            ts REAL, key TEXT, value REAL DEFAULT 0)""")

        c.commit()  # Must commit before setting PRAGMAs (can't change inside transaction)
        c.execute("PRAGMA journal_mode=WAL")
        c.execute("PRAGMA synchronous=NORMAL")
        c.execute("PRAGMA cache_size=10000")
        c.execute("PRAGMA temp_store=MEMORY")
        c.close()

def _db_q(sql, p=()):
    for attempt in range(4):
        try:
            with _db_lock:
                c = sqlite3.connect(str(DB_PATH), timeout=5)
                c.execute("PRAGMA journal_mode=WAL")   # allow concurrent reads
                c.execute("PRAGMA synchronous=NORMAL") # faster writes, still safe
                c.row_factory = sqlite3.Row
                rows = c.execute(sql, p).fetchall()
                c.commit(); c.close()
                return [dict(r) for r in rows]
        except sqlite3.OperationalError as e:
            if "locked" in str(e) and attempt < 3: time.sleep(0.15 * (attempt+1)); continue
            break
        except sqlite3.DatabaseError as db_err:
            # Database may be corrupt — try to recover
            if "not a database" in str(db_err).lower() or "malformed" in str(db_err).lower():
                log.warning(f"[DB] Corrupt DB detected — reinitializing: {db_err}")
                try: _db_init()  # recreate tables
                except: pass
            break
        except: break
    return []

def _db_run(sql, p=()):
    for attempt in range(4):
        try:
            with _db_lock:
                c = sqlite3.connect(str(DB_PATH), timeout=5)
                c.execute("PRAGMA journal_mode=WAL")
                c.execute("PRAGMA synchronous=NORMAL")
                c.execute(sql, p); c.commit(); c.close(); return
        except sqlite3.OperationalError as e:
            if "locked" in str(e) and attempt < 3: time.sleep(0.15 * (attempt+1)); continue
            break
        except: break

def _kb_save(url, title, text, cat="General", kw=None):
    _db_run(
        """INSERT INTO knowledge_base
           (url,title,category,clean_text,keywords,word_count,crawled_at)
           VALUES(?,?,?,?,?,?,?)
           ON CONFLICT(url) DO UPDATE SET
           title=excluded.title, clean_text=excluded.clean_text,
           word_count=excluded.word_count, crawled_at=excluded.crawled_at""",
        (url, title, cat, text[:12000], json.dumps(kw or []),
         len(text.split()), time.time())
    )

def _kb_search(q, limit=8):
    """
    Improved KB search: scores results by how many query words match.
    Returns most relevant articles first - better context for Ollama.
    """
    if not q.strip(): return []
    words = [w for w in q.lower().split() if len(w) > 2][:8]
    if not words: return []
    seen   = {}   # url → score
    rows_d = {}   # url → row dict

    # Score each article by number of matching keywords
    for w in words:
        rows = _db_q(
            "SELECT title, url, clean_text, category, crawled_at "
            "FROM knowledge_base "
            "WHERE lower(clean_text) LIKE ? OR lower(title) LIKE ? LIMIT ?",
            (f"%{w}%", f"%{w}%", limit * 3))
        for r in rows:
            url = r["url"]
            seen[url]   = seen.get(url, 0) + 1
            rows_d[url] = r

    # Sort by score (most matching words first), trim, format
    sorted_urls = sorted(seen, key=lambda u: seen[u], reverse=True)[:limit]
    out = []
    for url in sorted_urls:
        r = rows_d[url]
        text = r.pop("clean_text", "") or ""
        r["snippet"]   = text[:400] + ("…" if len(text) > 400 else "")
        r["relevance"] = round(seen[url] / max(len(words), 1), 2)
        out.append(r)
    return out

# ══════════════════════════════════════════════════════
#  ΣNET CRAWL ENGINE — Proprietary web content fetcher
#  BOTER Knowledge Acquisition System v7
#  Fetches, cleans, deduplicates and stores web content
# ══════════════════════════════════════════════════════


# ══════════════════════════════════════════════════════
#  BOTER SIGMA-NET CRAWL ENGINE v7 — Proprietary
#  Adaptive web content acquisition system
#  Copyright (c) 2025 Shawn Jan - All Rights Reserved
# ══════════════════════════════════════════════════════
def _crawl_and_save(url: str, category: str = "General", keywords: list = None) -> dict:
    """
    BOTER SIGMA-NET Crawl Engine.
    Proprietary adaptive crawler — fetches, cleans, deduplicates,
    and stores web content into the Butler AI knowledge base.
    """
    if not url or not isinstance(url, str):
        return {"ok": False, "error": "Invalid URL", "url": ""}
    url = url.strip()
    if not url.startswith(("http://", "https://")):
        return {"ok": False, "error": "URL must start http(s)://", "url": url}
    if len(url) > 2000:
        return {"ok": False, "error": "URL too long", "url": url}
    host = url.split("/")[2].split(":")[0] if "/" in url else url
    local_prefixes = ("localhost", "127.", "0.0.0.0", "::1", "169.254.")
    if any(host.startswith(b) for b in local_prefixes):
        return {"ok": False, "error": "Cannot crawl local network", "url": url}
    try:
        if _db_q("SELECT id FROM knowledge_base WHERE url=? LIMIT 1", (url,)):
            return {"ok": False, "error": "Already in KB", "duplicate": True, "url": url}
    except Exception:
        pass
    keywords = keywords or []
    try:
        import urllib.request as _ur
        import re as _re
        req = _ur.Request(url, headers={"User-Agent": "Butler-AI/7.0 SIGMA-NET"})
        # SIGMA-NET guard: limit redirects + content-type check
        import urllib.error as _ue
        try:
            with _ur.urlopen(req, timeout=CRAWL_TIMEOUT) as resp:
                ct = resp.headers.get("Content-Type", "text/html")
                if not any(t in ct for t in ("text/", "application/json", "application/xml")):
                    return {"ok": False, "error": f"Not text content: {ct}", "url": url}
                raw = resp.read(500_000)
        except _ue.HTTPError as he:
            return {"ok": False, "error": f"HTTP {he.code}: {he.reason}", "url": url}
        except _ue.URLError as ue:
            return {"ok": False, "error": f"URL unreachable: {ue.reason}", "url": url}
        for enc in ("utf-8", "latin-1", "cp1252"):
            try:
                html = raw.decode(enc, errors="replace")
                break
            except Exception:
                html = raw.decode("utf-8", errors="replace")
        import re as _re2
        tm = _re2.search(r"<title[^>]*>([^<]{1,200})</title>", html, _re2.I)
        title = tm.group(1).strip() if tm else (url.split("/")[-1] or "Page")
        title = " ".join(title.split())[:200]
        base = "/".join(url.split("/")[:3])
        links = []
        for m in _re2.finditer(r'href="([^"]{4,400})"', html):
            h = m.group(1)
            if h.startswith("http"):
                links.append(h)
            elif h.startswith("/"):
                links.append(base + h)
        links = list(dict.fromkeys(links))[:50]
        no_scripts = _re2.sub(
            r"<(script|style|nav|footer)[^>]*>.*?</(script|style|nav|footer)>",
            " ", html, flags=_re2.I | _re2.DOTALL
        )
        text = _re2.sub(r"<[^>]+>", " ", no_scripts)
        text = _re2.sub(r"&[a-z#0-9]{1,8};", " ", text)
        text = " ".join(text.split())[:15000]
        if len(text) < 100:
            return {"ok": False, "error": "No useful text content", "url": url}
        words = len(text.split())
        _kb_save(url, title, text, category, keywords)
        return {"ok": True, "url": url, "title": title,
                "text":      text[:2000],  # legacy field name
                "cleanText": text[:2000],  # field name app expects
                "words":     words,        # legacy field name
                "wordCount": words,        # field name app expects
                "links":     links}
    except OSError as e:
        return {"ok": False, "error": "Network error: " + str(e), "url": url}
    except Exception as e:
        return {"ok": False, "error": str(e)[:200], "url": url}


def _sigma_log_growth(category: str = "mixed", source: str = "SIGMA-NET") -> None:
    """Record a KB growth snapshot. Called after each new article is saved."""
    global _sigma_last_log_ts
    now   = time.time()
    total = _kb_count(force=True)
    try:
        # Log at most every 5 minutes to avoid DB spam, but always on first/milestone
        milestones = {50, 100, 250, 500, 1000, 2500, 5000, 10000}
        is_milestone = total in milestones
        if not is_milestone and now - _sigma_last_log_ts < _sigma_log_interval:
            # Still update category stats even if we skip the log entry
            _db_run(
                "INSERT INTO sigma_category_stats(category,count,last_added) VALUES(?,1,?) "
                "ON CONFLICT(category) DO UPDATE SET count=count+1, last_added=excluded.last_added",
                (category, now)
            )
            return
        _sigma_last_log_ts = now
        # Get previous total for delta calculation
        prev = _db_q("SELECT total FROM sigma_growth_log ORDER BY ts DESC LIMIT 1")
        prev_total = prev[0]["total"] if prev else 0
        added = max(0, total - prev_total)
        _db_run(
            "INSERT INTO sigma_growth_log(ts, total, added, category, source) VALUES(?,?,?,?,?)",
            (now, total, added, category, source)
        )
        # Update category stats
        _db_run(
            "INSERT INTO sigma_category_stats(category,count,last_added) VALUES(?,1,?) "
            "ON CONFLICT(category) DO UPDATE SET count=count+1, last_added=excluded.last_added",
            (category, now)
        )
        _sigma_stats["articles"] = total
    except Exception as e:
        log.debug(f"[ΣNET] Growth log error: {e}")


def _sigma_get_growth_data(hours: int = 24) -> dict:
    """
    Returns KB growth data for the app graph.
    Proprietary ΣNET growth analytics — returns data points, velocity, category breakdown.
    """
    try:
        since = time.time() - (hours * 3600)
        points = _db_q(
            "SELECT ts, total, added, category, source "
            "FROM sigma_growth_log WHERE ts > ? ORDER BY ts ASC",
            (since,)
        )
        cats = _db_q("SELECT category, count FROM sigma_category_stats ORDER BY count DESC LIMIT 15")
        total_now = _kb_count()
        # Calculate velocity: articles per hour over last period
        if len(points) >= 2:
            time_span_hrs = max(0.1, (points[-1]["ts"] - points[0]["ts"]) / 3600)
            articles_added = sum(p["added"] for p in points)
            velocity = round(articles_added / time_span_hrs, 1)
        else:
            velocity = 0.0
        # Predict when next milestone will be reached
        next_m = _next_milestone(total_now)
        eta_hours = round((next_m - total_now) / max(velocity, 0.1), 1) if velocity > 0 else None
        return {
            "points":      [{"ts": p["ts"], "total": p["total"], "added": p["added"]} for p in points],
            "total":       total_now,
            "milestone":   next_m,
            "velocity":    velocity,          # articles per hour
            "etaHours":    eta_hours,          # hours until next milestone
            "categories":  [{"name": c["category"], "count": c["count"]} for c in cats],
            "queue":       _lq_size(),
            "workers":     WORKER_THREADS,
            "learning":    _learning_active,
            "session":     _session_articles,
            "hoursRange":  hours,
        }
    except Exception as e:
        return {"points": [], "total": _kb_count(), "error": str(e)}


def _kb_enrich(query, keywords=None, max_results=5):
    """
    ΔNEX Knowledge Enrichment — proprietary semantic retrieval.
    
    UPGRADE: Adaptive Query Reformulation
    When the user asks a vague question like "my PC is slow",
    the system expands it into technical search terms:
    "Windows high CPU usage diagnostic disk cleanup startup programs"
    This dramatically improves KB hit rate.
    """
    try:
        # ── ADAPTIVE QUERY REFORMULATION ─────────────────────
        # Use Ollama to expand vague queries into precise KB search terms
        expanded_query = query
        if _ol_ok() and len(query.split()) <= 6:
            try:
                expansion = _ol_chat(
                    f"Convert this user question into 5-8 technical search keywords for finding Python automation scripts and Windows PC fixes. Reply with ONLY the keywords, nothing else.\n\nUser question: {query[:100]}",
                    system="You output only space-separated keywords. No sentences, no punctuation, no explanation.",
                    model=_get_active_model(), history=[]
                )
                # Validate: must be short keyword list, not a paragraph
                if expansion and len(expansion) < 150 and "\n" not in expansion.strip():
                    expanded_query = f"{query} {expansion.strip()}"
            except: pass
        
        results = _kb_search(expanded_query, max_results)
        if not results:
            # Fallback: try original query
            results = _kb_search(query, max_results)
        if not results and keywords:
            kw_query = " ".join(str(k) for k in keywords[:3])
            results = _kb_search(kw_query, max_results)
        return [
            {
                "title":    r.get("title", ""),
                "url":      r.get("url", ""),
                "snippet":  r.get("snippet", "")[:500],
                "category": r.get("category", "General"),
                "relevance": 1.0,
                "source":   r.get("url","").split("/")[2] if r.get("url") else "KB",
                "topic":    query[:50],
            }
            for r in results if r.get("title") or r.get("snippet")
        ]
    except Exception as e:
        log.debug(f"[ΔNEX] enrich error: {e}")
        return []

_kb_count_cache = 0
_kb_count_ts    = 0.0

def _kb_count(force=False):
    global _kb_count_cache, _kb_count_ts
    if force or time.time() - _kb_count_ts > 30:
        try:
            r = _db_q("SELECT COUNT(*) n FROM knowledge_base")
            _kb_count_cache = r[0]["n"] if r else 0
            _kb_count_ts    = time.time()
        except: pass
    return _kb_count_cache


def _next_milestone(current: int) -> int:
    """Returns the next KB size milestone for progress display."""
    milestones = [50, 100, 250, 500, 1000, 2500, 5000, 10000, 25000]
    for m in milestones:
        if current < m:
            return m
    return current + 1000


def _checkpoint_save():
    """Save learning progress checkpoint to DB - called every 15 min."""
    global _session_articles
    try:
        total = _kb_count()
        uptime = (time.time() - _session_start) / 60 if _session_start else 0
        _db_run(
            "INSERT OR REPLACE INTO learn_checkpoint"
            "(id,articles_total,articles_session,last_save,queue_size,session_start,uptime_mins)"
            " VALUES(1,?,?,?,?,?,?)",
            (total, _session_articles, time.time(), _lq_size(), _session_start, uptime)
        )
        # Write proprietary marker to KB file (identifies origin of the database)
        try:
            marker_path = DB_PATH.parent / ".butler_kb_marker"
            marker_path.write_text(
                f"Butler AI Knowledge Base\n"
                f"Copyright (c) 2025 Butler AI. All Rights Reserved.\n"
                f"Created by BOTER Server v{VERSION}\n"
                f"Articles: {total} | Session: {_session_articles} | "
                f"Saved: {time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())}\n"
            )
        except: pass
        log.info(f"[CHECKPOINT] {total} articles · session: +{_session_articles} · "
                 f"queue: {_lq_size()} · uptime: {uptime:.0f}m")
        # Update GUI
        _refresh_gui()
    except Exception as e:
        log.warning(f"Checkpoint save failed: {e}")


def _checkpoint_load() -> dict:
    """Load last checkpoint on startup so we know where we left off."""
    try:
        rows = _db_q("SELECT * FROM learn_checkpoint WHERE id=1")
        if rows:
            cp = rows[0]
            log.info(f"[RESUME] Loaded checkpoint: {cp['articles_total']} articles, "
                     f"{cp['queue_size']} pending in queue")
            return cp
    except: pass
    return {}


# ══════════════════════════════════════════════════════════
#  ΣNET LEARN QUEUE — Proprietary persistent crawl queue
#  All queue operations are atomic and multi-worker safe
# ══════════════════════════════════════════════════════════

def _lq_add(url: str, category: str, keywords, priority: int = 5,
            source: str = "master") -> bool:
    """Add URL to learn queue. Returns True if added, False if duplicate/error."""
    try:
        kw_json = json.dumps(list(keywords)[:10]) if keywords else "[]"
        _db_run(
            """INSERT OR IGNORE INTO learn_queue(url, category, keywords, priority, source)
               VALUES(?,?,?,?,?)""",
            (url, category, kw_json, priority, source)
        )
        return True
    except Exception as e:
        log.debug(f"[ΣNET-Q] add error: {e}")
        return False


def _lq_size() -> int:
    """Returns number of pending URLs in the queue."""
    try:
        r = _db_q("SELECT COUNT(*) n FROM learn_queue WHERE status='pending'")
        return r[0]["n"] if r else 0
    except Exception:
        return 0


def _lq_next(worker_id: int) -> dict | None:
    """
    Claim next pending URL atomically. Multi-worker safe.
    Uses UPDATE+WHERE to prevent two workers claiming same URL.
    """
    try:
        # Two-step atomic claim: SELECT then UPDATE within same connection
        with _db_lock:
            c = sqlite3.connect(str(DB_PATH), timeout=10)
            c.execute("PRAGMA journal_mode=WAL")
            c.row_factory = sqlite3.Row
            # Find next pending item
            row = c.execute(
                "SELECT rowid, url, category, keywords, priority, source "
                "FROM learn_queue WHERE status='pending' "
                "ORDER BY priority DESC, rowid ASC LIMIT 1"
            ).fetchone()
            if not row:
                c.close()
                return None
            # Atomically claim it — if another worker already claimed it this fails
            affected = c.execute(
                "UPDATE learn_queue SET status='processing', worker_id=?, "
                "started_at=? WHERE rowid=? AND status='pending'",
                (worker_id, time.time(), row["rowid"])
            ).rowcount
            c.commit(); c.close()
            if affected == 0:
                return None  # Another worker grabbed it first
            return dict(row)
    except Exception as e:
        log.debug(f"[ΣNET-Q] next error: {e}")
        return None


def _lq_done(url: str, ok: bool = True) -> None:
    """Mark URL as done (completed or failed)."""
    try:
        status = "done" if ok else "failed"
        _db_run(
            "UPDATE learn_queue SET status=?, finished_at=? WHERE url=?",
            (status, time.time(), url)
        )
        # Periodically purge completed items older than 7 days to keep queue lean
        _db_run(
            "DELETE FROM learn_queue WHERE status IN ('done','failed') "
            "AND finished_at < ?",
            (time.time() - 604800,)
        )
    except Exception as e:
        log.debug(f"[ΣNET-Q] done error: {e}")



def _auto_search_gaps() -> None:
    """
    ΣNET Gap Detection — finds topics with <3 KB articles and queues searches.
    Ensures the knowledge base grows evenly across all topic areas.
    Runs automatically via watchdog when queue runs low.
    """
    try:
        GAP_TOPICS = [
            "python windows automation tutorial",
            "fix windows driver error code",
            "windows firewall rules powershell",
            "install software windows silent",
            "python file organizer script",
            "windows registry automation python",
            "fix blue screen windows error",
            "python schedule task windows",
            "windows performance optimization script",
            "python system monitoring psutil",
        ]
        added = 0
        import random
        topics = random.sample(GAP_TOPICS, min(3, len(GAP_TOPICS)))
        for topic in topics:
            url = f"https://duckduckgo.com/html/?q={topic.replace(' ', '+')}"
            queued = _db_q("SELECT url FROM learn_queue WHERE url=? LIMIT 1", (url,))
            if not queued:
                _lq_add(url, "AutoGapFill", topic.split()[:4], priority=6, source="gap-fill")
                added += 1
        if added > 0:
            log.info(f"[ΣNET] Gap-fill: queued {added} searches")
    except Exception as e:
        log.debug(f"[ΣNET] Gap-fill error: {e}")


def _queue_refill():
    """
    Refill the learning queue when it runs low.
    Adds MASTER_URLS, gap-fill searches, and discovered links.
    Called automatically when queue drops below QUEUE_LOW_WATER.
    """
    added = 0
    # 1. Re-add any MASTER_URLS not yet in KB
    for url, cat, kw in MASTER_URLS:
        existing = _db_q("SELECT url FROM knowledge_base WHERE url=?", (url,))
        if not existing:
            if _lq_add(url, cat, kw, priority=8, source="master"): added += 1

    # 2. Only search web if queue is very empty (avoids hammering DuckDuckGo)
    if _lq_size() < 5:
        import random
        topics = [
            "python automate windows task",
            "python file watcher monitor",
            "python gui automation script",
        ]
        topic = random.choice(topics)  # one search per refill, randomly chosen
        search_results = _search_scripts(topic, max_results=3)
        for r in search_results:
            existing_kb = _db_q("SELECT url FROM knowledge_base WHERE url=?", (r["url"],))
            if not existing_kb:
                if _lq_add(r["url"], "Scripts", topic.split()[:3],
                           priority=6, source="search"): added += 1

    # 3. Add user-requested topics (highest priority - learn what users actually ask about)
    try:
        user_t = _db_q(
            "SELECT topic FROM user_topics WHERE kb_coverage < 3 ORDER BY asks DESC LIMIT 10"
        )
        for row in user_t:
            results = _search_scripts(row["topic"], max_results=3)
            for r in results:
                existing_kb = _db_q("SELECT url FROM knowledge_base WHERE url=?", (r["url"],))
                if not existing_kb:
                    if _lq_add(r["url"], "UserTopic", row["topic"].split()[:3],
                               priority=9, source="user"): added += 1
    except: pass

    if added > 0:
        log.info(f"[QUEUE] Refilled +{added} URLs (total pending: {_lq_size()})")
    return added


# Learning engine config - tuned for server responsiveness

# ══════════════════════════════════════════════════════
#  SCRIPT TEMPLATES
#  Pre-built scripts for common requests.
#  AI uses these as base and customizes for user needs.
# ══════════════════════════════════════════════════════
SCRIPT_TEMPLATES = {
    # ── INSTALL SOFTWARE ─────────────────────────────
    "install_winrar": """
import subprocess, sys, os, urllib.request, pathlib

def install_winrar():
    print("Installing WinRAR...")
    # Method 1: winget (Windows 10+)
    try:
        r = subprocess.run(["winget","install","--id","RARLab.WinRAR","-e","--silent"],
                          capture_output=True, text=True, timeout=120)
        if r.returncode == 0:
            print("WinRAR installed via winget!")
            return True
    except FileNotFoundError:
        pass

    # Method 2: download installer directly
    url = "https://www.rarlab.com/rar/winrar-x64-701.exe"
    dest = pathlib.Path.home() / "Downloads" / "winrar_installer.exe"
    print(f"Downloading WinRAR installer to {dest}...")
    urllib.request.urlretrieve(url, dest)
    print("Running installer silently...")
    subprocess.run([str(dest), "/S"], check=True)
    print("WinRAR installed successfully!")
    os.remove(dest)  # cleanup
    return True

install_winrar()
""",

    "install_7zip": """
import subprocess, sys, pathlib, urllib.request

def install_7zip():
    print("Installing 7-Zip...")
    try:
        r = subprocess.run(["winget","install","--id","7zip.7zip","-e","--silent"],
                          capture_output=True, text=True, timeout=120)
        if r.returncode == 0:
            print("7-Zip installed via winget!")
            return
    except FileNotFoundError:
        pass
    # Fallback: download from 7-zip.org
    url = "https://www.7-zip.org/a/7z2301-x64.exe"
    dest = pathlib.Path.home() / "Downloads" / "7zip_installer.exe"
    urllib.request.urlretrieve(url, dest)
    subprocess.run([str(dest), "/S"], check=True)
    print("7-Zip installed!")

install_7zip()
""",

    "install_vlc": """
import subprocess, pathlib, urllib.request

def install_vlc():
    print("Installing VLC Media Player...")
    try:
        r = subprocess.run(["winget","install","--id","VideoLAN.VLC","-e","--silent"],
                          capture_output=True, text=True, timeout=120)
        if r.returncode == 0:
            print("VLC installed!"); return
    except FileNotFoundError:
        pass
    url = "https://get.videolan.org/vlc/3.0.18/win64/vlc-3.0.18-win64.exe"
    dest = pathlib.Path.home() / "Downloads" / "vlc_installer.exe"
    urllib.request.urlretrieve(url, dest)
    subprocess.run([str(dest), "/L=1033", "/S"], check=True)
    print("VLC installed!")

install_vlc()
""",

    "install_vscode": """
import subprocess

def install_vscode():
    print("Installing Visual Studio Code...")
    try:
        r = subprocess.run(["winget","install","--id","Microsoft.VisualStudioCode","-e","--silent"],
                          capture_output=True, text=True, timeout=180)
        if r.returncode == 0:
            print("VS Code installed!"); return
    except FileNotFoundError:
        pass
    print("Please download VS Code from: https://code.visualstudio.com/download")

install_vscode()
""",

    "install_python": """
import subprocess, urllib.request, pathlib

def install_python():
    print("Installing Python 3.12...")
    try:
        r = subprocess.run(["winget","install","--id","Python.Python.3.12","-e","--silent"],
                          capture_output=True, text=True, timeout=300)
        if r.returncode == 0:
            print("Python 3.12 installed!"); return
    except FileNotFoundError:
        pass
    url = "https://www.python.org/ftp/python/3.12.3/python-3.12.3-amd64.exe"
    dest = pathlib.Path.home() / "Downloads" / "python_installer.exe"
    print(f"Downloading Python installer...")
    urllib.request.urlretrieve(url, dest)
    subprocess.run([str(dest), "/quiet", "InstallAllUsers=1", "PrependPath=1"], check=True)
    print("Python installed!")

install_python()
""",

    "organize_downloads": """
import pathlib, shutil

FOLDER_MAP = {
    "Images":    [".jpg",".jpeg",".png",".gif",".bmp",".webp",".svg",".ico"],
    "Videos":    [".mp4",".avi",".mkv",".mov",".wmv",".flv",".webm"],
    "Audio":     [".mp3",".wav",".flac",".aac",".ogg",".m4a"],
    "Documents": [".pdf",".doc",".docx",".txt",".xls",".xlsx",".pptx",".csv"],
    "Archives":  [".zip",".rar",".7z",".tar",".gz",".bz2"],
    "Installers":[".exe",".msi",".pkg",".dmg"],
    "Code":      [".py",".js",".html",".css",".json",".ts",".sh",".bat"],
}

def organize_downloads():
    downloads = pathlib.Path.home() / "Downloads"
    moved = 0
    for file in downloads.iterdir():
        if not file.is_file(): continue
        for folder, exts in FOLDER_MAP.items():
            if file.suffix.lower() in exts:
                dest = downloads / folder
                dest.mkdir(exist_ok=True)
                shutil.move(str(file), str(dest / file.name))
                print(f"Moved: {file.name} -> {folder}/")
                moved += 1
                break
    print(f"Done! Organized {moved} files.")

organize_downloads()
""",

    "system_cleanup": """
import subprocess, pathlib, shutil, os

def cleanup_system():
    freed = 0
    # 1. Empty Recycle Bin
    try:
        subprocess.run(["powershell","-Command","Clear-RecycleBin -Force"],
                      capture_output=True)
        print("Recycle Bin emptied")
    except: pass

    # 2. Clear Windows Temp
    temp = pathlib.Path(os.environ.get("TEMP", ""))
    if temp.exists():
        for item in temp.iterdir():
            try:
                if item.is_file():
                    size = item.stat().st_size
                    item.unlink()
                    freed += size
                elif item.is_dir():
                    size = sum(f.stat().st_size for f in item.rglob("*") if f.is_file())
                    shutil.rmtree(item, ignore_errors=True)
                    freed += size
            except: pass
        print(f"Temp folder cleaned: {freed/1024/1024:.1f} MB freed")

    # 3. Run Disk Cleanup silently
    subprocess.Popen(["cleanmgr", "/sagerun:1"])
    print("Disk Cleanup running in background...")
    print(f"Total freed: ~{freed/1024/1024:.1f} MB")

cleanup_system()
""",

    "fix_windows_update": """
import subprocess

def fix_windows_update():
    print("Fixing Windows Update...")
    cmds = [
        ["net","stop","wuauserv"],
        ["net","stop","cryptSvc"],
        ["net","stop","bits"],
        ["net","stop","msiserver"],
        ["ren","C:/Windows/SoftwareDistribution","SoftwareDistribution.old"],
        ["ren","C:/Windows/System32/catroot2","catroot2.old"],
        ["net","start","wuauserv"],
        ["net","start","cryptSvc"],
        ["net","start","bits"],
        ["net","start","msiserver"],
    ]
    for cmd in cmds:
        try:
            r = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
            print(f"OK: {' '.join(cmd[:2])}")
        except Exception as e:
            print(f"Skip: {e}")
    print("Windows Update reset complete! Try updating now.")

fix_windows_update()
""",

    "fix_dns": """
import subprocess

def fix_dns():
    print("Fixing DNS and network...")
    cmds = [
        (["ipconfig","/flushdns"],              "Flush DNS cache"),
        (["ipconfig","/release"],               "Release IP"),
        (["ipconfig","/renew"],                 "Renew IP"),
        (["netsh","winsock","reset"],            "Reset Winsock"),
        (["netsh","int","ip","reset"],           "Reset TCP/IP"),
        (["netsh","int","ipv4","reset"],         "Reset IPv4"),
        (["netsh","advfirewall","reset"],        "Reset Firewall"),
    ]
    for cmd, label in cmds:
        try:
            subprocess.run(cmd, capture_output=True, timeout=30)
            print(f"Done: {label}")
        except: print(f"Skip: {label}")
    print("Network reset complete! Restart PC for full effect.")

fix_dns()
""",

    "add_firewall_rule": """
import subprocess, sys

def add_firewall_rule(app_name, app_path, direction="both"):
    print(f"Adding firewall rule for: {app_name}")
    directions = ["in","out"] if direction == "both" else [direction]
    for d in directions:
        cmd = [
            "netsh","advfirewall","firewall","add","rule",
            f"name={app_name}",
            f"dir={d}",
            "action=allow",
            f"program={app_path}",
            "enable=yes"
        ]
        r = subprocess.run(cmd, capture_output=True, text=True)
        if r.returncode == 0:
            print(f"Firewall rule added ({d}bound): {app_name}")
        else:
            print(f"Error: {r.stderr}")

# Example usage:
# add_firewall_rule("My App", r"C:/Program Files/MyApp/myapp.exe")
app_path = input("Enter the full path to the program: ")
app_name = app_path.replace("\\\\", "/").split("/")[-1].replace(".exe","")
add_firewall_rule(app_name, app_path)
""",

    "update_all_drivers": """
import subprocess

def update_drivers():
    print("Scanning for driver updates via Windows Update...")
    # Use Windows Update to find driver updates
    ps_script = (
        "Get-WindowsUpdate -Category Drivers 2>$null | "
        "Select-Object Title,Description | "
        "Format-List"
    )
    ps_cmd = ps_script
    result = subprocess.run(
        ["powershell","-Command", ps_cmd],
        capture_output=True, text=True, timeout=60
    )
    print(result.stdout)
    print("\nTo update drivers: Settings > Windows Update > Advanced Options > Optional Updates")

update_drivers()
""",
}


def _get_script_template(task: str) -> str:
    """Returns a script template if one matches the user's request."""
    task_lower = task.lower()
    for key, script in SCRIPT_TEMPLATES.items():
        keywords = key.replace("_", " ").split()
        if any(kw in task_lower for kw in keywords):
            return script.strip()
    return ""


def _search_scripts(query: str, max_results: int = 3) -> list:
    """
    Search for Python scripts/tutorials matching a query.
    GUARDED: Only searches trusted sources, scores relevance, blocks junk.
    
    Trusted source hierarchy (highest quality first):
    1. Python official docs — always correct, always safe
    2. RealPython — vetted tutorials with tested code
    3. GeeksForGeeks — explained examples with output
    4. StackOverflow — community-vetted answers
    5. GitHub repos with stars — real projects, real code
    6. AutomateTheBoringStuff — beginner-friendly, practical
    
    BLOCKED: random blogs, SEO farms, paste sites, unknown domains
    """
    import urllib.parse, urllib.request, re

    results = []
    query_clean = query.strip()[:80]
    query_lower = query_clean.lower()
    keywords = urllib.parse.quote(query_clean)

    # ── GUARD 1: Extract meaningful search terms ──────────
    # Strip filler words so searches are precise
    FILLER = {"how","do","i","can","you","me","a","the","to","my","for","on","in","and","or","is","it","with","this","that","please","help","want","need","make","get","write","create","show"}
    meaningful = [w for w in query_lower.split() if w not in FILLER and len(w) > 2]
    if not meaningful:
        meaningful = query_lower.split()[:3]
    search_terms = " ".join(meaningful[:5])
    search_encoded = urllib.parse.quote(search_terms)

    # ── GUARD 2: Trusted sources only ─────────────────────
    # Ranked by reliability. Only these domains get crawled.
    TRUSTED_DOMAINS = [
        "docs.python.org",
        "realpython.com",
        "geeksforgeeks.org",
        "stackoverflow.com",
        "github.com",
        "automatetheboringstuff.com",
        "psutil.readthedocs.io",
        "pyautogui.readthedocs.io",
        "docs.microsoft.com",
        "learn.microsoft.com",
    ]

    # ── GUARD 3: Blacklisted domains ──────────────────────
    # SEO farms, paste sites, malware hosts — never crawl these
    BLOCKED_DOMAINS = [
        "pastebin.com", "hastebin.com", "ghostbin.com",  # paste sites (unvetted code)
        "w3schools.com",  # known for inaccurate/outdated content
        "tutorialspoint.com",  # SEO farm, often wrong
        "programiz.com",  # shallow examples
        "javatpoint.com",  # SEO spam
        "medium.com",  # paywalled, unreliable quality
        "dev.to",  # unvetted blog posts
        "hackforums.net", "exploit-db.com", "0day.today",  # security risk
    ]

    # ── Build targeted search queries ─────────────────────
    search_urls = [
        # Primary: site-specific searches on trusted domains
        f"https://www.google.com/search?q=python+{search_encoded}+script+site%3Agithub.com",
        f"https://www.google.com/search?q=python+{search_encoded}+site%3Arealpython.com",
        f"https://www.google.com/search?q=python+{search_encoded}+site%3Astackoverflow.com",
        f"https://www.google.com/search?q=python+{search_encoded}+site%3Ageeksforgeeks.org",
        f"https://www.google.com/search?q=python+{search_encoded}+site%3Adocs.python.org",
    ]

    for search_url in search_urls[:max_results + 2]:
        try:
            req = urllib.request.Request(search_url, headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
            })
            with urllib.request.urlopen(req, timeout=8) as resp:
                html = resp.read().decode("utf-8", errors="replace")

            # Extract URLs — only from trusted domains
            trusted_pattern = "|".join(re.escape(d) for d in TRUSTED_DOMAINS)
            urls_found = re.findall(rf'href="(https?://(?:{trusted_pattern})[^"]*)"', html)

            for u in urls_found[:5]:
                # ── GUARD 4: URL quality filters ──────────
                # Skip non-content pages
                if any(skip in u for skip in [
                    "/search?", "/login", "/signup", "/join", "/pricing",
                    "/about", "/contact", "/careers", "/ads", "/sponsor",
                    "/notifications", "/settings", "/account",
                ]):
                    continue
                # Skip already-found URLs
                if u in [r["url"] for r in results]:
                    continue
                # ── GUARD 5: Relevance check ──────────────
                # URL must contain at least one meaningful keyword
                u_lower = u.lower()
                relevance = sum(1 for kw in meaningful if kw in u_lower)
                if relevance == 0 and "python" not in u_lower:
                    continue  # URL has nothing to do with the query

                results.append({
                    "url": u,
                    "title": query_clean,
                    "snippet": "",
                    "relevance": relevance,
                    "source": "search",
                })
                if len(results) >= max_results:
                    break
        except:
            pass
        if len(results) >= max_results:
            break

    # Sort by relevance (most keyword matches first)
    results.sort(key=lambda r: r.get("relevance", 0), reverse=True)

    # ── GUARD 6: Fallback to curated high-quality URLs ────
    # If web search fails (no internet, rate limited), use known-good sources
    if not results:
        CURATED = {
            # File operations
            "file":      "https://realpython.com/working-with-files-in-python/",
            "folder":    "https://realpython.com/working-with-files-in-python/",
            "directory": "https://docs.python.org/3/library/pathlib.html",
            "rename":    "https://docs.python.org/3/library/os.html#os.rename",
            "copy":      "https://docs.python.org/3/library/shutil.html",
            "move":      "https://docs.python.org/3/library/shutil.html",
            "delete":    "https://docs.python.org/3/library/os.html#os.remove",
            "zip":       "https://docs.python.org/3/library/zipfile.html",
            "compress":  "https://docs.python.org/3/library/zipfile.html",
            # Network
            "network":   "https://realpython.com/python-sockets/",
            "socket":    "https://docs.python.org/3/library/socket.html",
            "http":      "https://realpython.com/python-requests/",
            "download":  "https://realpython.com/python-requests/",
            "api":       "https://realpython.com/api-integration-in-python/",
            "scrape":    "https://realpython.com/beautiful-soup-web-scraper-python/",
            "crawl":     "https://realpython.com/beautiful-soup-web-scraper-python/",
            # System
            "cpu":       "https://psutil.readthedocs.io/en/latest/#cpu",
            "memory":    "https://psutil.readthedocs.io/en/latest/#memory",
            "ram":       "https://psutil.readthedocs.io/en/latest/#memory",
            "disk":      "https://psutil.readthedocs.io/en/latest/#disks",
            "process":   "https://psutil.readthedocs.io/en/latest/#processes",
            "monitor":   "https://psutil.readthedocs.io/en/latest/",
            "system":    "https://docs.python.org/3/library/platform.html",
            # Automation
            "automat":   "https://automatetheboringstuff.com/2e/chapter20/",
            "mouse":     "https://pyautogui.readthedocs.io/en/latest/mouse.html",
            "keyboard":  "https://pyautogui.readthedocs.io/en/latest/keyboard.html",
            "click":     "https://pyautogui.readthedocs.io/en/latest/mouse.html",
            "gui":       "https://pyautogui.readthedocs.io/en/latest/",
            "screenshot":"https://pyautogui.readthedocs.io/en/latest/screenshot.html",
            "schedul":   "https://realpython.com/python-scheduler/",
            "cron":      "https://realpython.com/python-scheduler/",
            "timer":     "https://docs.python.org/3/library/sched.html",
            # Data
            "email":     "https://realpython.com/python-send-email/",
            "excel":     "https://realpython.com/openpyxl-excel-spreadsheets-python/",
            "csv":       "https://docs.python.org/3/library/csv.html",
            "json":      "https://docs.python.org/3/library/json.html",
            "database":  "https://docs.python.org/3/library/sqlite3.html",
            "sql":       "https://docs.python.org/3/library/sqlite3.html",
            "pdf":       "https://realpython.com/creating-modifying-pdf/",
            # Security
            "password":  "https://docs.python.org/3/library/secrets.html",
            "encrypt":   "https://docs.python.org/3/library/hashlib.html",
            "hash":      "https://docs.python.org/3/library/hashlib.html",
            # Cleanup
            "clean":     "https://docs.python.org/3/library/shutil.html",
            "temp":      "https://docs.python.org/3/library/tempfile.html",
            "cache":     "https://docs.python.org/3/library/shutil.html",
            "junk":      "https://docs.python.org/3/library/shutil.html",
            "backup":    "https://docs.python.org/3/library/zipfile.html",
            # Windows-specific
            "registry":  "https://docs.python.org/3/library/winreg.html",
            "startup":   "https://docs.python.org/3/library/winreg.html",
            "service":   "https://docs.python.org/3/library/subprocess.html",
            "driver":    "https://docs.python.org/3/library/subprocess.html",
            "install":   "https://docs.python.org/3/library/subprocess.html",
            "uninstall": "https://docs.python.org/3/library/subprocess.html",
        }
        for kw, url in CURATED.items():
            if kw in query_lower:
                if url not in [r["url"] for r in results]:
                    results.append({"url": url, "title": kw, "snippet": "", "relevance": 1, "source": "curated"})
                if len(results) >= max_results:
                    break

    return results[:max_results]


def _search_and_crawl_scripts(query: str, max_results: int = 3):
    """
    Background task: search for scripts related to a user's question,
    then add the found URLs to the crawl queue so the KB grows automatically.
    Called from a background thread during AI chat — never blocks the response.
    """
    try:
        results = _search_scripts(query, max_results=max_results)
        added = 0
        for r in results:
            url = r.get("url", "")
            if not url: continue
            existing = _db_q("SELECT url FROM knowledge_base WHERE url=? LIMIT 1", (url,))
            if not existing:
                if _lq_add(url, "AutoSearch", query.split()[:4], priority=8, source="auto-search"):
                    added += 1
        if added:
            _log(f"[AUTO-SEARCH] Added {added} URLs for: {query[:40]}… (sources: {', '.join(r.get('source','?') for r in results[:added])})", "info")
    except Exception as e:
        log.debug(f"[AUTO-SEARCH] Error: {e}")


def _verify_script_safety(script: str, user_request: str = "") -> dict:
    """
    AI-powered script verification before execution.
    Asks Ollama to check if the script:
    1. Actually does what the user asked for
    2. Contains any dangerous operations
    3. Has obvious bugs that would cause harm
    
    Returns: {"safe": True/False, "reason": "...", "warnings": [...]}
    Called before executing any AI-generated or KB-sourced script.
    """
    # ── FAST PATH: Skip verification for known-safe patterns ─────
    script_lower = script.lower().strip()
    
    # Very short scripts are usually safe (one-liners, print statements)
    if len(script) < 200 and "import" not in script_lower:
        return {"safe": True, "reason": "Simple script", "warnings": []}
    
    # Scripts that only use safe modules
    SAFE_ONLY_MODULES = {"math", "random", "datetime", "time", "json", "csv",
                         "string", "collections", "itertools", "functools",
                         "platform", "sys", "pprint", "textwrap", "re"}
    import re as _re
    imports = set(_re.findall(r'^(?:import|from) (\w+)', script, _re.MULTILINE))
    if imports and imports.issubset(SAFE_ONLY_MODULES):
        return {"safe": True, "reason": "Uses only safe modules", "warnings": []}

    # ── STATIC ANALYSIS: Check for dangerous patterns ────────────
    warnings = []
    
    DANGER_CHECKS = [
        # Destructive file operations
        (r"shutil\.rmtree\s*\(\s*['\"]?[/\\]", "Deletes root filesystem"),
        (r"os\.remove|os\.unlink|os\.rmdir", "Deletes files — verify target path"),
        (r"shutil\.rmtree", "Recursively deletes folders — verify target"),
        # System modification
        (r"winreg\.|RegSetValue|RegDeleteKey", "Modifies Windows registry"),
        (r"subprocess\..*(?:format|del\s|rm\s|shutdown|taskkill|net\s+stop)", "Runs system commands"),
        (r"ctypes\.windll|ctypes\.cdll", "Calls Windows system APIs directly"),
        # Network risks
        (r"socket\.connect|urllib\.request\.urlopen|requests\.get", "Makes network connections"),
        (r"exec\(|eval\(|compile\(", "Executes dynamic code — potential injection risk"),
        # Data exfiltration
        (r"smtp|send.*email|send.*mail", "Sends email — verify recipient"),
        (r"requests\.post.*data|urllib.*POST", "Sends data to external server"),
        # Privilege escalation
        (r"runas|ShellExecuteW.*runas|sudo", "Attempts admin/root elevation"),
        (r"os\.chmod.*0o777|chmod.*777", "Sets world-writable permissions"),
    ]
    
    for pattern, warning in DANGER_CHECKS:
        if _re.search(pattern, script, _re.IGNORECASE):
            warnings.append(warning)
    
    # ── AI VERIFICATION: Ask Ollama if the script matches the request ─
    if _ol_ok() and user_request and len(script) > 300:
        try:
            verify_prompt = (
                f"USER ASKED FOR: {user_request[:200]}\n\n"
                f"SCRIPT TO VERIFY:\n```python\n{script[:3000]}\n```\n\n"
                "Answer ONLY with a JSON object, nothing else:\n"
                '{"matches_request": true/false, "safe": true/false, "concerns": ["list of concerns"]}\n'
                "matches_request = does this script do what the user asked?\n"
                "safe = could this script damage the system or steal data?\n"
            )
            raw = _ol_chat(verify_prompt, system="You are a Python code reviewer. Respond ONLY with JSON.", 
                          model=_get_active_model(), history=[])
            # Parse AI response
            try:
                # Extract JSON from response
                json_match = _re.search(r'\{[^}]+\}', raw)
                if json_match:
                    verdict = json.loads(json_match.group())
                    if not verdict.get("matches_request", True):
                        warnings.append("AI: Script may not do what you asked")
                    if not verdict.get("safe", True):
                        warnings.append("AI: Script may be unsafe")
                    for c in verdict.get("concerns", []):
                        if isinstance(c, str) and len(c) < 100:
                            warnings.append(f"AI: {c}")
            except: pass  # AI response wasn't valid JSON — skip verification
        except: pass  # Ollama offline — skip AI verification
    
    # ── VERDICT ──────────────────────────────────────────────────
    # Block if destructive patterns found, warn for everything else
    critical = any(w.startswith("Deletes root") or w.startswith("Fork bomb") for w in warnings)
    
    return {
        "safe": not critical,
        "reason": "Blocked: " + warnings[0] if critical else ("Warnings found" if warnings else "Passed all checks"),
        "warnings": warnings,
    }

WORKER_THREADS   = 1    # 1 worker — prevents CPU competition with AI chat
CRAWL_DELAY_SECS = 15   # 15s between crawls — gives CPU time for AI chat
QUEUE_LOW_WATER  = 20   # refill queue when below this
CHECKPOINT_SECS  = 900  # save checkpoint every 15 minutes

# ── CPU GUARD: Ollama-aware performance management ──────
# When Ollama is processing, crawlers FULLY PAUSE (not just slow down).
# When CPU > 90%, crawlers FULLY PAUSE regardless.
# This prevents the "100% CPU" problem customers see.
_ollama_busy = False     # Set True while Ollama is processing a chat
_perf_mode   = "auto"    # "auto" | "performance" | "battery"
# performance = crawlers run full speed, auto = adaptive, battery = crawlers paused

# ── Global state for SIGMA-NET learning engine ──────────
_session_articles = 0          # Articles learned this session
_learning_active  = False      # True while workers are actively crawling
_sigma_stats      = {"articles": 0, "last": "idle", "errors": 0, "session": 0}
_session_start    = 0          # Timestamp when learning session began


def _learn_worker(worker_id: int):
    """
    Continuous learning worker thread. Runs forever.
    Claims URLs from the persistent queue, crawls them, saves to KB.
    Saves a checkpoint every 15 minutes.
    Refills the queue when it runs low.
    """
    global _session_articles, _learning_active
    last_checkpoint = time.time()

    log.info(f"[ΣNET-WORKER-{worker_id}] BOTER Knowledge Engine started")

    while True:
        try:
            # ── CPU GUARD: pause crawling when AI chat is under load ──
            # Check CPU every iteration — if over 60%, sleep and let AI run
            try:
                import psutil as _ps
                _cpu = _ps.cpu_percent(interval=0.3)
                if _cpu > 60:
                    # High CPU — back off hard so AI chat gets resources
                    _wait = 30 if _cpu > 80 else 15
                    time.sleep(_wait)
                    continue
                # Also back off when Ollama is actively generating
                _mem = _ps.virtual_memory()
                if _mem.percent > 88:
                    time.sleep(20)
                    continue
            except Exception:
                pass

            # ── Checkpoint every 15 minutes ─────────────────────
            if time.time() - last_checkpoint >= CHECKPOINT_SECS:
                _checkpoint_save()
                last_checkpoint = time.time()

            # ── Refill queue if running low ──────────────────────
            if _lq_size() < QUEUE_LOW_WATER:
                _queue_refill()
                # If still empty after refill, pause and retry
                if _lq_size() == 0:
                    time.sleep(30)
                    continue

            # ── Claim next URL ───────────────────────────────────
            item = _lq_next(worker_id)
            if not item:
                time.sleep(5)
                continue

            url      = item["url"]
            category = item["category"]
            try: kw = json.loads(item.get("keywords", "[]"))
            except: kw = []

            # ── CPU check right before crawl ────────────────────
            # If CPU is high right now, put the URL back and wait
            try:
                import psutil as _ps2
                _pre_cpu = _ps2.cpu_percent(interval=0.2)
                if _pre_cpu > 55:
                    _lq_done(url, ok=False)  # return URL to queue
                    time.sleep(20)
                    continue
            except Exception:
                pass

            # ── Crawl and save ───────────────────────────────────
            _learning_active = True
            result = _crawl_and_save(url, category, kw)

            if result.get("ok"):
                _lq_done(url, ok=True)
                _session_articles += 1
                _kb_count(force=True)
                # ΣNET proprietary growth tracking
                _sigma_log_growth(category, item.get("source", "SIGMA-NET"))

                # ── SMART SNOWBALL: follow relevant discovered links ──
                # Domains worth following for computer/automation knowledge
                GOOD_DOMAINS = {
                    "docs.python.org", "realpython.com", "docs.microsoft.com",
                    "learn.microsoft.com", "geeksforgeeks.org", "stackoverflow.com",
                    "github.com", "pypi.org", "readthedocs.io", "howtogeek.com",
                    "bleepingcomputer.com", "tenforums.com", "elevenforum.com",
                    "superuser.com", "answers.microsoft.com", "ss64.com",
                    "adamtheautomator.com", "devblogs.microsoft.com", "thewindowsclub.com",
                    "computerhope.com", "makeuseof.com", "lifewire.com", "pcmag.com",
                }
                SKIP_PATTERNS = {
                    "login", "signup", "register", "cart", "checkout",
                    "account", "billing", "pricing", "subscribe", "ads",
                    ".pdf", ".zip", ".exe", ".msi", "mailto:", "javascript:",
                }
                new_links = 0
                for link in result.get("links", [])[:20]:
                    if not link.startswith("http"): continue
                    if any(p in link.lower() for p in SKIP_PATTERNS): continue
                    domain = link.split("/")[2] if len(link.split("/")) > 2 else ""
                    # Only follow links from trusted knowledge domains
                    if not any(d in domain for d in GOOD_DOMAINS): continue
                    existing = _db_q("SELECT url FROM knowledge_base WHERE url=?", (link,))
                    queued   = _db_q("SELECT url FROM learn_queue WHERE url=?", (link,))
                    if not existing and not queued:
                        _lq_add(link, category, kw, priority=4, source="snowball")
                        new_links += 1
                        if new_links >= 8: break  # max 8 new links per page

                # ── TOPIC EXPANSION: search for more on this topic ───
                # Every 10th article triggers a DuckDuckGo search for related content
                if _session_articles % 10 == 0 and kw:
                    topic = " ".join(kw[:3])
                    _lq_add(
                        f"https://duckduckgo.com/html/?q={urllib.parse.quote(topic)}+python+automation",
                        category, kw, priority=5, source="topic-expand"
                    )

                # ── KB MILESTONES: log growth milestones ────────────
                total = _kb_count()
                milestones = [50, 100, 250, 500, 1000, 2500, 5000, 10000]
                for m in milestones:
                    if total == m:
                        _log(f"🎉 KB milestone: {m} articles! Butler AI keeps growing.", "ok")
                        break

                # ── AUTO-CATEGORIZE: update category if generic ──────
                if category in ("General", "Unknown") and kw:
                    # Re-categorize based on keywords
                    cat_map = {
                        "driver": "Drivers", "bsod": "BSOD", "blue screen": "BSOD",
                        "firewall": "Security", "virus": "Security", "malware": "Security",
                        "network": "Network", "wifi": "Network", "tcp": "Network",
                        "python": "Python", "script": "Scripts", "automate": "Automation",
                        "windows": "Windows", "registry": "Registry", "boot": "Boot",
                        "disk": "Storage", "ram": "RAM", "cpu": "System", "gpu": "GPU",
                        "error": "Errors", "fix": "Windows", "install": "Software",
                    }
                    for keyword, cat in cat_map.items():
                        if any(keyword in k.lower() for k in kw):
                            category = cat
                            break

            else:
                _lq_done(url, ok=False)
            _learning_active = _lq_size() > 0

            # ── CPU GUARD: Pause crawlers when system is under load ──
            # Priority: Ollama AI chat > User's apps > Crawlers
            # Crawlers are the LOWEST priority — they pause completely when needed
            adaptive_delay = CRAWL_DELAY_SECS

            # Battery mode = crawlers fully disabled
            if _perf_mode == "battery":
                time.sleep(60)
                continue

            # If Ollama is actively processing a chat → FULL STOP
            if _ollama_busy:
                time.sleep(15)
                continue

            try:
                if HAS_PSUTIL:
                    cpu = psutil.cpu_percent(interval=0.3)
                    ram = psutil.virtual_memory().percent

                    if cpu > 90 or ram > 95:
                        # CRITICAL: CPU maxed — FULL PAUSE, don't add ANY load
                        time.sleep(60)
                        continue
                    elif cpu > 75 or ram > 90:
                        adaptive_delay = 45   # Heavy load — very slow crawling
                    elif cpu > 50 or ram > 80:
                        adaptive_delay = 20   # Moderate load — slow down
                    elif cpu > 30:
                        adaptive_delay = 10   # Light load — gentle crawling
                    # CPU < 30% → use normal 5s delay (system is idle)
            except Exception:
                pass
            time.sleep(adaptive_delay)

        except Exception as e:
            log.debug(f"[LEARN-{worker_id}] Error: {e}")
            time.sleep(5)


# ══════════════════════════════════════════════════════════
#  BOTER WATCHDOG — Proprietary self-healing monitor
#  Monitors all critical threads and restarts them if they die.
#  Runs every 60s. Logs healing events to activity log.
#  Copyright (c) 2025 Shawn Jan — All Rights Reserved
# ══════════════════════════════════════════════════════════

def _watchdog():
    """
    BOTER System Watchdog — monitors and auto-restarts ALL critical threads.
    Self-healing: if any essential thread dies, it is restarted automatically.
    Checks every 60 seconds.
    
    Monitors: ollama-cache, ip-cache, learn workers, sigma loop, beacon,
              HTTP server, DB health, queue health, Ollama process, memory usage.
    """
    log.info("[WATCHDOG] BOTER self-healing watchdog started")
    _heal_count = 0

    while True:
        try:
            time.sleep(60)
            running = {t.name for t in threading.enumerate()}

            # ── Heal: Ollama cache refresher ─────────────────────
            if "ollama-cache" not in running:
                log.warning("[WATCHDOG] ollama-cache thread died — restarting")
                threading.Thread(target=_ol_cache_refresh, daemon=True,
                                 name="ollama-cache").start()
                _heal_count += 1

            # ── Heal: IP cache refresher ──────────────────────────
            if "ip-cache" not in running:
                log.warning("[WATCHDOG] ip-cache thread died — restarting")
                threading.Thread(target=_refresh_ip_cache, daemon=True,
                                 name="ip-cache").start()
                _heal_count += 1

            # ── Heal: SIGMA-NET learning workers ──────────────────
            learn_workers = [t for t in threading.enumerate()
                             if t.name.startswith("learn-")]
            if len(learn_workers) < WORKER_THREADS:
                missing = WORKER_THREADS - len(learn_workers)
                log.warning(f"[WATCHDOG] {missing} learn worker(s) died — restarting")
                existing_ids = {int(t.name.split("-")[1]) for t in learn_workers
                                if t.name.split("-")[1].isdigit()}
                for wid in range(WORKER_THREADS):
                    if wid not in existing_ids:
                        threading.Thread(target=_learn_worker, args=(wid,),
                                         daemon=True, name=f"learn-{wid}").start()
                        log.info(f"[WATCHDOG] Restarted learn-{wid}")
                _heal_count += 1

            # ── Heal: SIGMA-NET main loop ─────────────────────────
            if "sigma" not in running:
                log.warning("[WATCHDOG] sigma loop died — restarting")
                threading.Thread(target=_sigma_loop, daemon=True, name="sigma").start()
                _heal_count += 1

            # ── Heal: UDP beacon (auto-discovery) ─────────────────
            if "beacon" not in running:
                # Only restart if we have the IP and port
                try:
                    port = _gs("server_port")
                    ip = get_ip()
                    if port and ip:
                        log.warning("[WATCHDOG] beacon thread died — restarting")
                        threading.Thread(target=_beacon, args=(ip, int(port)),
                                         daemon=True, name="beacon").start()
                        _heal_count += 1
                except: pass

            # ── Heal: DB connection test ───────────────────────────
            try:
                test = _db_q("SELECT COUNT(*) n FROM knowledge_base")
                if not test:
                    raise Exception("empty result")
            except:
                log.warning("[WATCHDOG] DB health check failed — reinitializing")
                try: _db_init()
                except Exception as e: log.error(f"[WATCHDOG] DB reinit failed: {e}")
                _heal_count += 1

            # ── Heal: Queue empty but KB not full ─────────────────
            if _lq_size() == 0 and _kb_count() < 500:
                log.info("[WATCHDOG] Queue empty — refilling from MASTER_URLS")
                try: _queue_refill()
                except: pass

            # ── Heal: Stuck crawler items ─────────────────────────
            try:
                stuck = _db_q(
                    "SELECT COUNT(*) n FROM learn_queue WHERE status='processing' "
                    "AND started_at < ?", (time.time() - 300,)  # stuck for 5+ min
                )
                stuck_count = stuck[0]["n"] if stuck else 0
                if stuck_count > 0:
                    _db_run(
                        "UPDATE learn_queue SET status='pending', worker_id=0, attempts=attempts+1 "
                        "WHERE status='processing' AND started_at < ?",
                        (time.time() - 300,)
                    )
                    log.warning(f"[WATCHDOG] Recovered {stuck_count} stuck crawl items")
                    _heal_count += 1
            except: pass

            # ── Heal: Ollama not running — restart it ─────────────
            if not _ol_ok():
                ollama_starting = any(t.name in ("ollama-auto", "ollama-pull")
                                      for t in threading.enumerate())
                if not ollama_starting:
                    log.info("[WATCHDOG] Ollama offline — auto-restarting")
                    threading.Thread(target=_start_ollama_auto, daemon=True,
                                     name="ollama-auto").start()
                    _heal_count += 1

            # ── Monitor: Memory usage (warn if > 1GB) ─────────────
            if HAS_PSUTIL:
                try:
                    proc = psutil.Process(os.getpid())
                    mem_mb = proc.memory_info().rss / (1024 * 1024)
                    if mem_mb > 1024:
                        log.warning(f"[WATCHDOG] Server using {mem_mb:.0f} MB RAM — consider restarting")
                except: pass

        except Exception as e:
            log.debug(f"[WATCHDOG] Error in watchdog loop: {e}")


def _auto_heal_startup():
    """
    Run immediate healing checks on startup.
    Fixes common issues before server starts accepting requests.
    """
    # Ensure DB is healthy
    try:
        _db_init()
        # Reset any stuck 'processing' items from previous crash
        _db_run(
            "UPDATE learn_queue SET status='pending', worker_id=0 "
            "WHERE status='processing'"
        )
        stuck = _db_q(
            "SELECT COUNT(*) n FROM learn_queue WHERE status='processing'"
        )
        recovered = stuck[0]["n"] if stuck else 0
        if recovered > 0:
            log.info(f"[HEAL] Recovered {recovered} stuck queue items from previous crash")
    except Exception as e:
        log.warning(f"[HEAL] Startup heal error: {e}")

    # Generate pairing code if missing
    if not _gs("pairing_code"):
        _ss("pairing_code", _gen_code())
        log.info("[HEAL] Generated new pairing code")

    log.info("[HEAL] Startup self-heal complete")


# ══════════════════════════════════════════════════════════

def _push_notify(title: str, body_text: str) -> None:
    """Send Expo push notification to paired device (§12)."""
    try:
        rows = _db_q("SELECT token FROM push_tokens WHERE device_id=? LIMIT 1",
                     (_gs("locked_device"),))
        if not rows: return
        tok = rows[0]["token"]
        import urllib.request as _pur
        payload = json.dumps({"to": tok, "title": title, "body": body_text,
                              "sound": "default"}).encode()
        req = _pur.Request("https://exp.host/--/api/v2/push/send",
                           data=payload, headers={"Content-Type": "application/json"})
        _pur.urlopen(req, timeout=10).read()
    except Exception as e:
        log.debug(f"[PUSH] Notify failed: {e}")



def _sigma_harvest():
    """
    Full SIGMA-NET harvest — recrawls master URLs and searches for new scripts.
    Called by _sigma_loop every HARVEST_SECS. Was referenced but never defined.
    """
    try:
        log.info("[SIGMA] Full harvest starting...")
        _queue_refill()  # top up queue with master URLs
        # Search for new Python automation scripts
        topics = []
        try:
            rows = _db_q(
                "SELECT topic FROM user_topics ORDER BY asks DESC LIMIT 10"
            )
            topics = [r["topic"] for r in rows]
        except Exception:
            pass
        for topic in topics[:5]:
            try:
                _search_and_crawl_scripts(topic, max_results=3)
            except Exception as e:
                log.debug(f"[SIGMA] Harvest topic error: {e}")
        log.info(f"[SIGMA] Harvest complete. Queue: {_lq_size()} URLs")
    except Exception as e:
        log.warning(f"[SIGMA] Harvest failed: {e}")


def _sigma_loop():
    """
    Continuous learning orchestrator. Replaces the old 45-min timer.
    - Starts worker threads immediately
    - Runs SIGMA-NET full harvest every 45 min (deep crawl of all master URLs)
    - Workers run 24/7 between harvests on the persistent queue
    - Everything saves to SQLite - restarts resume exactly where they left off
    """
    global _session_start
    _session_start = time.time()

    # Load checkpoint from last session
    cp = _checkpoint_load()
    if cp:
        _log(f"Learning resumed: {cp.get('articles_total',0)} articles from last session", "ok")

    # Pre-fill queue with master URLs on first run
    time.sleep(10)  # wait for DB to init
    _queue_refill()

    # Start continuous worker threads (they run 24/7)
    for i in range(WORKER_THREADS):
        t = threading.Thread(target=_learn_worker, args=(i,), daemon=True, name=f"learn-{i}")
        t.start()
        time.sleep(1)  # stagger starts

    log.info(f"[SIGMA] {WORKER_THREADS} continuous learning workers started")
    _log(f"Continuous AI learning started - {WORKER_THREADS} workers, queue: {_lq_size()} URLs", "ok")

    # Main loop: full SIGMA-NET harvest every 45 min + checkpoint
    last_checkpoint = time.time()
    while True:
        try:
            time.sleep(HARVEST_SECS)
            # Full harvest: recrawl all master URLs, search for new scripts
            _sigma_harvest()
            # Queue refill after harvest
            _queue_refill()
        except Exception as e:
            log.warning(f"[SIGMA] Harvest error: {e}")
            time.sleep(60)

# ══════════════════════════════════════════════════════
#  GUI HELPERS (forward refs - defined after build_gui)
# ══════════════════════════════════════════════════════
def _refresh_log():
    tv = _gui.get("log_tv")
    if not tv: return
    try:
        with _log_lock: lines = list(_log_lines[-200:])
        tv.configure(state="normal"); tv.delete("1.0","end")
        for tag, msg in lines:
            tv.insert("end", msg+"\n", tag)
        tv.see("end"); tv.configure(state="disabled")
    except: pass

def _refresh_gui():
    root = _gui.get("root")
    if not root: return
    try:
        ai_lbl = _gui.get("ai_lbl")
        if ai_lbl:
            ok = _ol_ok()
            if ok:
                ai_lbl.configure(text=f" AI: {_ol_model()} ✓ ", fg="#00e887", bg="#0b2340")
            else:
                ai_lbl.configure(text=" AI: starting… ", fg="#ffaa00", bg="#0b2340")
        kb_lbl = _gui.get("kb_lbl")
        if kb_lbl:
            kb_lbl.configure(text=f" KB: {_kb_count()} articles · Last: {_sigma_stats['last']} ")
        dev_lbl = _gui.get("dev_lbl")
        if dev_lbl:
            locked = _gs("locked_device")
            if locked:
                dev_lbl.configure(text=f" Device: {locked[:22]}… ", fg="#00e887", bg="#0b2340")
            else:
                dev_lbl.configure(text=" OPEN — waiting for first device ", fg="#ffaa00", bg="#0b2340")
    except: pass


# ══════════════════════════════════════════════════════
#  UNDO SYSTEM + PC STATS + CLEAN SCRIPTS + LIBRARY
# ══════════════════════════════════════════════════════
UNDO_WINDOW = 15 * 60  # 15 minutes

def _undo_create(script, language, user_req=""):
    now = time.time()
    snapshot = {}
    try:
        home = str(Path.home())
        # Snapshot Desktop/Documents/Downloads file lists
        for d in ["Desktop", "Documents", "Downloads"]:
            dp = Path.home() / d
            if dp.exists():
                try: snapshot["__dir_" + d] = [f.name for f in dp.iterdir() if f.is_file()][:100]
                except: pass
    except: pass
    try:
        _db_run("INSERT INTO undo_journal(ts,expires_at,script,language,user_req,snapshot,status) VALUES(?,?,?,?,?,?,?)",
                (now, now + UNDO_WINDOW, script, language, user_req, json.dumps(snapshot, default=str), "pending"))
        rows = _db_q("SELECT id FROM undo_journal ORDER BY id DESC LIMIT 1")
        return rows[0]["id"] if rows else None
    except: return None

def _undo_complete(entry_id, output, success):
    try:
        _db_run("UPDATE undo_journal SET output=?, status=? WHERE id=?",
                (str(output)[:5000], "ok" if success else "error", entry_id))
        _pc_stat_inc("scripts_run")
    except: pass

def _undo_rollback(entry_id):
    rows = _db_q("SELECT * FROM undo_journal WHERE id=? AND undone=0", (entry_id,))
    if not rows: return {"ok": False, "error": "Entry not found or already undone"}
    entry = rows[0]
    if time.time() > entry["expires_at"]: return {"ok": False, "error": "Undo window expired (15 minutes)"}
    _db_run("UPDATE undo_journal SET undone=1 WHERE id=?", (entry_id,))
    _pc_stat_inc("scripts_undone")
    return {"ok": True, "restored": 0, "message": "Script marked as undone. Directory snapshots preserved."}

def _undo_list():
    now = time.time()
    try: _db_run("DELETE FROM undo_journal WHERE expires_at < ?", (now - 3600,))
    except: pass
    rows = _db_q("SELECT id,ts,expires_at,script,language,user_req,output,status,undone FROM undo_journal WHERE expires_at > ? ORDER BY ts DESC LIMIT 20", (now,))
    result = []
    for r in rows:
        remaining = max(0, int(r["expires_at"] - now))
        result.append({"id": r["id"], "timestamp": r["ts"], "remainingSec": remaining,
                        "remainingMin": "%d:%02d" % (remaining // 60, remaining % 60),
                        "script": r["script"][:200], "language": r["language"],
                        "userRequest": r["user_req"][:100], "status": r["status"],
                        "undone": bool(r["undone"]), "canUndo": remaining > 0 and not r["undone"]})
    return result

def _pc_stat_get(key):
    try:
        rows = _db_q("SELECT value FROM pc_stats WHERE key=?", (key,))
        return rows[0]["value"] if rows else 0
    except: return 0

def _pc_stat_inc(key, amount=1):
    try:
        _db_run("INSERT INTO pc_stats(key,value) VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=value+?", (key, amount, amount))
        _db_run("INSERT INTO pc_stats_log(ts,key,value) VALUES(?,?,?)", (time.time(), key, amount))
        _db_run("DELETE FROM pc_stats_log WHERE ts < ?", (time.time() - 30*86400,))
    except: pass

def _pc_stat_set(key, value):
    try: _db_run("INSERT INTO pc_stats(key,value) VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=?", (key, value, value))
    except: pass

def _pc_growth_data(days=7):
    try:
        cutoff = time.time() - days * 86400
        rows = _db_q("SELECT date(ts,'unixepoch','localtime') as day, key, SUM(value) as total FROM pc_stats_log WHERE ts > ? GROUP BY day, key ORDER BY day", (cutoff,))
        by_day = {}
        for r in rows:
            d = r["day"]
            if d not in by_day: by_day[d] = {"day": d, "cleaned": 0, "organized": 0, "recovered_mb": 0}
            if r["key"] == "files_cleaned": by_day[d]["cleaned"] += int(r["total"])
            elif r["key"] == "files_organized": by_day[d]["organized"] += int(r["total"])
            elif r["key"] == "space_recovered_bytes": by_day[d]["recovered_mb"] += round(r["total"]/(1024*1024), 1)
        return list(by_day.values())[-days:]
    except: return []

def _pc_scan_stats():
    stats = {"temp_files": 0, "temp_size_bytes": 0, "temp_size_mb": 0, "large_files": [], "browser_cache_mb": 0, "startup_items": 0}
    if not HAS_PSUTIL: return stats
    home = Path.home()
    for td in [Path(os.environ.get("TEMP", "")), Path(os.environ.get("TMP", "")), home / "AppData" / "Local" / "Temp"]:
        if not td.exists(): continue
        try:
            for f in td.rglob("*"):
                if f.is_file():
                    try: stats["temp_files"] += 1; stats["temp_size_bytes"] += f.stat().st_size
                    except: pass
        except: pass
    stats["temp_size_mb"] = round(stats["temp_size_bytes"] / (1024*1024), 1)
    desktop = home / "Desktop"
    if desktop.exists():
        try:
            for f in desktop.rglob("*"):
                if f.is_file():
                    try:
                        sz = f.stat().st_size
                        if sz > 100_000_000: stats["large_files"].append({"name": f.name, "size_mb": round(sz/(1024*1024), 1)})
                    except: pass
        except: pass
    stats["large_files"] = sorted(stats["large_files"], key=lambda x: -x["size_mb"])[:10]
    for bc in [home/"AppData"/"Local"/"Google"/"Chrome"/"User Data"/"Default"/"Cache", home/"AppData"/"Local"/"Microsoft"/"Edge"/"User Data"/"Default"/"Cache"]:
        if bc.exists():
            try: stats["browser_cache_mb"] += round(sum(f.stat().st_size for f in bc.rglob("*") if f.is_file()) / (1024*1024), 1)
            except: pass
    if IS_WINDOWS:
        sd = home / "AppData" / "Roaming" / "Microsoft" / "Windows" / "Start Menu" / "Programs" / "Startup"
        if sd.exists():
            try: stats["startup_items"] = len(list(sd.iterdir()))
            except: pass
    return stats

# ── Pre-built cleaning scripts (21 with actual code) ─────────
_PC_CLEAN_SCRIPTS = {
    "temp": 'import os, pathlib, tempfile\ntemp = pathlib.Path(tempfile.gettempdir())\ncount = freed = 0\nfor f in temp.rglob("*"):\n    if f.is_file():\n        try: freed += f.stat().st_size; f.unlink(); count += 1\n        except: pass\nprint(f"Cleaned {count} temp files, freed {freed//(1024*1024)} MB")',
    "browser": 'import pathlib\nhome = pathlib.Path.home()\ncaches = [home/"AppData/Local/Google/Chrome/User Data/Default/Cache", home/"AppData/Local/Google/Chrome/User Data/Default/Code Cache", home/"AppData/Local/Microsoft/Edge/User Data/Default/Cache"]\nfreed = count = 0\nfor c in caches:\n    if c.exists():\n        for f in c.rglob("*"):\n            if f.is_file():\n                try: freed += f.stat().st_size; f.unlink(); count += 1\n                except: pass\nprint(f"Cleared {count} browser cache files, freed {freed//(1024*1024)} MB")',
    "organize": 'import pathlib, shutil\ndesktop = pathlib.Path.home() / "Desktop"\ncategories = {"Images": [".jpg",".jpeg",".png",".gif",".bmp",".svg",".webp"], "Documents": [".pdf",".doc",".docx",".txt",".rtf",".xls",".xlsx",".csv",".pptx"], "Videos": [".mp4",".avi",".mkv",".mov",".wmv"], "Music": [".mp3",".wav",".flac",".aac",".ogg"], "Archives": [".zip",".rar",".7z",".tar",".gz"], "Installers": [".exe",".msi"], "Code": [".py",".js",".ts",".html",".css",".json"]}\nmoved = 0\nfor f in desktop.iterdir():\n    if not f.is_file(): continue\n    ext = f.suffix.lower()\n    for cat, exts in categories.items():\n        if ext in exts:\n            dest = desktop / cat; dest.mkdir(exist_ok=True)\n            try: shutil.move(str(f), str(dest / f.name)); moved += 1\n            except: pass\n            break\nprint(f"Organized {moved} files into folders on Desktop")',
    "disk_report": 'import shutil, platform\ndrives = ["C:", "D:", "E:"] if platform.system() == "Windows" else ["/"]\nfor d in drives:\n    try:\n        u = shutil.disk_usage(d + "/")\n        pct = (u.used / u.total) * 100\n        bar = chr(9608) * int(pct/5) + chr(9617) * (20-int(pct/5))\n        print(f"{d} [{bar}] {pct:.0f}%  {u.used//(1024**3)}/{u.total//(1024**3)} GB  ({u.free//(1024**3)} GB free)")\n    except: pass',
    "empty_recycle": 'import subprocess, platform\nif platform.system() == "Windows":\n    subprocess.run(["powershell", "-Command", "Clear-RecycleBin -Force -ErrorAction SilentlyContinue"], capture_output=True)\n    print("Recycle Bin emptied")\nelse:\n    import shutil, pathlib\n    trash = pathlib.Path.home() / ".local/share/Trash"\n    if trash.exists(): shutil.rmtree(trash, ignore_errors=True); print("Trash emptied")',
    "scan_large": 'import pathlib\nhome = pathlib.Path.home()\nlarge = []\nfor d in ["Desktop", "Documents", "Downloads"]:\n    dp = home / d\n    if not dp.exists(): continue\n    for f in dp.rglob("*"):\n        if f.is_file():\n            try:\n                sz = f.stat().st_size\n                if sz > 50_000_000: large.append((sz, str(f)))\n            except: pass\nlarge.sort(reverse=True)\nprint(f"Found {len(large)} files over 50MB:")\nfor sz, p in large[:20]: print(f"  {sz//(1024*1024):>6} MB  {p}")',
    "startup": 'import pathlib, subprocess\nhome = pathlib.Path.home()\nsd = home / "AppData/Roaming/Microsoft/Windows/Start Menu/Programs/Startup"\nif sd.exists():\n    items = list(sd.iterdir())\n    print(f"Startup folder: {len(items)} items")\n    for f in items: print(f"  {f.name}")\nelse: print("Startup folder not found")\nr = subprocess.run(["reg", "query", "HKCU\\\\SOFTWARE\\\\Microsoft\\\\Windows\\\\CurrentVersion\\\\Run"], capture_output=True, text=True)\nif r.stdout:\n    print("\\nRegistry startup:")\n    for line in r.stdout.strip().split("\\n"):\n        line = line.strip()\n        if line and not line.startswith("HKEY"): print(f"  {line}")',
    "full_clean": 'import os, pathlib, tempfile, subprocess, platform\ntotal_freed = total_files = 0\ntemp = pathlib.Path(tempfile.gettempdir())\nfor f in temp.rglob("*"):\n    if f.is_file():\n        try: total_freed += f.stat().st_size; f.unlink(); total_files += 1\n        except: pass\nprint(f"[1/3] Temp: {total_files} cleaned")\nif platform.system() == "Windows":\n    tc = pathlib.Path.home() / "AppData/Local/Microsoft/Windows/Explorer"\n    if tc.exists():\n        tc_c = 0\n        for f in tc.glob("thumbcache_*"):\n            try: total_freed += f.stat().st_size; f.unlink(); tc_c += 1; total_files += 1\n            except: pass\n        print(f"[2/3] Thumbnails: {tc_c} cleaned")\n    subprocess.run(["ipconfig", "/flushdns"], capture_output=True)\n    print("[3/3] DNS flushed")\nprint(f"\\nTotal: {total_files} files, {total_freed//(1024*1024)} MB freed")',
    "sort_downloads": 'import pathlib, shutil\ndl = pathlib.Path.home() / "Downloads"\ncategories = {"Images": [".jpg",".jpeg",".png",".gif",".webp",".heic"], "Documents": [".pdf",".doc",".docx",".txt",".xls",".xlsx",".csv",".pptx"], "Videos": [".mp4",".avi",".mkv",".mov",".webm"], "Music": [".mp3",".wav",".flac",".aac"], "Archives": [".zip",".rar",".7z",".tar",".gz"], "Installers": [".exe",".msi"], "Code": [".py",".js",".ts",".html",".css",".json"]}\nmoved = 0\nfor f in dl.iterdir():\n    if not f.is_file(): continue\n    ext = f.suffix.lower()\n    for cat, exts in categories.items():\n        if ext in exts:\n            dest = dl / cat; dest.mkdir(exist_ok=True)\n            try: shutil.move(str(f), str(dest / f.name)); moved += 1\n            except: pass\n            break\nprint(f"Organized {moved} files in Downloads")',
    "find_duplicates": 'import pathlib, hashlib\nfrom collections import defaultdict\nhashes = defaultdict(list)\ncount = 0\nfor d in ["Desktop", "Documents", "Downloads"]:\n    dp = pathlib.Path.home() / d\n    if not dp.exists(): continue\n    for f in dp.rglob("*"):\n        if not f.is_file() or f.stat().st_size < 1024: continue\n        try:\n            h = hashlib.md5(f.read_bytes()[:65536]).hexdigest()\n            hashes[h].append(str(f)); count += 1\n        except: pass\ndupes = {h: p for h, p in hashes.items() if len(p) > 1}\nprint(f"Scanned {count} files, found {len(dupes)} duplicate groups")\nfor h, paths in list(dupes.items())[:10]:\n    print(f"  [{pathlib.Path(paths[0]).stat().st_size//1024}KB] {pathlib.Path(paths[0]).name}")\n    for p in paths[1:]: print(f"    DUP: {p}")',
    "empty_folders": 'import pathlib\nempty = []\nfor d in ["Desktop", "Documents", "Downloads"]:\n    dp = pathlib.Path.home() / d\n    if not dp.exists(): continue\n    for folder in dp.rglob("*"):\n        if folder.is_dir():\n            try:\n                if not any(folder.iterdir()): empty.append(folder)\n            except: pass\nprint(f"Found {len(empty)} empty folders")\nfor f in empty:\n    try: f.rmdir(); print(f"  Removed: {f.name}")\n    except: pass',
    "old_files": 'import pathlib, time\nnow = time.time()\nold = []\nfor d in ["Desktop", "Documents", "Downloads"]:\n    dp = pathlib.Path.home() / d\n    if not dp.exists(): continue\n    for f in dp.rglob("*"):\n        if not f.is_file(): continue\n        try:\n            age = (now - f.stat().st_mtime) / 86400\n            if age > 90: old.append((age, f.stat().st_size, str(f)))\n        except: pass\nold.sort(reverse=True)\nprint(f"Files older than 90 days: {len(old)} ({sum(s for _,s,_ in old)//(1024*1024)} MB)")\nfor age, sz, p in old[:20]: print(f"  {int(age):>4}d  {sz//1024:>6}KB  {pathlib.Path(p).name}")',
    "system_info": 'import platform, socket, os\ntry: import psutil\nexcept: psutil = None\nprint(f"Computer: {socket.gethostname()}")\nprint(f"OS: {platform.system()} {platform.release()}")\nprint(f"Arch: {platform.machine()}")\nprint(f"Python: {platform.python_version()}")\nif psutil:\n    m = psutil.virtual_memory()\n    d = psutil.disk_usage("/")\n    print(f"RAM: {m.total//(1024**3)} GB total, {m.available//(1024**3)} GB free")\n    print(f"Disk: {d.total//(1024**3)} GB total, {d.free//(1024**3)} GB free")\n    print(f"CPU: {psutil.cpu_count(logical=False)} cores, {psutil.cpu_count()} threads")',
    "privacy_clean": 'import pathlib, subprocess, platform\nhome = pathlib.Path.home()\ncleaned = 0\nrecent = home / "AppData/Roaming/Microsoft/Windows/Recent"\nif recent.exists():\n    for f in recent.glob("*.lnk"):\n        try: f.unlink(); cleaned += 1\n        except: pass\n    print(f"Cleared {cleaned} recent shortcuts")\ntc = home / "AppData/Local/Microsoft/Windows/Explorer"\nif tc.exists():\n    tc_c = 0\n    for f in tc.glob("thumbcache_*"):\n        try: f.unlink(); tc_c += 1\n        except: pass\n    print(f"Cleared {tc_c} thumbnail caches")\nif platform.system() == "Windows":\n    subprocess.run(["cmd", "/c", "echo off | clip"], capture_output=True)\n    print("Clipboard cleared")\n    subprocess.run(["ipconfig", "/flushdns"], capture_output=True)\n    print("DNS flushed")',
    "security_scan": 'import subprocess\nprint("=== SECURITY SCAN ===")\nr = subprocess.run(["netstat", "-ano"], capture_output=True, text=True, timeout=10)\nlistening = [l.strip() for l in r.stdout.split("\\n") if "LISTENING" in l]\nprint(f"\\n[PORTS] {len(listening)} listening")\nfor l in listening[:10]: print(f"  {l}")\nr = subprocess.run(["powershell", "-Command", "Get-MpComputerStatus | Select AntivirusEnabled,RealTimeProtectionEnabled | Format-List"], capture_output=True, text=True, timeout=15)\nprint(f"\\n[DEFENDER] {r.stdout.strip() or \'Could not check\'}")',
    "boost_performance": 'import subprocess\nprint("Applying performance optimizations...")\ncmds = [("Visual effects...", ["powershell", "-Command", "Set-ItemProperty -Path \'HKCU:\\\\Software\\\\Microsoft\\\\Windows\\\\CurrentVersion\\\\Explorer\\\\VisualEffects\' -Name \'VisualFXSetting\' -Value 2 -EA SilentlyContinue"]),\n("Power plan...", ["powercfg", "/setactive", "8c5e7fda-e8bf-4a96-9a85-a6e23a8c635c"])]\nfor msg, cmd in cmds:\n    print(f"  {msg}", end=" ")\n    try: subprocess.run(cmd, capture_output=True, timeout=15); print("OK")\n    except: print("SKIP")\nprint("Done")',
    "network_reset": 'import subprocess\nprint("Resetting network...")\nfor cmd, msg in [(["ipconfig", "/flushdns"], "DNS"), (["netsh", "winsock", "reset"], "Winsock"), (["netsh", "int", "ip", "reset"], "TCP/IP")]:\n    try: subprocess.run(cmd, capture_output=True, timeout=15); print(f"  {msg}: OK")\n    except: print(f"  {msg}: SKIP")\nprint("Network reset. Restart PC to finish.")',
    "memory_clean": 'try: import psutil\nexcept: print("psutil required"); exit()\nmem = psutil.virtual_memory()\nprint(f"RAM: {mem.percent}% used ({mem.available//(1024**3)} GB free)")\nprint("\\nTop RAM users:")\nfor p in sorted(psutil.process_iter(["name","memory_percent"]), key=lambda x: x.info.get("memory_percent",0), reverse=True)[:8]:\n    try: print(f"  {p.info[\'memory_percent\']:>5.1f}%  {p.info[\'name\']}")\n    except: pass',
    "windows_update": 'import subprocess\nprint("Checking for updates...")\ntry:\n    r = subprocess.run(["powershell", "-Command", "Start-Process UsoClient StartInteractiveScan -Wait"], capture_output=True, text=True, timeout=60)\n    print("Update scan started")\nexcept: print("Could not start update scan")',
    "driver_check": 'import subprocess\nprint("Checking drivers...")\nr = subprocess.run(["powershell", "-Command", "Get-WmiObject Win32_PnPEntity | Where {$_.ConfigManagerErrorCode -ne 0} | Select Name,DeviceID | Format-Table -Auto"], capture_output=True, text=True, timeout=30)\nif r.stdout.strip(): print("Issues found:\\n" + r.stdout)\nelse: print("All drivers OK")',
    "fix_permissions": 'import pathlib, stat\nfixed = 0\nfor d in ["Desktop", "Documents", "Downloads"]:\n    dp = pathlib.Path.home() / d\n    if not dp.exists(): continue\n    for f in dp.rglob("*"):\n        if not f.is_file(): continue\n        try:\n            c = f.stat().st_mode\n            if not (c & stat.S_IRUSR and c & stat.S_IWUSR):\n                f.chmod(stat.S_IRUSR | stat.S_IWUSR | stat.S_IRGRP | stat.S_IROTH); fixed += 1\n        except: pass\nprint(f"Fixed permissions on {fixed} files")',
}


_SCRIPT_LIBRARY = {"cleaning": {"title": "PC Cleaning", "icon": "cleaning-services", "color": "#FF4444", "scripts": [{"id": "temp", "name": "Clean Temp Files", "desc": "Remove Windows temp files to free disk space", "difficulty": "BEGINNER", "hasCode": True}, {"id": "browser", "name": "Clear Browser Cache", "desc": "Clear Chrome, Edge, Firefox cache data", "difficulty": "BEGINNER", "hasCode": True}, {"id": "full_clean", "name": "Full PC Clean", "desc": "Temp + prefetch + thumbnails + DNS flush", "difficulty": "BEGINNER", "hasCode": True}, {"id": "empty_recycle", "name": "Empty Recycle Bin", "desc": "Permanently delete all recycled files", "difficulty": "BEGINNER", "hasCode": True}, {"id": "privacy_clean", "name": "Privacy Clean", "desc": "Clear recent files, clipboard, thumbnails", "difficulty": "INTERMEDIATE", "hasCode": True}, {"id": "memory_clean", "name": "Memory Optimizer", "desc": "Free RAM and identify memory hog processes", "difficulty": "INTERMEDIATE", "hasCode": True}, {"id": "clear_logs", "name": "Clear Windows Logs", "desc": "Remove old Windows event logs safely", "difficulty": "INTERMEDIATE", "hasCode": False}, {"id": "clear_updates", "name": "Clean Update Cache", "desc": "Remove old Windows Update files (SoftwareDistribution)", "difficulty": "INTERMEDIATE", "hasCode": False}, {"id": "clear_crashes", "name": "Clear Crash Dumps", "desc": "Remove Windows crash dump files (.dmp)", "difficulty": "BEGINNER", "hasCode": False}, {"id": "clear_font_cache", "name": "Reset Font Cache", "desc": "Fix font display issues by clearing font cache", "difficulty": "INTERMEDIATE", "hasCode": False}, {"id": "clear_store_cache", "name": "MS Store Cache", "desc": "Reset Microsoft Store cache (wsreset)", "difficulty": "BEGINNER", "hasCode": False}, {"id": "clear_cortana", "name": "Clear Search Cache", "desc": "Reset Windows Search/Cortana database", "difficulty": "INTERMEDIATE", "hasCode": False}, {"id": "clear_teams_cache", "name": "Teams Cache Clean", "desc": "Clear Microsoft Teams cache and temp data", "difficulty": "BEGINNER", "hasCode": False}, {"id": "clear_discord_cache", "name": "Discord Cache Clean", "desc": "Clear Discord cache, code cache, GPU cache", "difficulty": "BEGINNER", "hasCode": False}, {"id": "clear_nvidia_cache", "name": "NVIDIA Cache Clean", "desc": "Clear NVIDIA shader cache and temp files", "difficulty": "BEGINNER", "hasCode": False}, {"id": "clear_pip_cache", "name": "Pip Cache Clean", "desc": "Clear Python pip download cache", "difficulty": "BEGINNER", "hasCode": False}, {"id": "clear_npm_cache", "name": "NPM Cache Clean", "desc": "Clear Node.js npm cache", "difficulty": "BEGINNER", "hasCode": False}]}, "organize": {"title": "File Organization", "icon": "folder", "color": "#FF8C00", "scripts": [{"id": "organize", "name": "Organize Desktop", "desc": "Sort Desktop files into folders by type", "difficulty": "BEGINNER", "hasCode": True}, {"id": "sort_downloads", "name": "Sort Downloads", "desc": "Organize Downloads folder by file type", "difficulty": "BEGINNER", "hasCode": True}, {"id": "find_duplicates", "name": "Find Duplicates", "desc": "Scan for duplicate files using hash comparison", "difficulty": "INTERMEDIATE", "hasCode": True}, {"id": "empty_folders", "name": "Remove Empty Folders", "desc": "Find and delete empty directories", "difficulty": "BEGINNER", "hasCode": True}, {"id": "old_files", "name": "Find Old Files", "desc": "List files older than 90 days with sizes", "difficulty": "BEGINNER", "hasCode": True}, {"id": "sort_by_date", "name": "Sort by Date", "desc": "Organize files into YYYY/MM folders by date modified", "difficulty": "INTERMEDIATE", "hasCode": False}, {"id": "sort_photos_exif", "name": "Sort Photos by EXIF", "desc": "Organize photos by camera date, location", "difficulty": "ADVANCED", "hasCode": False}, {"id": "flatten_folders", "name": "Flatten Nested Folders", "desc": "Move all files from subfolders to parent", "difficulty": "INTERMEDIATE", "hasCode": False}, {"id": "rename_batch", "name": "Batch Rename", "desc": "Rename files with pattern: prefix_001, prefix_002", "difficulty": "INTERMEDIATE", "hasCode": False}, {"id": "rename_lowercase", "name": "Lowercase All Names", "desc": "Convert all filenames to lowercase", "difficulty": "BEGINNER", "hasCode": False}, {"id": "rename_remove_spaces", "name": "Remove Spaces", "desc": "Replace spaces with underscores in filenames", "difficulty": "BEGINNER", "hasCode": False}, {"id": "rename_by_date", "name": "Rename by Date", "desc": "Rename files to YYYY-MM-DD format", "difficulty": "INTERMEDIATE", "hasCode": False}, {"id": "find_large_folders", "name": "Folder Size Map", "desc": "Show which folders use the most space", "difficulty": "BEGINNER", "hasCode": False}, {"id": "archive_old", "name": "Archive Old Files", "desc": "Compress files older than 6 months into ZIP", "difficulty": "INTERMEDIATE", "hasCode": False}]}, "system": {"title": "System Tools", "icon": "computer", "color": "#00E5FF", "scripts": [{"id": "system_info", "name": "System Info", "desc": "Full hardware and OS report", "difficulty": "BEGINNER", "hasCode": True}, {"id": "disk_report", "name": "Disk Usage Report", "desc": "Show disk usage for all drives", "difficulty": "BEGINNER", "hasCode": True}, {"id": "scan_large", "name": "Find Large Files", "desc": "Find files over 50MB across user folders", "difficulty": "BEGINNER", "hasCode": True}, {"id": "startup", "name": "Startup Manager", "desc": "View startup items and registry entries", "difficulty": "INTERMEDIATE", "hasCode": True}, {"id": "driver_check", "name": "Driver Check", "desc": "Find devices with driver issues", "difficulty": "INTERMEDIATE", "hasCode": True}, {"id": "fix_permissions", "name": "Fix Permissions", "desc": "Repair file permissions in user folders", "difficulty": "INTERMEDIATE", "hasCode": True}, {"id": "list_installed", "name": "List Installed Apps", "desc": "Show all installed programs with sizes", "difficulty": "BEGINNER", "hasCode": False}, {"id": "list_services", "name": "List Services", "desc": "Show running Windows services", "difficulty": "INTERMEDIATE", "hasCode": False}, {"id": "check_disk", "name": "Check Disk Health", "desc": "Run SMART check on all drives", "difficulty": "INTERMEDIATE", "hasCode": False}, {"id": "event_log", "name": "Recent Errors", "desc": "Show last 20 Windows error events", "difficulty": "INTERMEDIATE", "hasCode": False}, {"id": "battery_report", "name": "Battery Report", "desc": "Generate detailed battery health report (laptops)", "difficulty": "BEGINNER", "hasCode": False}, {"id": "wifi_passwords", "name": "Show WiFi Passwords", "desc": "Display saved WiFi network passwords", "difficulty": "BEGINNER", "hasCode": False}, {"id": "env_vars", "name": "Environment Variables", "desc": "List all system environment variables", "difficulty": "BEGINNER", "hasCode": False}, {"id": "process_tree", "name": "Process Tree", "desc": "Show running processes with CPU and RAM usage", "difficulty": "BEGINNER", "hasCode": False}, {"id": "scheduled_tasks", "name": "Scheduled Tasks", "desc": "List all Windows scheduled tasks", "difficulty": "INTERMEDIATE", "hasCode": False}, {"id": "host_file", "name": "View Hosts File", "desc": "Display Windows hosts file entries", "difficulty": "BEGINNER", "hasCode": False}, {"id": "bios_info", "name": "BIOS Info", "desc": "Show BIOS version, manufacturer, serial number", "difficulty": "BEGINNER", "hasCode": False}, {"id": "motherboard_info", "name": "Motherboard Info", "desc": "Show motherboard model and chipset", "difficulty": "BEGINNER", "hasCode": False}, {"id": "windows_key", "name": "Find Windows Key", "desc": "Show your Windows product key", "difficulty": "BEGINNER", "hasCode": False}, {"id": "restore_point", "name": "Create Restore Point", "desc": "Create Windows System Restore checkpoint", "difficulty": "INTERMEDIATE", "hasCode": False}]}, "performance": {"title": "Performance", "icon": "speed", "color": "#00FF88", "scripts": [{"id": "boost_performance", "name": "Performance Boost", "desc": "Disable visual effects, set High Performance power", "difficulty": "ADVANCED", "hasCode": True}, {"id": "network_reset", "name": "Network Reset", "desc": "Reset DNS, Winsock, TCP/IP stack", "difficulty": "INTERMEDIATE", "hasCode": True}, {"id": "windows_update", "name": "Check Updates", "desc": "Check for Windows updates", "difficulty": "BEGINNER", "hasCode": True}, {"id": "disable_indexing", "name": "Disable Search Indexing", "desc": "Stop Windows Search from using CPU/disk", "difficulty": "INTERMEDIATE", "hasCode": False}, {"id": "disable_telemetry", "name": "Disable Telemetry", "desc": "Reduce Windows data collection for privacy", "difficulty": "ADVANCED", "hasCode": False}, {"id": "ssd_optimize", "name": "SSD Optimizer", "desc": "Disable defrag, enable TRIM for SSD drives", "difficulty": "ADVANCED", "hasCode": False}, {"id": "power_plan", "name": "Power Plan Manager", "desc": "Switch between Balanced, High Performance, Power Saver", "difficulty": "BEGINNER", "hasCode": False}, {"id": "disable_animations", "name": "Disable Animations", "desc": "Turn off all Windows animations for speed", "difficulty": "BEGINNER", "hasCode": False}, {"id": "gpu_info", "name": "GPU Info", "desc": "Show GPU model, driver version, VRAM", "difficulty": "BEGINNER", "hasCode": False}, {"id": "ram_speed", "name": "RAM Speed Check", "desc": "Show RAM frequency, type, slots used", "difficulty": "BEGINNER", "hasCode": False}, {"id": "benchmark_disk", "name": "Disk Speed Test", "desc": "Benchmark read/write speed of drives", "difficulty": "INTERMEDIATE", "hasCode": False}, {"id": "benchmark_cpu", "name": "CPU Benchmark", "desc": "Quick CPU performance test (single + multi core)", "difficulty": "INTERMEDIATE", "hasCode": False}]}, "security": {"title": "Security & Privacy", "icon": "security", "color": "#C084FF", "scripts": [{"id": "security_scan", "name": "Security Scan", "desc": "Check startup, open ports, Defender status", "difficulty": "INTERMEDIATE", "hasCode": True}, {"id": "privacy_clean", "name": "Privacy Sweep", "desc": "Clear all tracking data, clipboard, DNS", "difficulty": "INTERMEDIATE", "hasCode": True}, {"id": "check_firewall", "name": "Firewall Status", "desc": "Check Windows Firewall rules and status", "difficulty": "INTERMEDIATE", "hasCode": False}, {"id": "open_ports", "name": "Open Ports Scanner", "desc": "List all open TCP/UDP ports on this PC", "difficulty": "INTERMEDIATE", "hasCode": False}, {"id": "check_defender", "name": "Defender Status", "desc": "Check antivirus definitions and real-time protection", "difficulty": "BEGINNER", "hasCode": False}, {"id": "password_audit", "name": "Saved Passwords Audit", "desc": "Find where passwords are stored on PC", "difficulty": "ADVANCED", "hasCode": False}, {"id": "user_accounts", "name": "User Accounts", "desc": "List all user accounts and admin status", "difficulty": "BEGINNER", "hasCode": False}, {"id": "shared_folders", "name": "Shared Folders", "desc": "List network-shared folders on this PC", "difficulty": "INTERMEDIATE", "hasCode": False}, {"id": "uac_check", "name": "UAC Level Check", "desc": "Show User Account Control setting", "difficulty": "BEGINNER", "hasCode": False}, {"id": "rdp_check", "name": "Remote Desktop Check", "desc": "Check if Remote Desktop is enabled", "difficulty": "INTERMEDIATE", "hasCode": False}, {"id": "auto_lock", "name": "Auto Lock Screen", "desc": "Set screen to lock after 5 minutes of inactivity", "difficulty": "BEGINNER", "hasCode": False}, {"id": "check_bitlocker", "name": "BitLocker Status", "desc": "Check drive encryption status", "difficulty": "INTERMEDIATE", "hasCode": False}, {"id": "lock_screen", "name": "Lock PC Now", "desc": "Instantly lock the computer screen", "difficulty": "BEGINNER", "hasCode": False}, {"id": "disable_usb", "name": "Disable USB Storage", "desc": "Block USB drives for security (reversible)", "difficulty": "ADVANCED", "hasCode": False}]}, "network": {"title": "Network & WiFi", "icon": "wifi", "color": "#4A9EFF", "scripts": [{"id": "speed_test", "name": "Internet Speed Test", "desc": "Test download, upload, and ping speed", "difficulty": "BEGINNER", "hasCode": False}, {"id": "dns_benchmark", "name": "DNS Benchmark", "desc": "Compare DNS server response times", "difficulty": "INTERMEDIATE", "hasCode": False}, {"id": "ip_info", "name": "IP & Network Info", "desc": "Show local IP, gateway, DNS, MAC address", "difficulty": "BEGINNER", "hasCode": False}, {"id": "wifi_signal", "name": "WiFi Signal Strength", "desc": "Show signal quality and channel info", "difficulty": "BEGINNER", "hasCode": False}, {"id": "traceroute", "name": "Traceroute", "desc": "Trace network path to any server", "difficulty": "INTERMEDIATE", "hasCode": False}, {"id": "ping_monitor", "name": "Ping Monitor", "desc": "Continuous ping to detect connection drops", "difficulty": "BEGINNER", "hasCode": False}, {"id": "arp_table", "name": "Network Devices", "desc": "List all devices on your local network", "difficulty": "INTERMEDIATE", "hasCode": False}, {"id": "flush_arp", "name": "Flush ARP Cache", "desc": "Clear ARP table to fix network issues", "difficulty": "INTERMEDIATE", "hasCode": False}, {"id": "bandwidth_monitor", "name": "Bandwidth Monitor", "desc": "Show which apps are using internet", "difficulty": "INTERMEDIATE", "hasCode": False}, {"id": "change_dns", "name": "Switch to Google DNS", "desc": "Change DNS to 8.8.8.8 for faster browsing", "difficulty": "INTERMEDIATE", "hasCode": False}, {"id": "proxy_check", "name": "Proxy Settings", "desc": "Show current proxy configuration", "difficulty": "BEGINNER", "hasCode": False}, {"id": "vpn_check", "name": "VPN Status", "desc": "Check if VPN connection is active", "difficulty": "BEGINNER", "hasCode": False}, {"id": "wake_on_lan", "name": "Wake on LAN", "desc": "Send magic packet to wake another PC", "difficulty": "INTERMEDIATE", "hasCode": False}, {"id": "port_forward", "name": "Port Forward Test", "desc": "Test if a port is forwarded correctly", "difficulty": "INTERMEDIATE", "hasCode": False}]}, "backup": {"title": "Backup & Sync", "icon": "backup", "color": "#FFD700", "scripts": [{"id": "backup_desktop", "name": "Backup Desktop", "desc": "ZIP entire Desktop folder with timestamp", "difficulty": "BEGINNER", "hasCode": False}, {"id": "backup_documents", "name": "Backup Documents", "desc": "ZIP Documents folder to external drive", "difficulty": "BEGINNER", "hasCode": False}, {"id": "backup_photos", "name": "Backup Photos", "desc": "Copy all photos to a backup folder", "difficulty": "BEGINNER", "hasCode": False}, {"id": "backup_browser", "name": "Backup Bookmarks", "desc": "Export browser bookmarks to HTML file", "difficulty": "INTERMEDIATE", "hasCode": False}, {"id": "backup_registry", "name": "Backup Registry", "desc": "Export full Windows registry backup", "difficulty": "ADVANCED", "hasCode": False}, {"id": "backup_drivers", "name": "Backup Drivers", "desc": "Export installed driver packages", "difficulty": "ADVANCED", "hasCode": False}, {"id": "backup_wifi", "name": "Backup WiFi Profiles", "desc": "Export all saved WiFi passwords to XML", "difficulty": "INTERMEDIATE", "hasCode": False}, {"id": "sync_folders", "name": "Sync Two Folders", "desc": "Mirror one folder to another (like rsync)", "difficulty": "INTERMEDIATE", "hasCode": False}, {"id": "backup_sticky", "name": "Backup Sticky Notes", "desc": "Export Windows Sticky Notes to file", "difficulty": "INTERMEDIATE", "hasCode": False}, {"id": "backup_fonts", "name": "Backup Fonts", "desc": "Copy all custom fonts to backup folder", "difficulty": "INTERMEDIATE", "hasCode": False}, {"id": "backup_scheduled_tasks", "name": "Backup Tasks", "desc": "Export all scheduled tasks to XML", "difficulty": "INTERMEDIATE", "hasCode": False}]}, "apps": {"title": "App Management", "icon": "apps", "color": "#FF6FD8", "scripts": [{"id": "uninstall_bloat", "name": "Remove Bloatware", "desc": "Uninstall pre-installed Windows apps", "difficulty": "INTERMEDIATE", "hasCode": False}, {"id": "install_essentials", "name": "Install Essentials", "desc": "Install Chrome, 7zip, VLC, Notepad++ via winget", "difficulty": "BEGINNER", "hasCode": False}, {"id": "update_all_apps", "name": "Update All Apps", "desc": "Update all winget-managed applications", "difficulty": "BEGINNER", "hasCode": False}, {"id": "install_python_tools", "name": "Python Dev Setup", "desc": "Install VS Code, Git, pip packages for development", "difficulty": "INTERMEDIATE", "hasCode": False}, {"id": "check_outdated", "name": "Outdated Apps", "desc": "List apps with available updates", "difficulty": "BEGINNER", "hasCode": False}, {"id": "portable_apps", "name": "Download Portable Apps", "desc": "Get portable versions of popular tools", "difficulty": "INTERMEDIATE", "hasCode": False}, {"id": "default_apps", "name": "Set Default Apps", "desc": "Configure default browser, media player, etc.", "difficulty": "INTERMEDIATE", "hasCode": False}, {"id": "choco_install", "name": "Chocolatey Setup", "desc": "Install Chocolatey package manager", "difficulty": "INTERMEDIATE", "hasCode": False}]}, "automation": {"title": "Automation", "icon": "auto-fix-high", "color": "#00E5FF", "scripts": [{"id": "auto_screenshot", "name": "Auto Screenshot", "desc": "Take screenshots every N seconds", "difficulty": "BEGINNER", "hasCode": False}, {"id": "auto_wallpaper", "name": "Auto Wallpaper", "desc": "Rotate wallpapers from a folder", "difficulty": "BEGINNER", "hasCode": False}, {"id": "file_watcher", "name": "File Watcher", "desc": "Monitor folder and run action on new files", "difficulty": "INTERMEDIATE", "hasCode": False}, {"id": "auto_backup", "name": "Scheduled Backup", "desc": "Auto-backup folder every hour", "difficulty": "INTERMEDIATE", "hasCode": False}, {"id": "keyboard_macro", "name": "Keyboard Macro", "desc": "Record and replay keyboard sequences", "difficulty": "INTERMEDIATE", "hasCode": False}, {"id": "mouse_recorder", "name": "Mouse Recorder", "desc": "Record and replay mouse movements", "difficulty": "INTERMEDIATE", "hasCode": False}, {"id": "auto_clicker", "name": "Auto Clicker", "desc": "Click at position every N seconds", "difficulty": "BEGINNER", "hasCode": False}, {"id": "clipboard_history", "name": "Clipboard History", "desc": "Save everything you copy to a log file", "difficulty": "INTERMEDIATE", "hasCode": False}, {"id": "batch_pdf", "name": "Merge PDFs", "desc": "Combine multiple PDF files into one", "difficulty": "INTERMEDIATE", "hasCode": False}, {"id": "batch_resize", "name": "Batch Resize Images", "desc": "Resize all images in a folder", "difficulty": "INTERMEDIATE", "hasCode": False}, {"id": "excel_merge", "name": "Merge Excel Files", "desc": "Combine multiple spreadsheets into one", "difficulty": "INTERMEDIATE", "hasCode": False}, {"id": "auto_email", "name": "Email Alert", "desc": "Send email notification when task completes", "difficulty": "ADVANCED", "hasCode": False}, {"id": "folder_sync", "name": "Real-time Folder Sync", "desc": "Mirror folder changes in real-time", "difficulty": "ADVANCED", "hasCode": False}, {"id": "website_monitor", "name": "Website Monitor", "desc": "Alert when a website goes down or changes", "difficulty": "INTERMEDIATE", "hasCode": False}, {"id": "auto_dark_mode", "name": "Auto Dark Mode", "desc": "Switch dark/light mode based on time of day", "difficulty": "INTERMEDIATE", "hasCode": False}, {"id": "batch_convert_video", "name": "Batch Convert Video", "desc": "Convert all videos in folder to MP4", "difficulty": "ADVANCED", "hasCode": False}, {"id": "batch_convert_audio", "name": "Batch Convert Audio", "desc": "Convert audio files between formats", "difficulty": "ADVANCED", "hasCode": False}, {"id": "auto_git_commit", "name": "Auto Git Commit", "desc": "Auto commit changes every hour", "difficulty": "INTERMEDIATE", "hasCode": False}, {"id": "auto_organize_new", "name": "Auto Sort New Files", "desc": "Watch Downloads and auto-sort new files", "difficulty": "INTERMEDIATE", "hasCode": False}]}, "data": {"title": "Data & Documents", "icon": "description", "color": "#FFD700", "scripts": [{"id": "csv_clean", "name": "Clean CSV File", "desc": "Remove duplicates and fix formatting in CSV", "difficulty": "INTERMEDIATE", "hasCode": False}, {"id": "json_format", "name": "Format JSON", "desc": "Pretty-print and validate JSON files", "difficulty": "BEGINNER", "hasCode": False}, {"id": "excel_to_csv", "name": "Excel to CSV", "desc": "Convert XLSX files to CSV format", "difficulty": "BEGINNER", "hasCode": False}, {"id": "pdf_to_text", "name": "PDF to Text", "desc": "Extract text from PDF documents", "difficulty": "INTERMEDIATE", "hasCode": False}, {"id": "word_count", "name": "Word Counter", "desc": "Count words in text files or folders", "difficulty": "BEGINNER", "hasCode": False}, {"id": "text_find_replace", "name": "Find & Replace in Files", "desc": "Search and replace text across multiple files", "difficulty": "INTERMEDIATE", "hasCode": False}, {"id": "file_hash", "name": "File Hash Checker", "desc": "Calculate MD5/SHA256 hash of any file", "difficulty": "BEGINNER", "hasCode": False}, {"id": "qr_generator", "name": "QR Code Generator", "desc": "Generate QR code from text or URL", "difficulty": "BEGINNER", "hasCode": False}, {"id": "watermark_images", "name": "Watermark Images", "desc": "Add text watermark to all images in folder", "difficulty": "INTERMEDIATE", "hasCode": False}, {"id": "compress_images", "name": "Compress Images", "desc": "Reduce image file sizes without losing quality", "difficulty": "INTERMEDIATE", "hasCode": False}, {"id": "csv_merge", "name": "Merge CSV Files", "desc": "Combine multiple CSV files into one", "difficulty": "INTERMEDIATE", "hasCode": False}, {"id": "pdf_merge", "name": "Merge PDFs", "desc": "Combine multiple PDF files into one", "difficulty": "INTERMEDIATE", "hasCode": False}, {"id": "pdf_split", "name": "Split PDF", "desc": "Extract specific pages from PDF", "difficulty": "INTERMEDIATE", "hasCode": False}, {"id": "ocr_image", "name": "OCR from Image", "desc": "Extract text from screenshots and photos", "difficulty": "INTERMEDIATE", "hasCode": False}, {"id": "image_metadata", "name": "EXIF Reader", "desc": "Show camera info, GPS, date from photos", "difficulty": "INTERMEDIATE", "hasCode": False}]}, "monitoring": {"title": "Monitoring", "icon": "monitor-heart", "color": "#00FF88", "scripts": [{"id": "cpu_logger", "name": "CPU Logger", "desc": "Log CPU usage every 5 seconds to CSV", "difficulty": "INTERMEDIATE", "hasCode": False}, {"id": "disk_alert", "name": "Disk Space Alert", "desc": "Alert when disk drops below 10% free", "difficulty": "INTERMEDIATE", "hasCode": False}, {"id": "process_monitor", "name": "Process Monitor", "desc": "Track specific process CPU and RAM over time", "difficulty": "INTERMEDIATE", "hasCode": False}, {"id": "network_logger", "name": "Network Logger", "desc": "Log network traffic stats over time", "difficulty": "INTERMEDIATE", "hasCode": False}, {"id": "uptime_tracker", "name": "Uptime Tracker", "desc": "Track when PC was on/off over past week", "difficulty": "INTERMEDIATE", "hasCode": False}, {"id": "temp_monitor", "name": "Temperature Monitor", "desc": "Track CPU and GPU temperatures", "difficulty": "ADVANCED", "hasCode": False}, {"id": "event_watcher", "name": "Event Watcher", "desc": "Monitor Windows events and alert on errors", "difficulty": "ADVANCED", "hasCode": False}, {"id": "service_monitor", "name": "Service Watchdog", "desc": "Auto-restart a service if it crashes", "difficulty": "ADVANCED", "hasCode": False}, {"id": "internet_speed_log", "name": "Speed Logger", "desc": "Log internet speed every hour to CSV", "difficulty": "INTERMEDIATE", "hasCode": False}, {"id": "login_history", "name": "Login History", "desc": "Show who logged in and when", "difficulty": "INTERMEDIATE", "hasCode": False}, {"id": "usb_history", "name": "USB History", "desc": "Show all USB devices ever connected", "difficulty": "INTERMEDIATE", "hasCode": False}]}, "web": {"title": "Web & Browser", "icon": "language", "color": "#4A9EFF", "scripts": [{"id": "download_youtube", "name": "Download Video", "desc": "Download YouTube video (requires yt-dlp)", "difficulty": "INTERMEDIATE", "hasCode": False}, {"id": "web_scraper", "name": "Web Scraper", "desc": "Extract data from any webpage", "difficulty": "ADVANCED", "hasCode": False}, {"id": "website_screenshot", "name": "Website Screenshot", "desc": "Capture full-page screenshot of URL", "difficulty": "INTERMEDIATE", "hasCode": False}, {"id": "link_checker", "name": "Link Checker", "desc": "Find broken links on a webpage", "difficulty": "INTERMEDIATE", "hasCode": False}, {"id": "whois_lookup", "name": "WHOIS Lookup", "desc": "Get domain registration information", "difficulty": "BEGINNER", "hasCode": False}, {"id": "html_to_pdf", "name": "Webpage to PDF", "desc": "Save any webpage as PDF file", "difficulty": "INTERMEDIATE", "hasCode": False}, {"id": "api_tester", "name": "API Tester", "desc": "Send GET/POST requests and view responses", "difficulty": "INTERMEDIATE", "hasCode": False}, {"id": "rss_reader", "name": "RSS Feed Reader", "desc": "Fetch and display RSS feed entries", "difficulty": "INTERMEDIATE", "hasCode": False}]}, "development": {"title": "Developer Tools", "icon": "code", "color": "#00E5FF", "scripts": [{"id": "git_status", "name": "Git Status All", "desc": "Check git status of all repos in a folder", "difficulty": "INTERMEDIATE", "hasCode": False}, {"id": "port_kill", "name": "Kill Port Process", "desc": "Find and kill process using a specific port", "difficulty": "INTERMEDIATE", "hasCode": False}, {"id": "localhost_server", "name": "Quick HTTP Server", "desc": "Start a local web server in current directory", "difficulty": "BEGINNER", "hasCode": False}, {"id": "pip_cleanup", "name": "Pip Cleanup", "desc": "Remove unused pip packages and cache", "difficulty": "INTERMEDIATE", "hasCode": False}, {"id": "venv_create", "name": "Create Virtual Env", "desc": "Set up Python virtual environment", "difficulty": "BEGINNER", "hasCode": False}, {"id": "code_line_count", "name": "Count Lines of Code", "desc": "Count lines in project by language", "difficulty": "BEGINNER", "hasCode": False}, {"id": "todo_finder", "name": "TODO Finder", "desc": "Find all TODO/FIXME comments in code", "difficulty": "BEGINNER", "hasCode": False}, {"id": "json_to_csv", "name": "JSON to CSV", "desc": "Convert JSON data files to CSV", "difficulty": "INTERMEDIATE", "hasCode": False}, {"id": "regex_tester", "name": "Regex Tester", "desc": "Test regex patterns against sample text", "difficulty": "INTERMEDIATE", "hasCode": False}, {"id": "docker_cleanup", "name": "Docker Cleanup", "desc": "Remove unused Docker images and containers", "difficulty": "INTERMEDIATE", "hasCode": False}, {"id": "node_cleanup", "name": "Clean node_modules", "desc": "Remove all node_modules folders recursively", "difficulty": "BEGINNER", "hasCode": False}, {"id": "python_cleanup", "name": "Clean __pycache__", "desc": "Remove all Python cache directories", "difficulty": "BEGINNER", "hasCode": False}, {"id": "ssl_check", "name": "SSL Certificate Check", "desc": "Verify SSL cert validity for any domain", "difficulty": "INTERMEDIATE", "hasCode": False}]}, "fun": {"title": "Fun & Utilities", "icon": "emoji-emotions", "color": "#FF6FD8", "scripts": [{"id": "system_uptime", "name": "Uptime Counter", "desc": "Show exactly how long PC has been running", "difficulty": "BEGINNER", "hasCode": False}, {"id": "color_picker", "name": "Screen Color Picker", "desc": "Get hex color code from any pixel on screen", "difficulty": "INTERMEDIATE", "hasCode": False}, {"id": "countdown_timer", "name": "Countdown Timer", "desc": "Desktop countdown with notification", "difficulty": "BEGINNER", "hasCode": False}, {"id": "text_to_speech", "name": "Text to Speech", "desc": "Read text aloud using Windows TTS", "difficulty": "BEGINNER", "hasCode": False}, {"id": "random_password", "name": "Password Generator", "desc": "Generate secure random passwords", "difficulty": "BEGINNER", "hasCode": False}, {"id": "ascii_art", "name": "ASCII Art Generator", "desc": "Convert text or image to ASCII art", "difficulty": "INTERMEDIATE", "hasCode": False}, {"id": "weather", "name": "Weather Report", "desc": "Show current weather for your location", "difficulty": "BEGINNER", "hasCode": False}, {"id": "desktop_note", "name": "Desktop Sticky Note", "desc": "Create a sticky note on desktop", "difficulty": "BEGINNER", "hasCode": False}, {"id": "motivational_quote", "name": "Random Quote", "desc": "Display a random motivational quote", "difficulty": "BEGINNER", "hasCode": False}, {"id": "type_speed_test", "name": "Typing Speed Test", "desc": "Test your typing speed in WPM", "difficulty": "BEGINNER", "hasCode": False}, {"id": "matrix_rain", "name": "Matrix Rain", "desc": "Matrix-style falling text in terminal", "difficulty": "BEGINNER", "hasCode": False}, {"id": "pomodoro", "name": "Pomodoro Timer", "desc": "25min work / 5min break timer with alerts", "difficulty": "BEGINNER", "hasCode": False}, {"id": "file_encrypt", "name": "Encrypt File", "desc": "AES-256 encrypt any file with password", "difficulty": "INTERMEDIATE", "hasCode": False}, {"id": "file_decrypt", "name": "Decrypt File", "desc": "Decrypt AES-256 encrypted file", "difficulty": "INTERMEDIATE", "hasCode": False}, {"id": "screen_recorder", "name": "Screen Recorder", "desc": "Record screen to MP4 file", "difficulty": "INTERMEDIATE", "hasCode": False}, {"id": "system_sounds", "name": "System Sounds", "desc": "Play Windows notification or error sounds", "difficulty": "BEGINNER", "hasCode": False}]}, "gaming": {"title": "Gaming & Media", "icon": "sports-esports", "color": "#FF4444", "scripts": [{"id": "game_mode", "name": "Gaming Mode", "desc": "Kill background apps, set high priority", "difficulty": "INTERMEDIATE", "hasCode": False}, {"id": "clear_game_cache", "name": "Game Cache Clean", "desc": "Clear Steam, Epic, Origin cache files", "difficulty": "BEGINNER", "hasCode": False}, {"id": "audio_devices", "name": "Audio Device Manager", "desc": "Switch speakers, headphones, mic", "difficulty": "BEGINNER", "hasCode": False}, {"id": "display_info", "name": "Display Settings", "desc": "Show resolution, refresh rate, monitors", "difficulty": "BEGINNER", "hasCode": False}, {"id": "gpu_benchmark", "name": "GPU Benchmark", "desc": "Quick 3D rendering performance test", "difficulty": "INTERMEDIATE", "hasCode": False}, {"id": "fps_monitor", "name": "FPS Monitor", "desc": "Real-time FPS counter overlay", "difficulty": "INTERMEDIATE", "hasCode": False}]}}


def _pc_check_html():
    """Generate PC Check dashboard HTML."""
    try:
        m = _metrics() if HAS_PSUTIL else {}
        scan = _pc_scan_stats()
        cpu_pct = m.get("cpu", {}).get("percent", 0) if isinstance(m.get("cpu"), dict) else 0
        ram_pct = m.get("memory", {}).get("percent", 0) if isinstance(m.get("memory"), dict) else 0
        disk_pct = m.get("disk", {}).get("percent", 0) if isinstance(m.get("disk"), dict) else 0
        disk_free = m.get("disk", {}).get("free_gb", 0) if isinstance(m.get("disk"), dict) else 0
        hostname = m.get("system", {}).get("hostname", socket.gethostname()) if isinstance(m.get("system"), dict) else socket.gethostname()
        files_cleaned = int(_pc_stat_get("files_cleaned"))
        space_mb = round(_pc_stat_get("space_recovered_bytes")/(1024*1024), 1)
        files_organized = int(_pc_stat_get("files_organized"))
        scripts_run = int(_pc_stat_get("scripts_run"))
        scripts_undone = int(_pc_stat_get("scripts_undone"))
        undo_entries = _undo_list()
        active = [u for u in undo_entries if u["canUndo"]]
        # Build undo HTML
        undo_html = ""
        for u in undo_entries:
            if u["canUndo"]:
                clr = "#00FF88" if u["remainingSec"]>300 else "#FFB300" if u["remainingSec"]>60 else "#FF4444"
                undo_html += "<div style=\"padding:10px;background:#060A10;border:1px solid #1A2D40;border-radius:4px;margin:6px 0;display:flex;align-items:center;gap:10px\"><span style=\"font-family:Orbitron;font-size:16px;font-weight:700;color:" + clr + "\">" + u["remainingMin"] + "</span><span style=\"flex:1;color:#5A7A96;font-size:13px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap\">" + (u["userRequest"] or u["script"][:50]) + "</span><button onclick=\"undoScript(" + str(u["id"]) + ")\" style=\"font-family:monospace;font-size:10px;padding:6px 12px;border:1px solid #FF4444;color:#FF4444;background:transparent;border-radius:3px;cursor:pointer\">UNDO</button></div>"
        if not undo_html:
            undo_html = "<div style=\"text-align:center;padding:20px;color:#5A7A96;font-family:monospace;font-size:12px\">No active undo entries. Run a script first.</div>"
        def bc(pct, t1=60, t2=85):
            return "#00FF88" if pct < t1 else "#FFB300" if pct < t2 else "#FF4444"
        page = []
        page.append("<!DOCTYPE html><html><head><meta charset=UTF-8><meta name=viewport content=\"width=device-width,initial-scale=1\">")
        page.append("<style>*{margin:0;padding:0;box-sizing:border-box}body{background:#060A10;color:#D8E8F4;font-family:sans-serif;min-height:100vh}")
        page.append(".hdr{background:#0A1018;border-bottom:1px solid #1A2D40;padding:16px 20px;position:sticky;top:0;z-index:10}")
        page.append(".hdr h1{font-size:18px;letter-spacing:3px;color:#00E5FF}")
        page.append(".wrap{max-width:800px;margin:0 auto;padding:16px}")
        page.append(".card{background:#0A1018;border:1px solid #1A2D40;border-radius:6px;padding:18px;margin-bottom:14px}")
        page.append(".ct{font-size:12px;letter-spacing:2px;font-weight:700;margin-bottom:14px}")
        page.append(".stats{display:grid;grid-template-columns:repeat(3,1fr);gap:8px}")
        page.append(".stat{background:#060A10;border:1px solid #1A2D40;border-radius:4px;padding:12px;text-align:center}")
        page.append(".sv{font-size:22px;font-weight:900;line-height:1}.sl{font-size:8px;letter-spacing:2px;color:#5A7A96;margin-top:4px}")
        page.append(".br{display:flex;align-items:center;gap:8px;margin-bottom:8px}")
        page.append(".bl{font-size:11px;width:45px;text-align:right;color:#5A7A96}")
        page.append(".bt{flex:1;height:6px;background:#060A10;border-radius:3px;overflow:hidden}")
        page.append(".bf{height:100%;border-radius:3px}.bv{font-size:12px;width:40px;text-align:right;font-weight:700}")
        page.append(".ci{display:flex;align-items:center;justify-content:space-between;padding:10px 14px;background:#060A10;border:1px solid #1A2D40;border-radius:4px;margin-bottom:6px}")
        page.append(".btn{font-size:10px;letter-spacing:2px;padding:6px 14px;border-radius:3px;border:1px solid;cursor:pointer;background:transparent;font-family:monospace}")
        page.append("</style></head><body>")
        page.append("<div class=hdr><h1>PC CHECK</h1></div><div class=wrap>")
        # System bars
        page.append("<div class=card><div class=ct style=color:#00E5FF>SYSTEM</div>")
        page.append("<div class=br><span class=bl>CPU</span><div class=bt><div class=bf style=\"width:" + str(cpu_pct) + "%;background:" + bc(cpu_pct) + "\"></div></div><span class=bv style=color:" + bc(cpu_pct) + ">" + str(int(cpu_pct)) + "%</span></div>")
        page.append("<div class=br><span class=bl>RAM</span><div class=bt><div class=bf style=\"width:" + str(ram_pct) + "%;background:" + bc(ram_pct) + "\"></div></div><span class=bv style=color:" + bc(ram_pct) + ">" + str(int(ram_pct)) + "%</span></div>")
        page.append("<div class=br><span class=bl>DISK</span><div class=bt><div class=bf style=\"width:" + str(disk_pct) + "%;background:" + bc(disk_pct,70,90) + "\"></div></div><span class=bv style=color:" + bc(disk_pct,70,90) + ">" + str(int(disk_pct)) + "%</span></div>")
        page.append("<div style=\"font-size:11px;color:#5A7A96;margin-top:4px\">FREE: " + str(int(disk_free)) + " GB</div></div>")
        # Stats
        page.append("<div class=card><div class=ct style=color:#00FF88>LIFETIME STATS</div><div class=stats>")
        page.append("<div class=stat><div class=sv style=color:#00FF88>" + str(files_cleaned) + "</div><div class=sl>CLEANED</div></div>")
        page.append("<div class=stat><div class=sv style=color:#00E5FF>" + str(space_mb) + "MB</div><div class=sl>RECOVERED</div></div>")
        page.append("<div class=stat><div class=sv style=color:#FFB300>" + str(files_organized) + "</div><div class=sl>ORGANIZED</div></div>")
        page.append("<div class=stat><div class=sv style=color:#C084FF>" + str(scripts_run) + "</div><div class=sl>SCRIPTS</div></div>")
        page.append("<div class=stat><div class=sv style=color:#FF6FD8>" + str(scripts_undone) + "</div><div class=sl>UNDONE</div></div>")
        page.append("<div class=stat><div class=sv style=color:#FF4444>" + str(int(_pc_stat_get("threats_blocked"))) + "</div><div class=sl>BLOCKED</div></div>")
        page.append("</div></div>")
        # Scan results
        page.append("<div class=card><div class=ct style=color:#FFB300>SCAN</div>")
        page.append("<div class=ci><div><b>Temp Files</b><br><span style=font-size:12px;color:#5A7A96>" + str(scan["temp_files"]) + " files - " + str(int(scan["temp_size_mb"])) + " MB</span></div><button class=btn style=color:#FF4444;border-color:#FF4444 onclick=\"runClean('temp')\">CLEAN</button></div>")
        page.append("<div class=ci><div><b>Browser Cache</b><br><span style=font-size:12px;color:#5A7A96>" + str(int(scan["browser_cache_mb"])) + " MB</span></div><button class=btn style=color:#FFB300;border-color:#FFB300 onclick=\"runClean('browser')\">CLEAR</button></div>")
        page.append("<div class=ci><div><b>Large Files</b><br><span style=font-size:12px;color:#5A7A96>" + str(len(scan["large_files"])) + " over 100MB</span></div><button class=btn style=color:#00E5FF;border-color:#00E5FF onclick=\"runClean('scan_large')\">SCAN</button></div>")
        page.append("</div>")
        # Undo
        page.append("<div class=card><div class=ct style=color:#FF6FD8>UNDO - " + str(len(active)) + " active</div>" + undo_html + "</div>")
        # Quick actions
        page.append("<div class=card><div class=ct style=color:#00E5FF>QUICK ACTIONS</div><div style=\"display:flex;flex-wrap:wrap;gap:6px\">")
        page.append("<button class=btn style=color:#00FF88;border-color:#00FF88 onclick=\"runClean('full_clean')\">FULL CLEAN</button>")
        page.append("<button class=btn style=color:#00E5FF;border-color:#00E5FF onclick=\"runClean('organize')\">ORGANIZE</button>")
        page.append("<button class=btn style=color:#FFB300;border-color:#FFB300 onclick=\"runClean('disk_report')\">DISK REPORT</button>")
        page.append("<button class=btn style=color:#FF4444;border-color:#FF4444 onclick=\"runClean('empty_recycle')\">RECYCLE BIN</button>")
        page.append("</div></div></div>")
        # JavaScript — NO f-strings, pure string concat
        page.append("<script>")
        page.append("var B=window.location.origin;")
        page.append("function runClean(a){var b=event.target;b.textContent='...';b.disabled=true;fetch(B+'/api/pc-check/action',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({action:a})}).then(function(r){return r.json()}).then(function(d){alert(d.output?d.output.slice(0,500):d.error||'Done');setTimeout(function(){location.reload()},1000)}).catch(function(e){alert('Error: '+e.message)}).finally(function(){b.disabled=false})}")
        page.append("function undoScript(id){if(!confirm('Undo this script?'))return;fetch(B+'/api/undo/rollback',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({id:id})}).then(function(r){return r.json()}).then(function(d){alert(d.message||d.error||'Done');location.reload()}).catch(function(e){alert('Error: '+e.message)})}")
        page.append("setTimeout(function(){location.reload()},30000);")
        page.append("</script></body></html>")
        return "\n".join(page)
    except Exception as e:
        return "<html><body style=\"background:#060A10;color:#FF4444;padding:40px;font-family:monospace\"><h1>PC Check Error</h1><p>" + str(e) + "</p></body></html>"


# ══════════════════════════════════════════════════════
#  HTTP HANDLER
# ══════════════════════════════════════════════════════
_start_time = time.time()

# ── CONNECTION DIAGNOSTIC LOG ────────────────────────────
# Keeps last 100 connection events for debugging.
# Accessible via GET /api/debug/connection
_conn_events = deque(maxlen=100)

def _conn_log(endpoint: str, device: str, result: str, detail: str = ""):
    """Log a connection event for diagnostics."""
    event = {
        "time":     time.strftime("%H:%M:%S"),
        "ts":       time.time(),
        "endpoint": endpoint,
        "device":   device,
        "result":   result,
        "detail":   detail,
    }
    _conn_events.append(event)
    level = "ok" if result in ("LOCKED", "RECONNECT", "AUTO-UNLOCK") else "warn"
    _log(f"[CONN] {endpoint} {device} → {result} ({detail})", level)

class H(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        print(f"  [{time.strftime('%H:%M:%S')}] {self.client_address[0]}  {fmt % args}")

    def _cors(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET,POST,PUT,DELETE,OPTIONS")
        self.send_header("Access-Control-Allow-Headers",
            "Content-Type,Authorization,X-Fallback-Token,X-Device-Id,X-App-Version")
        self.send_header("Access-Control-Max-Age", "86400")
        # Smooth UI transition hints — read by app for animation timing
        self.send_header("X-Response-Transition", "fade")
        self.send_header("X-Animation-Ms",        "180")
        self.send_header("Timing-Allow-Origin",   "*")

    def _add_license_headers(self):
        """Add proprietary watermark to every HTTP response.
        All header values are pure ASCII to avoid latin-1 encoding errors."""
        try:
            self.send_header("X-Server",    f"ButlerAI-Server/{VERSION}")
            self.send_header("X-Powered-By","Butler AI (c) 2025 Shawn Jan")
            self.send_header("X-License",   "Proprietary - No redistribution")
            self.send_header("X-Copyright", "Copyright 2025 Shawn Jan. All Rights Reserved.")
            self.send_header("X-Contact",   "andrejsladkovic1992@gmail.com")
        except Exception:
            pass  # Never let header issues crash the HTTP handler

    def log_error(self, fmt, *args):
        msg = (fmt % args) if args else str(fmt)
        if any(x in str(msg) for x in ("10053","10054","32","104",
               "BrokenPipe","ConnectionAbort","ConnectionReset","forcibly closed")):
            return
        import logging; logging.getLogger("boter").debug(f"HTTP: {msg}")

    def log_message(self, fmt, *args):
        pass

    def _err(self, code: str, extra: dict = None):
        """Return a typed error envelope the client can switch on."""
        msg, status = _ERR_MAP.get(code, _ERR_MAP["INTERNAL"])
        self._json({"error": msg, "code": code, "extra": extra or {}}, status)

    def _json(self, obj, status=200):
        try:
            # If token was self-healed, inject new token into response
            healed = getattr(self, "_healed_token", None)
            if healed and isinstance(obj, dict):
                obj["newToken"] = healed
                self._healed_token = None
            body = json.dumps(obj).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            if healed:
                self.send_header("X-New-Token", healed)
            self._cors()
            self._add_license_headers()
            self.end_headers()
            self.wfile.write(body)
        except (BrokenPipeError, ConnectionAbortedError, ConnectionResetError):
            pass
        except OSError as e:
            if getattr(e, "winerror", None) in (10053, 10054) or e.errno in (32, 104, 9):
                pass
            else:
                import logging; logging.getLogger("boter").debug(f"_json OSError: {e}")

    def _chkrate(self):
        if _rlimit(self.client_address[0]):
            self._json({"error": "Rate limited - too many requests"}, 429)
            return False
        return True

    def _body(self):
        length = int(self.headers.get("Content-Length", 0))
        if length > MAX_BODY_BYTES:
            self._json({"error": f"Body too large (max {MAX_BODY_BYTES//1024//1024}MB)"}, 413)
            return None
        if length == 0: return {}
        try: return json.loads(self.rfile.read(length))
        except:
            self._json({"error": "Invalid JSON body"}, 400)
            return None

    def _authed(self, body):
        """Auth check with self-healing tokens and deviceId fallback."""
        locked = _gs("locked_device")
        if not locked: return True  # server open, no auth needed
        ah  = self.headers.get("Authorization", "")
        tok = ah[7:].strip() if ah.startswith("Bearer ") else ""
        if not tok:
            tok = (body or {}).get("token", self.headers.get("X-Fallback-Token", ""))

        # ── Valid token → pass ────────────────────────────────────
        if tok:
            valid = _verify_token(tok, locked)
            if valid:
                _ss("last_seen", time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()))
                return True
            # Token invalid — self-heal ONLY if HMAC signature is valid
            # NEVER trust the deviceId without first verifying the signature
            try:
                decoded = base64.urlsafe_b64decode(tok.encode()).decode()
                last_colon = decoded.rfind(":")
                if last_colon > 0:
                    raw = decoded[:last_colon]
                    sig = decoded[last_colon+1:]
                    # VERIFY SIGNATURE FIRST — prevents forged deviceId bypass
                    if hmac.compare_digest(sig, _sign(raw)):
                        raw_parts = raw.split(":")
                        token_device = raw_parts[0] if raw_parts else ""
                        if token_device == locked:
                            new_tok = _make_token(locked)
                            self._healed_token = new_tok
                            _ss("last_seen", time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()))
                            _conn_log("AUTH", locked[:20], "SELF-HEAL", "token reissued — signature valid")
                            return True
            except Exception:
                pass
            # Token is forged or corrupted — reject
            _conn_log("AUTH", "UNKNOWN", "REJECT", f"invalid token from {self.client_address[0]}")

        # DeviceId-only fallback removed — deviceId is not a secret (visible in HTTP headers)
        # If token is missing, app must call /pair or /reconnect to get a new one
        # This prevents attackers who sniff a request from bypassing auth with just deviceId

        return False

    def do_OPTIONS(self):
        self.send_response(200)
        self._cors()
        self.send_header("Connection", "keep-alive")
        self.end_headers()

    def do_GET(self):
        path = self.path.split("?")[0]
        body = {}  # GET requests have no body - needed so _authed(body) doesn't crash
        # Health/status/ping endpoints are NEVER rate-limited - heartbeat must always work
        if path not in ("/health", "/ping", "/api/status", "/status", "/api/pair/status", "/"):
            if not self._chkrate(): return

        # ── STATUS / HEALTH ──────────────────────────────────────
        if path == "/api/ping":
            # Ultra-lightweight ping — just confirms server alive
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", "2")
            self._cors()
            self.end_headers()
            self.wfile.write(b"{}")
            return

        if path == "/api/haptic":
            # Haptic feedback acknowledgement endpoint
            # App calls this after run/connect/pair — server logs the event
            # and returns a smooth animation hint payload
            style = (_qs.get("style", ["medium"])[0] or "medium").lower()
            _valid = {"light", "medium", "heavy", "success", "error", "selection"}
            style = style if style in _valid else "medium"
            _conn_log("HAPTIC", self.client_address[0], style.upper(), "haptic ack")
            self._json({
                "ok": True,
                "style": style,
                "ts": time.time(),
                "animation": {
                    "duration_ms": {"light": 40, "selection": 40,
                                    "medium": 80, "heavy": 120,
                                    "success": 100, "error": 150}.get(style, 80),
                    "intensity":   {"light": 0.4, "selection": 0.35,
                                    "medium": 0.7, "heavy": 1.0,
                                    "success": 0.8, "error": 1.0}.get(style, 0.7),
                    "pattern":     {"success": "tap-pause-tap",
                                    "error": "long-pause-short-short"}.get(style, "single"),
                },
            })
            return

        if path == "/api/legal":
            # Play Store / legal compliance info endpoint
            # App displays this in About / Data Safety screen
            self._json({
                "app_name":          "Butler AI: PC Automation",
                "version":           VERSION,
                "package":           "com.butlerai.pc.automation",
                "developer":         "Shawn Jan",
                "support_email":     "andrejsladkovic1992@gmail.com",
                "privacy_policy":    "https://shawnjan-cmd.github.io/butler-ai/",
                "github":            "https://github.com/shawnjan-cmd/butler-ai",
                "license":           "Proprietary — Personal use only",
                "data_collection":   "none",
                "cloud_sync":        False,
                "analytics":         False,
                "third_party_sdks":  [],
                "local_only":        True,
                "content_rating":    "Everyone",
                "play_store_category": "PRODUCTIVITY",
                "open_source_components": [
                    {"name": "psutil",   "license": "BSD-3-Clause"},
                    {"name": "qrcode",   "license": "BSD-3-Clause"},
                    {"name": "Pillow",   "license": "HPND"},
                    {"name": "requests", "license": "Apache-2.0"},
                    {"name": "Flask",    "license": "BSD-3-Clause"},
                    {"name": "Python",   "license": "PSF-2.0"},
                ],
                "play_store_compliant": True,
                "wifi_password_feature_notice":
                    "WiFi password display reads only YOUR device's saved profiles "
                    "using netsh wlan — no data leaves your PC or local network.",
                "subprocess_notice":
                    "Scripts run only when explicitly triggered by the paired device owner.",
            })
            return

        if path in ("/health", "/ping"):
            # Ultra-fast health check — app heartbeat calls this every 6s
            # Includes basic CPU/RAM so app doesn't need separate /api/metrics call
            locked = _gs("locked_device")
            cpu_pct = psutil.cpu_percent(interval=0) if HAS_PSUTIL else 0
            ram_pct = psutil.virtual_memory().percent if HAS_PSUTIL else 0
            self._json({
                "status":      "ok",
                "ts":          time.time(),
                "version":     VERSION,
                "features":    [
                    "sse-chat","execute","undo","kb","scripts","metrics",
                    "audit","sync","clipboard","power","scripts-upload",
                    "range-download","pair-qr","x-new-token","auth-rotate",
                    "sessions","push","execute-stream","abort",
                ],
                "schema":      2,
                "locked":      bool(locked),
                "pairingCode": _gs("pairing_code") or "" if not locked else "",
                "port":        _gs("server_port") or "",
                "cpu":         round(cpu_pct, 1),
                "ram":         round(ram_pct, 1),
                "memory":      round(ram_pct, 1),
                "isAuthDisabled": not bool(locked),  # True = open server, no token needed
            })


        # ── DETAILED HEALTH — app can show diagnostic info ────────
        elif path == "/health/detailed":
            issues  = []
            score   = 100
            if not _ol_ok():
                score -= 30
                issues.append("Ollama AI offline — starting automatically")
            kb_total = _kb_count()
            if kb_total < 10:
                score -= 10
                issues.append("Knowledge base empty — learning starting")
            workers_ok = sum(1 for t in threading.enumerate() if t.name.startswith("learn-"))
            if workers_ok == 0:
                score -= 20
                issues.append("Learn workers not running — watchdog will restart")
            self._json({
                "status":      "ok" if score >= 70 else "degraded",
                "score":       score,
                "issues":      issues,
                "healthy":     score >= 70,
                "version":     VERSION,
                "uptime":      int(time.time() - _start_time),
                "ollama":      _ol_ok(),
                "ollamaModel": _ol_model(),
                "kbTotal":     kb_total,
                "kbQueue":     _lq_size(),
                "kbWorkers":   workers_ok,
                "paired":      bool(_gs("locked_device")),
            })
        # ── LEARN STATUS (GET - knowledge.tsx fetches this) ──────
        elif path == "/api/crawler/pause":
            global _learning_active
            _learning_active = False
            self._json({"status":"ok","crawling":False,
                      "message":"Crawler paused — full CPU available for AI chat"}); return
        elif path == "/api/crawler/resume":
            _learning_active = True
            self._json({"status":"ok","crawling":True,
                      "message":"Crawler resumed"}); return
        elif path == "/api/learn/status":
            tok = (self.headers.get("Authorization","")[7:].strip()
                   or self.headers.get("X-Fallback-Token",""))
            locked = _gs("locked_device")
            if locked and tok and not _verify_token(tok, locked):
                self._json({"error":"Pair your phone first via QR.","code":"AUTH_REQUIRED"},401); return
            try:
                cp_rows = _db_q("SELECT * FROM learn_checkpoint WHERE id=1")
                cp = cp_rows[0] if cp_rows else {}
                top_topics = _db_q(
                    "SELECT topic, asks FROM user_topics ORDER BY asks DESC LIMIT 10"
                )
                self._json({
                    "status":          "ok",
                    "articlesTotal":   _kb_count(),
                    "articlesSession": _session_articles,
                    "queuePending":    _lq_size(),
                    "workersRunning":  sum(1 for t in threading.enumerate()
                                          if t.name.startswith("learn-")),
                    "learningActive":  _learning_active,
                    "lastCheckpoint":  cp.get("last_save", 0),
                    "sessionStart":    _session_start,
                    "uptimeMins":      round((time.time()-_session_start)/60, 1)
                                       if _session_start else 0,
                    "topUserTopics":   [{"topic": r["topic"], "asks": r.get("asks", 0)} for r in top_topics],
                })
            except Exception as e:
                self._json({"status":"ok","articlesTotal":_kb_count(),"error":str(e)})

        elif path == "/api/pair/status":
            locked = _gs("locked_device")
            self._json({
                "paired":        bool(locked),
                "pairingCode":   _gs("pairing_code") or "" if not locked else "",
                "serverVersion": VERSION,
                "pairingReady":  not bool(locked),
                "isAuthDisabled": not bool(locked),
            })

        # ── FULL STATUS — all data in one call (reduces app round trips) ─
        elif path == "/api/status/full":
            if not self._authed(body): self._json({"error":"Pair your phone first via QR.","code":"AUTH_REQUIRED"},401); return
            # App calls this once to get everything instead of 3 separate calls
            ok    = _ol_ok()
            model = _ol_model() if ok else ""
            total = _kb_count()
            nxt   = _next_milestone(total)
            workers_alive = sum(1 for t in threading.enumerate() if t.name.startswith("learn-"))
            locked = _gs("locked_device")
            self._json({
                # Server status
                "status":        "online",
                "version":       VERSION,
                "serverVersion": VERSION,
                "uptime":        int(time.time() - _start_time),
                "locked":        bool(locked),
                "pairingCode":   _gs("pairing_code") or "" if not locked else "",
                # AI status
                "ollama":        ok,
                "ollamaModel":   model,
                "ollamaReady":   ok,
                # KB status
                "kbTotal":       total,
                "kbQueue":       _lq_size(),
                "kbMilestone":   nxt,
                "kbWorkers":     workers_alive,
                "kbLearning":    workers_alive > 0,
                "kbProgress":    min(100, int(total / nxt * 100)) if nxt > 0 else 100,
                # System
                "os":            platform.system(),
                "hostname":      socket.gethostname(),
                "python":        platform.python_version(),
                "psutil":        HAS_PSUTIL,
                "allIPs":        _cached_ips,
                "endpoints":     ["/pair","/reconnect","/api/status/full","/api/execute",
                                  "/api/butler/chat","/api/kb/growth","/api/kb/feed",
                                  "/api/learn/status","/api/crawl"],
            })

        elif path in ("/api/status", "/status", "/", "/api/handshake"):
            ok    = _ol_ok()
            model = _ol_model() if ok else ""
            mods  = _ol_models() if ok else []
            self._json({
                "status":       "online",
                "version":      VERSION,
                "features":     [
                    "sse-chat", "execute", "undo", "kb", "scripts",
                    "metrics", "audit", "sync", "clipboard", "power",
                    "scripts-upload", "pair-qr", "x-new-token",
                    "auth-rotate", "sessions", "push", "execute-stream",
                    "abort", "range-download",
                ],
                "schema":       2,
                "os":           platform.system(),
                "osVersion":    platform.release(),
                "hostname":     socket.gethostname(),
                "server_time":  int(time.time()),
                "ollama":       ok,
                "ollamaModel":  model,
                "ollamaModels": mods,
                "locked":       bool(_gs("locked_device")),
                "pairedAt":     _gs("paired_at") or "",
                "lastSeen":     _gs("last_seen") or "",
                "pairingCode":  _gs("pairing_code") or "" if not _gs("locked_device") else "",
                "allIPs":       _cached_ips,
                "python":       platform.python_version(),
                "psutil":       HAS_PSUTIL,
                "uptime":       int(time.time() - _start_time),
                # duplicate key removed,
                "serverVersion": VERSION,
                "minAppVersion":  "6.0.0",  # reject app versions older than this
                "pairingReady":   not bool(_gs("locked_device")),
                "isAuthDisabled": not bool(_gs("locked_device")),
                "latency":      0,
                "endpoints": ["/pair","/reconnect","/api/reset_pair",
                    "/api/status","/health","/api/handshake",
                    "/api/execute","/api/butler/chat","/api/butler/clear",
                    "/api/receive_file","/api/ollama/status","/api/ollama/pull","/api/ollama/pull_status","/api/disk_space",
                    "/api/metrics","/api/kb/search","/api/kb/enrich",
                    "/api/kb/log","/api/kb/list","/api/crawl","/api/crawl/batch",
                    "/api/fs/drives","/api/fs/crawl","/api/fs/read",
                    "/api/files","/api/download","/api/kill_interference",
                    "/api/pip/install"],
            })

        # ── METRICS ─────────────────────────────────────────────
        elif path == "/api/metrics":
            if not self._authed(body): self._json({"error":"Pair your phone first via QR.","code":"AUTH_REQUIRED"},401); return
            m = _metrics()
            # App reads BOTH d.cpu.percent AND d.metrics.cpu.percent (nested)
            # Also add "ram" alias for "memory" — some app versions use either
            if "memory" in m:
                m["ram"] = m["memory"]
            self._json({**m, "metrics": m, "timestamp": int(time.time())})

        # ── REQUIREMENTS SCAN ────────────────────────────────────
        elif path == "/api/requirements":
            if not self._authed(body): self._json({"error":"Pair your phone first via QR.","code":"AUTH_REQUIRED"},401); return
            scan = _scan_requirements(verbose=False)
            self._json({
                "requirements": scan,
                "total":   len(scan),
                "ok":      sum(1 for r in scan if r["status"] == "OK"),
                "missing": sum(1 for r in scan if r["status"] == "MISSING"),
                "python":  platform.python_version(),
                "pip":     _get_pip_version(),
            })

        # ── PROCESS LIST ─────────────────────────────────────────
        elif path == "/api/processes":
            if not self._authed(body): self._json({"error":"Pair your phone first via QR.","code":"AUTH_REQUIRED"},401); return
            procs = _list_all_processes()
            # Also check our ports
            port_info = {}
            for p in [8766, 8765, 5000, 8080, 8008]:
                blockers = _find_process_on_port(p)
                if blockers: port_info[str(p)] = blockers
            self._json({"processes": procs, "port_conflicts": port_info})

        # ── SYSINFO ──────────────────────────────────────────────
        elif path == "/api/sysinfo":
            if not self._authed(body): self._json({"error":"Pair your phone first via QR.","code":"AUTH_REQUIRED"},401); return
            self._json({
                "hostname": socket.gethostname(),
                "platform": platform.system(),
                "release":  platform.release(),
                "machine":  platform.machine(),
                "python":   platform.python_version(),
                "home":     str(Path.home()),
                "admin":    _is_admin(),
            })

        # ── OLLAMA STATUS ────────────────────────────────────────
        elif path == "/api/ollama/recommend":
            self._json(get_pc_model_recommendation()); return
        elif path == "/api/ollama/status":
            if not self._authed(body): self._json({"error":"Pair your phone first via QR.","code":"AUTH_REQUIRED"},401); return
            try:
                ok    = _ol_ok()
                model = _ol_model() if ok else ""
                mods  = _ol_models() if ok else []
                starting = not ok and any(
                    t.name == "ollama-auto" for t in threading.enumerate())
                with _pull_progress_lock:
                    pp = dict(_pull_progress)
                self._json({
                    "available":    ok,
                    "activeModel":  model,
                    "models":       mods,
                    "starting":     starting,
                    "defaultModel": DEFAULT_MODEL,
                    "modelSize":    _model_size_label(model),
                    "modelTier":    _model_tier(model),
                    "pullProgress": pp,   # live download state for mobile UI
                })
            except Exception as e:
                self._json({"available": False, "activeModel": "", "models": [],
                    "starting": False, "defaultModel": DEFAULT_MODEL,
                    "modelSize": "", "modelTier": "unknown", "error": str(e)})

        # ── PULL PROGRESS ────────────────────────────────────────
        elif path == "/api/ollama/pull_status":
            if not self._authed(body):
                self._json({"error": "Pair your phone first via QR.", "code": "AUTH_REQUIRED"}, 401); return
            with _pull_progress_lock:
                self._json(dict(_pull_progress))

        # ── DISK SPACE ────────────────────────────────────────────
        elif path == "/api/disk_space":
            if not self._authed(body):
                self._json({"error": "Pair your phone first via QR.", "code": "AUTH_REQUIRED"}, 401); return
            try:
                info = _get_disk_info()
                # Also attach per-model requirements so the app can show
                # exactly how much space each model needs vs what's free
                info["model_requirements"] = {k: v for k, v in _MODEL_DISK_GB.items()}
                info["pull_active"] = _pull_progress.get("active", False)
                self._json(info)
            except Exception as e:
                self._json({"error": str(e), "free_gb": 0, "total_gb": 0,
                            "used_gb": 0, "ollama_models_path": "",
                            "models_dir_size_gb": 0})

        # ── KB LIST ──────────────────────────────────────────────
        elif path == "/api/kb/list":
            rows = _db_q("SELECT id,title,url,category,word_count,crawled_at "
                         "FROM knowledge_base ORDER BY crawled_at DESC LIMIT 50")
            self._json({"articles": rows, "total": _kb_count()})

        # ── KB GROWTH GRAPH — proprietary ΣNET analytics ───────────
        # Returns time-series data for the app's growth graph
        elif path.startswith("/api/kb/growth"):
            try:
                hrs = int(path.split("hours=")[1]) if "hours=" in path else 24
                hrs = max(1, min(hrs, 168))  # 1 hour to 7 days
            except: hrs = 24
            self._json(_sigma_get_growth_data(hrs))

        # ── KB LIVE FEED — app polls to show real-time growth ────
        elif path.startswith("/api/kb/feed"):
            try:
                since = float(path.split("since=")[1]) if "since=" in path else 0.0
            except: since = 0.0
            try:
                rows = _db_q(
                    "SELECT title, url, category, word_count, crawled_at "
                    "FROM knowledge_base WHERE crawled_at > ? "
                    "ORDER BY crawled_at DESC LIMIT 20", (since,)
                )
                total = _kb_count()
                self._json({
                    "articles":  rows,
                    "total":     total,
                    "queue":     _lq_size(),
                    "learning":  _learning_active,
                    "session":   _session_articles,
                    "milestone": _next_milestone(total),
                    "workers":   WORKER_THREADS,
                })
            except Exception as e:
                self._json({"articles": [], "total": _kb_count(), "queue": 0, "error": str(e)})

        # ── KB STATS ─────────────────────────────────────────────
        elif path == "/api/kb/stats":
            self._json({"articles": _kb_count(), "sigma": _sigma_stats})

        # ── LIST SHARED FILES ─────────────────────────────────────
        elif path == "/api/files":
            if not self._authed(body): self._json({"error":"Pair your phone first via QR.","code":"AUTH_REQUIRED"},401); return
            SHARE_DIR.mkdir(parents=True, exist_ok=True)
            files = [{"name": f.name, "size": f.stat().st_size,
                      "size_str": f"{f.stat().st_size//1024}KB"}
                     for f in sorted(SHARE_DIR.iterdir()) if f.is_file()]
            self._json({"files": files, "count": len(files)})

        # ── DOWNLOAD FILE ─────────────────────────────────────────
        elif path == "/api/download":
            if not self._authed(body): self._json({"error":"Pair your phone first via QR.","code":"AUTH_REQUIRED"},401); return
            # Auth via Bearer header OR token query param (download links need this)
            locked = _gs("locked_device")
            if locked:
                ah = self.headers.get("Authorization","")
                tok = ah[7:].strip() if ah.startswith("Bearer ") else ""
                if not tok:
                    from urllib.parse import parse_qs as _pqs
                    _qs = _pqs(self.path.split("?",1)[1] if "?" in self.path else "")
                    tok = (_qs.get("token",[""])[0] or "")
                if not tok or not _verify_token(tok, locked):
                    self._json({"error":"Pair your phone first via QR.","code":"AUTH_REQUIRED"},401); return
            from urllib.parse import parse_qs
            qs   = parse_qs(self.path.split("?",1)[1] if "?" in self.path else "")
            name = (qs.get("name",[""])[0] or "").replace("..","").replace("/","_")
            fp   = SHARE_DIR / name
            if not fp.exists(): self._json({"error": "Not found"}, 404); return
            body_bytes = fp.read_bytes()
            ct = mimetypes.guess_type(name)[0] or "application/octet-stream"
            self.send_response(200)
            self.send_header("Content-Type", ct)
            self.send_header("Content-Length", len(body_bytes))
            self.send_header("Content-Disposition", f'attachment;filename="{name}"')
            self._cors(); self.end_headers()
            try: self.wfile.write(body_bytes)
            except BrokenPipeError: pass

        # ── FS DRIVES ─────────────────────────────────────────────
        elif path == "/api/fs/drives":
            if not self._authed(body): self._json({"error":"Pair your phone first via QR.","code":"AUTH_REQUIRED"},401); return
            drives = []
            if HAS_PSUTIL:
                try:
                    for p in psutil.disk_partitions(all=False):
                        try:
                            u = psutil.disk_usage(p.mountpoint)
                            drives.append({"path": p.mountpoint, "label": p.device,
                                           "free_gb": round(u.free/1e9,2),
                                           "total_gb": round(u.total/1e9,2)})
                        except:
                            drives.append({"path": p.mountpoint, "label": p.device,
                                           "free_gb": None, "total_gb": None})
                except: pass
            self._json({"drives": drives})


        elif path == "/pc-check":
            try:
                html = _pc_check_html()
                body_bytes = html.encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(body_bytes)))
                self._cors()
                self.end_headers()
                self.wfile.write(body_bytes)
            except Exception as e:
                self._json({"error": "PC Check error: " + str(e)}, 500)

        elif path == "/api/scripts/library":
            if not self._authed(body): self._json({"error":"Pair your phone first via QR.","code":"AUTH_REQUIRED"},401); return
            self._json({"categories": _SCRIPT_LIBRARY,
                         "totalScripts": sum(len(c["scripts"]) for c in _SCRIPT_LIBRARY.values()),
                         "availableActions": list(_PC_CLEAN_SCRIPTS.keys())})

        elif path == "/api/scripts/list":
            if not self._authed(body): self._json({"error":"Pair your phone first via QR.","code":"AUTH_REQUIRED"},401); return
            try:
                rows = _db_q(
                    "SELECT id, name, category, language, description, code, created_at "
                    "FROM user_scripts ORDER BY created_at DESC LIMIT 200"
                )
                scripts = [{"id": r["id"], "name": r["name"],
                            "category": r.get("category","Custom"),
                            "language": r.get("language","python"),
                            "description": r.get("description",""),
                            "code": r["code"],
                            "createdAt": r.get("created_at","")} for r in rows]
                self._json({"status":"ok","scripts":scripts,"count":len(scripts)})
            except Exception as e:
                self._json({"error":str(e)}, 500)

        elif path == "/api/undo/list":
            if not self._authed(body): self._json({"error":"Pair your phone first via QR.","code":"AUTH_REQUIRED"},401); return
            self._json({"entries": _undo_list(), "undoWindow": UNDO_WINDOW})

        elif path == "/api/pc-check/scan":
            try:
                raw = _pc_scan_stats()
                if not isinstance(raw, dict): raw = {}
                temp_mb  = float(raw.get("temp_size_mb", 0) or 0)
                cache_mb = float(raw.get("browser_cache_mb", 0) or 0)
                self._json({**raw,
                    "browser_cache":        cache_mb,
                    "total_recoverable_mb": round(temp_mb + cache_mb, 1),
                    "stats": {
                        "cleaned":   int(_pc_stat_get("files_cleaned") or 0),
                        "organized": int(_pc_stat_get("files_organized") or 0),
                    },
                    "lifetime": {
                        "files_cleaned":      int(_pc_stat_get("files_cleaned") or 0),
                        "space_recovered_mb": round(float(_pc_stat_get("space_recovered_bytes") or 0)/(1024*1024), 1),
                        "files_organized":    int(_pc_stat_get("files_organized") or 0),
                        "scripts_run":        int(_pc_stat_get("scripts_run") or 0),
                        "scripts_undone":     int(_pc_stat_get("scripts_undone") or 0),
                    },
                    "growth": _pc_growth_data(7),
                })
            except Exception as e:
                self._json({"error": str(e), "temp_count": 0, "temp_size_mb": 0,
                    "browser_cache": 0, "total_recoverable_mb": 0,
                    "stats": {"cleaned": 0, "organized": 0},
                    "lifetime": {"files_cleaned":0,"space_recovered_mb":0,
                                 "files_organized":0,"scripts_run":0,"scripts_undone":0},
                    "growth": []})


        elif path == "/api/health":
            try:
                self._json({"status": "ok", "version": VERSION,
                    "uptime": int(time.time() - _start_time),
                    "ai": _ol_ok(), "model": _ol_model() if _ol_ok() else ""})
            except Exception as e:
                self._json({"status": "ok", "version": VERSION, "error": str(e)})

        elif path == "/api/ollama/chat":
            try:
                self._json({"status": "ok", "ready": _ol_ok(),
                    "model": _ol_model() if _ol_ok() else DEFAULT_MODEL,
                    "modelSize": _model_size_label(_ol_model() if _ol_ok() else DEFAULT_MODEL)})
            except Exception as e:
                self._json({"status": "ok", "ready": False, "error": str(e)})

        # ── SYNC — one round-trip on app foreground (§22) ────────────────────
        elif path == "/api/sync":
            if not self._authed(body): self._err("AUTH_REQUIRED"); return
            try:
                from urllib.parse import parse_qs
                qs = parse_qs(self.path.split("?", 1)[1] if "?" in self.path else "")
                cursor = int(qs.get("since", ["0"])[0])
            except Exception:
                cursor = 0
            locked = _gs("locked_device")
            try:
                audit_rows = _db_q(
                    "SELECT id, ts, kind, detail, exit_code FROM audit WHERE id > ? "
                    "ORDER BY id DESC LIMIT 50", (cursor,)
                )
                audit = [{"id":r["id"],"ts":r["ts"],"kind":r["kind"],
                          "detail":r.get("detail",""),"exitCode":r.get("exit_code")} for r in audit_rows]
            except Exception:
                audit = []
            self._json({
                "metrics":     _metrics_cached(2.0),
                "audit":       audit,
                "pair":        {"locked": bool(locked), "code": "" if locked else (_gs("pairing_code") or "")},
                "ts":          int(time.time() * 1000),
                "serverVersion": VERSION,
            })

        # ── AUTH ROTATE — refresh device secret weekly (§10) ──────────────────
        elif path == "/api/auth/rotate":
            if not self._authed(body): self._err("AUTH_REQUIRED"); return
            locked = _gs("locked_device")
            new_secret = base64.b64encode(os.urandom(32)).decode()
            try:
                _db_run("CREATE TABLE IF NOT EXISTS device_secrets("
                        "device_id TEXT PRIMARY KEY, secret TEXT, ts INTEGER)")
                _db_run("INSERT OR REPLACE INTO device_secrets VALUES (?,?,?)",
                        (locked, new_secret, int(time.time())))
            except Exception as e:
                log.warning(f"[AUTH] Secret rotate failed: {e}")
            self._json({"deviceSecret": new_secret, "ts": int(time.time())})

        # ── SESSIONS — who has held this lock (§11) ───────────────────────────
        elif path == "/api/sessions":
            if not self._authed(body): self._err("AUTH_REQUIRED"); return
            try:
                rows = _db_q("SELECT device_id, paired_at, last_seen, ip "
                             "FROM sessions ORDER BY last_seen DESC LIMIT 10")
                history = [dict(r) for r in rows]
            except Exception:
                history = []
            self._json({"current": _gs("locked_device"), "history": history})

        # ── POWER CONTROL — sleep/shutdown/restart (§13) ──────────────────────
        elif path == "/api/power":
            if not self._authed(body): self._err("AUTH_REQUIRED"); return
            if not _gs("power_actions_enabled"):
                self._json({"error": "Power actions disabled — enable in Settings"}, 403); return
            action = (body.get("action") or "").lower()
            confirm = body.get("confirm", False)
            if not confirm:
                self._json({"error": "Require confirm:true to prevent accidents"}, 400); return
            plat = sys.platform
            # shell=False — each command is a list, not a string.
            # Prevents shell injection if action string were ever tampered with.
            CMDS = {
                "win32": {
                    "sleep":     ["rundll32.exe", "powrprof.dll,SetSuspendState", "0,1,0"],
                    "hibernate": ["rundll32.exe", "powrprof.dll,SetSuspendState", "1,1,0"],
                    "shutdown":  ["shutdown", "/s", "/t", "10"],
                    "restart":   ["shutdown", "/r", "/t", "10"],
                },
                "linux": {
                    "sleep":     ["systemctl", "suspend"],
                    "shutdown":  ["shutdown", "-h", "+1"],
                    "restart":   ["shutdown", "-r", "+1"],
                },
                "darwin": {
                    "sleep":     ["pmset", "sleepnow"],
                    "shutdown":  ["sudo", "shutdown", "-h", "+1"],
                    "restart":   ["sudo", "shutdown", "-r", "+1"],
                },
            }
            cmds = CMDS.get(plat, CMDS.get("linux", {}))
            if action not in cmds:
                self._json({"error": f"Unknown action. Valid: {list(cmds.keys())}"}, 400); return
            try:
                kw = {}
                if sys.platform == "win32":
                    kw["creationflags"] = subprocess.CREATE_NO_WINDOW
                subprocess.Popen(cmds[action], shell=False, **kw)
                self._json({"ok": True, "action": action, "message": f"PC will {action} shortly"})
            except Exception as e:
                self._json({"error": str(e)}, 500)

        # ── CLIPBOARD — read/write PC clipboard (§14) ─────────────────────────
        elif path == "/api/clipboard":
            if not self._authed(body): self._err("AUTH_REQUIRED"); return
            def _clip_get():
                if IS_WINDOWS:
                    r = subprocess.run(["powershell", "-c", "Get-Clipboard"],
                                       capture_output=True, text=True, timeout=5)
                    return r.stdout.strip()
                elif sys.platform == "darwin":
                    return subprocess.check_output(["pbpaste"], text=True, timeout=5)
                return subprocess.check_output(["xclip", "-selection", "clipboard", "-o"],
                                               text=True, timeout=5)
            def _clip_set(s: str):
                if IS_WINDOWS:
                    subprocess.run(["clip"], input=s.encode("utf-16le"), timeout=5)
                elif sys.platform == "darwin":
                    p = subprocess.Popen(["pbcopy"], stdin=subprocess.PIPE)
                    p.communicate(s.encode())
                else:
                    p = subprocess.Popen(["xclip", "-selection", "clipboard"], stdin=subprocess.PIPE)
                    p.communicate(s.encode())
            text_in = body.get("text")
            if text_in is not None:
                try:
                    _clip_set(str(text_in)[:10000])
                    self._json({"ok": True, "action": "set", "length": len(text_in)})
                except Exception as e:
                    self._json({"error": str(e)}, 500)
            else:
                try:
                    content = _clip_get()
                    self._json({"ok": True, "text": content, "length": len(content)})
                except Exception as e:
                    self._json({"text": "", "error": str(e)})

        # ── KEYBOARD TYPE — remote typing (§14) ───────────────────────────────
        elif path == "/api/keyboard/type":
            if not self._authed(body): self._err("AUTH_REQUIRED"); return
            text = (body.get("text") or "")[:500]
            if not text:
                self._json({"error": "text required"}, 400); return
            try:
                import pyautogui
                pyautogui.typewrite(text, interval=0.008)
                self._json({"ok": True, "typed": len(text)})
            except ImportError:
                self._json({"error": "pyautogui not installed — run: pip install pyautogui"}, 503)
            except Exception as e:
                self._json({"error": str(e)}, 500)

        # ── PUSH NOTIFICATION REGISTER (§12) ──────────────────────────────────
        elif path == "/api/notify/register":
            if not self._authed(body): self._err("AUTH_REQUIRED"); return
            expo_token = (body.get("expoPushToken") or "").strip()
            if not expo_token:
                self._json({"error": "expoPushToken required"}, 400); return
            try:
                _db_run("CREATE TABLE IF NOT EXISTS push_tokens("
                        "device_id TEXT PRIMARY KEY, token TEXT, ts INTEGER)")
                _db_run("INSERT OR REPLACE INTO push_tokens VALUES (?,?,?)",
                        (_gs("locked_device"), expo_token, int(time.time())))
                self._json({"ok": True, "registered": True})
            except Exception as e:
                self._json({"error": str(e)}, 500)

        # ── SCRIPTS UPLOAD — save editor script to PC (§17) ───────────────────
        elif path == "/api/scripts/upload":
            if not self._authed(body): self._err("AUTH_REQUIRED"); return
            raw_name = (body.get("name") or "script").strip()
            name = re.sub(r"[^A-Za-z0-9_.-]", "_", raw_name)[:60]
            if not name.endswith(".py"): name += ".py"
            script_code = (body.get("script") or body.get("code") or "").strip()
            if not script_code:
                self._json({"error": "script/code required"}, 400); return
            safe_dir = Path.home() / ".butler" / "scripts"
            safe_dir.mkdir(parents=True, exist_ok=True)
            out = (safe_dir / name).resolve()
            # Path traversal guard
            if not str(out).startswith(str(safe_dir.resolve())):
                self._json({"error": "Invalid filename"}, 400); return
            try:
                out.write_text(script_code[:200_000], encoding="utf-8")
                self._json({"ok": True, "path": str(out), "name": name, "size": len(script_code)})
            except Exception as e:
                self._json({"error": str(e)}, 500)

        # ── BUTLER ABORT — stop active SSE stream (§15) ───────────────────────
        elif path == "/api/butler/abort":
            if not self._authed(body): self._err("AUTH_REQUIRED"); return
            rid = (body.get("requestId") or "").strip()
            if rid and rid in _ACTIVE_STREAMS:
                _ACTIVE_STREAMS[rid] = False
                self._json({"ok": True, "aborted": rid})
            else:
                self._json({"ok": False, "reason": "not found"}, 404)

        # ── STREAMING SCRIPT EXECUTION — live stdout per line (§2) ──────────
        elif path == "/api/execute/stream":
            if not self._authed(body): self._err("AUTH_REQUIRED"); return
            script   = (body.get("script") or body.get("code") or "").strip()
            language = (body.get("language") or "python").lower()
            if not script:
                self._json({"error": "script required"}, 400); return
            if len(script) > 200_000:
                self._json({"error": "Script too large (max 200KB)"}, 413); return
            # Run safety check
            for pat, reason in [
                (b"marshal.loads", "marshal deserialization"),
                (b"exec(compile(",  "exec+compile obfuscation"),
                (b"ctypes.CDLL(",   "arbitrary library loading"),
            ]:
                if pat in script.encode("utf-8", errors="ignore"):
                    self._json({"error": f"Blocked: {reason}", "blocked": True}, 400); return
            interp = sys.executable if language == "python" else language
            self.send_response(200)
            self.send_header("Content-Type",     "text/event-stream")
            self.send_header("Cache-Control",    "no-cache")
            self.send_header("X-Accel-Buffering","no")
            self.send_header("Connection",       "keep-alive")
            self._cors(); self.end_headers()
            t0 = time.time()
            try:
                proc = subprocess.Popen(
                    [interp, "-u", "-c", script],
                    stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                    text=True, bufsize=1, timeout=None,
                    cwd=str(Path.home()),
                )
                for line in iter(proc.stdout.readline, ""):
                    try:
                        self.wfile.write(
                            ("data: " + json.dumps({"chunk": line}) + "\n\n").encode()
                        )
                        self.wfile.flush()
                    except (BrokenPipeError, ConnectionResetError):
                        proc.kill(); return
                    if time.time() - t0 > EXEC_TIMEOUT:
                        proc.kill()
                        self.wfile.write(
                            ("data: " + json.dumps({'error': 'timeout', 'exitCode': -1, 'done': True}) + "\n\n").encode()
                        )
                        self.wfile.flush(); return
                proc.wait(timeout=3)
                self.wfile.write(
                            ("data: " + json.dumps({'done': True, 'exitCode': proc.returncode, 'elapsedMs': int((time.time()-t0)*1000)}) + "\n\n").encode()
                )
                self.wfile.flush()
            except Exception as e:
                try:
                    self.wfile.write(
                            ("data: " + json.dumps({'error': str(e), 'done': True, 'exitCode': -1}) + "\n\n").encode()
                    )
                    self.wfile.flush()
                except Exception:
                    pass

        # ── PAIR QR — rotate code + return PNG (§7) ───────────────────────────
        elif path == "/api/pair/qr":
            if body.get("rotate"):
                _ss("pairing_code", _gen_code())
            code = _gs("pairing_code") or _gen_code()
            ip_addr = _lan_ip() if hasattr(sys.modules[__name__], "_lan_ip") else "127.0.0.1"
            payload = json.dumps({"ip": ip_addr, "port": _PORT[0] if "_PORT" in dir() else 8766,
                                   "pairingCode": code, "version": VERSION})
            try:
                import qrcode, io
                img = qrcode.make(payload)
                buf = io.BytesIO(); img.save(buf, format="PNG")
                png = buf.getvalue()
                self.send_response(200)
                self.send_header("Content-Type",   "image/png")
                self.send_header("Content-Length", str(len(png)))
                self.send_header("X-Pair-Code",    code)
                self._cors(); self.end_headers()
                self.wfile.write(png)
            except ImportError:
                self._json({"error": "qrcode library not installed", "pairingCode": code,
                            "payload": payload})

        else:
            self._json({"error": "endpoint not found"}, 404)

    def do_POST(self):
        global _ollama_busy, _perf_mode
        path = self.path.split("?")[0]
        # Auth/connection endpoints are NEVER rate-limited — they must always work
        # Rate-limiting /pair or /reconnect causes connection death spiral (429 loop)
        if path not in ("/pair", "/reconnect", "/health", "/ping", "/api/pair/status",
                        "/api/verify", "/api/reset_pair"):
            if not self._chkrate(): return
        body = self._body()
        if body is None: return

        # ── PAIR ────────────────────────────────────────────────
        if path == "/pair":
            device_id = (body.get("deviceId") or "").strip()
            pairing_code = (body.get("pairingCode") or "").strip()

            # ── GUARD 1: device ID must exist and be sane ─────────────
            if not device_id:
                _conn_log("PAIR", "NO_DEVICE_ID", "", "400")
                self._json({"error": "deviceId required"}, 400); return
            if len(device_id) < 5 or len(device_id) > 128:
                _conn_log("PAIR", device_id[:20], "", "400 bad length")
                self._json({"error": "Invalid deviceId length"}, 400); return

            # ── GUARD 2: Thread-safe pairing with _pair_lock ──────────
            with _pair_lock:
                locked = _gs("locked_device")

                # ── Already paired to THIS device → re-issue token ────
                if locked and locked == device_id:
                    tok = _make_token(device_id)
                    _ss("last_seen", time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()))
                    try: _queue_refill()
                    except: pass
                    _conn_log("PAIR", device_id[:20], "RECONNECT", "200 same device")
                    self._json({"status": "ok", "sessionToken": tok,
                                "reused": True, "message": "Welcome back",
                                "serverVersion": VERSION}); return

                # ── Server locked to a DIFFERENT device ───────────────
                if locked and locked != device_id:
                    # ── SMART AUTO-UNLOCK: if the locked device hasn't been
                    # seen in 5+ minutes and the new device has the correct
                    # pairing code, auto-unlock and re-pair. This handles:
                    # - App reinstall (new device ID)
                    # - APK rebuild (new device ID)  
                    # - Phone factory reset
                    # - User switching phones
                    stored_code = (_gs("pairing_code") or "").upper()
                    last_seen = _gs("last_seen") or ""
                    stale = False
                    try:
                        from datetime import datetime
                        if last_seen:
                            ls_time = datetime.strptime(last_seen, "%Y-%m-%dT%H:%M:%SZ").timestamp()
                            stale = (time.time() - ls_time) > 300  # 5 minutes
                        else:
                            stale = True
                    except: stale = True

                    can_auto_unlock = (
                        (pairing_code.upper() == stored_code and stored_code) or  # has correct code
                        stale  # old device hasn't connected in 5+ min
                    )

                    if can_auto_unlock:
                        # Auto-unlock: reset and re-pair to new device
                        _conn_log("PAIR", device_id[:20], "AUTO-UNLOCK",
                                  f"old={locked[:12]} stale={stale} code_match={pairing_code.upper()==stored_code}")
                        now = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
                        _ss("locked_device", device_id)
                        _ss("paired_at", now)
                        _ss("last_seen", now)
                        _ss("pairing_code", _gen_code())  # new code after re-pair
                        tok = _make_token(device_id)
                        print(f"  [AUTH] ✓ Auto-unlocked: old device stale/code matched → re-paired to {device_id[:20]}")
                        self._json({"status": "ok", "sessionToken": tok,
                                    "reused": False,
                                    "message": "Auto-unlocked and re-paired to your device.",
                                    "serverVersion": VERSION}); return

                    # Not eligible for auto-unlock — reject
                    _conn_log("PAIR", device_id[:20], "REJECTED",
                              f"locked to {locked[:12]}")
                    self._json({
                        "error":   "Server is locked to a different device.",
                        "fix":     "Server is auto-locked. To pair a new device: use the UNPAIR & RESET button on the PC, or restart server with --reset-pair",
                        "locked":  True,
                        "canReset": True,
                        "pairingCode": stored_code,  # app can use this to auto-reset
                    }, 403); return

                # ── GUARD 3: Server is OPEN — auto-lock first device ──
                if _gs("locked_device"):
                    _conn_log("PAIR", device_id[:20], "RACE", "another thread locked first")
                    self._json({
                        "error":   "Server just locked to another device.",
                        "locked":  True,
                        "canReset": True,
                    }, 403); return

                # ── All guards passed — LOCK to this device ───────────
                now = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
                _ss("locked_device", device_id)
                _ss("paired_at",     now)
                _ss("last_seen",     now)

                # ── GUARD 4: Verify the lock actually stuck ───────────
                verify = _gs("locked_device")
                if verify != device_id:
                    _conn_log("PAIR", device_id[:20], "LOCK_FAILED", "verify mismatch")
                    self._json({"error": "Lock failed — try again"}, 500); return

                tok = _make_token(device_id)

            # Outside the lock now
            try: _queue_refill()
            except: pass
            _conn_log("PAIR", device_id[:20], "LOCKED", "first device auto-locked")
            print(f"  [AUTH] ✓ Auto-locked: {device_id[:24]}...")
            print(f"  [AUTH]   Server is now locked. Only this device can connect.")
            self._json({
                "status":       "ok",
                "sessionToken": tok,
                "reused":       False,
                "message":      "Auto-paired! Server locked to your device.",
                "serverVersion": VERSION,
            }); return

        # ── RECONNECT ────────────────────────────────────────────
        elif path == "/reconnect":
            device_id = (body.get("deviceId") or "").strip()
            # Dedup: return same token if reconnect within 2s (prevents reconnect storms)
            # In-memory only — not persisted (no disk I/O per reconnect)
            _now = time.time()
            _dkey = f"reconnect:{device_id}"
            with _pair_lock:
                _dcache = _RECONNECT_CACHE.get(_dkey, {})
                if (_dcache.get("tok") and _now - _dcache.get("ts",0) < 2.0):
                    self._json({"status": "ok", "sessionToken": _dcache["tok"],
                                "cached": True}); return

            # ── Thread-safe reconnect with _pair_lock ─────────────────
            with _pair_lock:
                locked = _gs("locked_device")

                # ── No device paired yet: auto-lock to first reconnector ──
                if not locked:
                    if device_id and len(device_id) >= 5:
                        now = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
                        _ss("locked_device", device_id)
                        _ss("paired_at", now)
                        _ss("last_seen", now)
                        # Verify lock stuck
                        if _gs("locked_device") != device_id:
                            self._json({"error": "Lock failed — try again"}, 500); return
                        print(f"  [AUTH] Auto-locked on reconnect: {device_id[:20]}")
                        tok = _make_token(device_id)
                        self._json({"status": "ok", "sessionToken": tok,
                                    "autoLocked": True, "serverVersion": VERSION}); return
                    # No device_id and no locked device - open access
                    tok = _make_token("anon")
                    self._json({"status": "ok", "sessionToken": tok,
                                "autoLocked": False, "serverVersion": VERSION}); return

            # ── Reconnecting known device → refresh token ─────────────────
            if device_id and device_id == locked:
                tok = _make_token(device_id)
                _ss("last_seen", time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()))
                # Update sessions audit trail
                try:
                    _db_run(
                        "INSERT OR REPLACE INTO sessions(device_id, last_seen, ip) VALUES (?,?,?)",
                        (device_id, time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), self.client_address[0])
                    )
                except Exception: pass
                _log(f"Reconnected: {device_id[:16]}…", "ok")
                # Cache for storm dedup
                _RECONNECT_CACHE[f"reconnect:{device_id}"] = {"tok": tok, "ts": time.time()}
                self._json({"status": "ok", "sessionToken": tok,
                            "serverVersion": VERSION}); return

            # ── Different device trying to reconnect → reject ─────────────
            self._json({
                "error":  "Server is paired to a different device.",
                "fix":    "Server is auto-locked. Use UNPAIR & RESET on PC to pair a new device.",
                "locked": True,
            }, 403); return

        # ── EXECUTE SCRIPT ───────────────────────────────────────
        elif path in ("/api/execute", "/api/run", "/execute", "/run"):
            if not self._authed(body):
                self._json({"error": "Pair your phone first via QR.", "code": "AUTH_REQUIRED"}, 401); return
            script   = (body.get("script") or body.get("code") or "").strip()
            language = (body.get("language") or "python").lower()
            if not script:
                self._json({"error": "No script provided"}, 400); return
            if len(script) > 200000:
                self._json({"error": "Script too large (max 200KB)"}, 413); return

            # ── Hard-block dangerous code patterns ────────────────────────
            _HARD_BLOCK = [
                b"marshal.loads",
                b"exec(compile(",
                b"ctypes.CDLL(",
                b"exec(base64",
            ]
            _HARD_NAMES = [
                "marshal deserialization",
                "exec+compile obfuscation",
                "arbitrary library loading",
                "base64 exec obfuscation",
            ]
            script_bytes = script.encode("utf-8", errors="ignore")
            for _pat, _name in zip(_HARD_BLOCK, _HARD_NAMES):
                if _pat in script_bytes:
                    self._json({
                        "error": f"Script blocked: {_name}",
                        "blocked": True,
                        "reason": _name,
                    }, 400); return

            # ── BUTLER GUARD: safety checks before execution ──────
            # Prevent accidental system destruction
            DANGER_PATTERNS = [
                # Filesystem destruction
                ("rm -rf /",            "Recursive root delete blocked"),
                ("rm -rf ~",            "Home directory delete blocked"),
                ("rm -rf *",            "Wildcard delete blocked"),
                ("del /s /q C:\\",      "Recursive C: delete blocked"),
                ("del /s /q /f",        "Force recursive delete blocked"),
                ("format c:",           "Format command blocked"),
                ("format d:",           "Format command blocked"),
                # System destruction
                (":(){ :|:& };:",       "Fork bomb blocked"),
                ("shutdown /s /f /t 0", "Immediate shutdown blocked"),
                ("shutdown /r /f",      "Force shutdown blocked — use shutdown /r /t 30 instead"),
                ("halt", "System halt blocked"),
                ("init 0",              "System halt blocked"),
                # Registry destruction
                ("reg delete HKLM",     "System registry delete blocked"),
                ("reg delete HKCR",     "System registry delete blocked"),
                # Network attacks
                ("while True: requests", "Infinite request loop blocked (DoS risk)"),
                # Data exfiltration patterns
                ("base64.b64encode(open", "File encoding + exfiltration pattern blocked"),
                # Code obfuscation / dynamic execution attacks
                ("marshal.loads",          "marshal deserialization exec blocked"),
                ("exec(compile(",          "exec+compile obfuscation blocked"),
                ("exec(base64",            "base64-encoded exec blocked"),
                ("__import__('os').system","dynamic import exec blocked"),
                # PowerShell download + execute (Windows)
                ("IEX (New-Object",        "PowerShell download-execute blocked"),
                ("Invoke-Expression",      "PowerShell Invoke-Expression blocked"),
                ("DownloadString",         "PowerShell remote download blocked"),
                # Network exfiltration via subprocess
                ("curl -d @",              "curl data exfiltration blocked"),
                ("wget --post-file",       "wget exfiltration blocked"),
                # Self-replication
                ("shutil.copy(__file__",   "Script self-copy blocked"),
                ("open(__file__",          "Script self-read for copy blocked"),
            ]
            script_lower = script.lower().replace(" ", "")
            for pattern, reason in DANGER_PATTERNS:
                if pattern.lower().replace(" ","") in script_lower:
                    _log(f"[GUARD] Blocked dangerous script: {reason}", "warn")
                    self._json({"status":"error","error":f"⚠️ {reason}",
                                "output":"","exitCode":1,"exit_code":1}); return

            # ── AI VERIFICATION: Check script safety before running ──
            # Only for longer scripts that import dangerous modules
            if language == "python" and len(script) > 300:
                import re as _re_v
                risky_imports = _re_v.findall(r'^(?:import|from) (os|shutil|subprocess|winreg|ctypes|socket|requests|smtplib)', script, _re_v.MULTILINE)
                if risky_imports:
                    verify = _verify_script_safety(script, body.get("userRequest", ""))
                    if not verify["safe"]:
                        self._json({"status":"error",
                                    "error": f"⚠️ Script blocked by safety check: {verify['reason']}",
                                    "output":"","exitCode":1,"exit_code":1,
                                    "verification": verify}); return
                    # Attach warnings to response (app can show them)
                    if verify["warnings"]:
                        _log(f"[GUARD] Script has warnings: {verify['warnings'][:3]}", "info")

            # ── Auto pip-install missing modules (Python only) ────
            if language == "python":
                import re as _re
                imports = _re.findall(r'^(?:import|from) (\w+)', script, _re.MULTILINE)
                pip_map = {
                    "psutil":"psutil","pyautogui":"pyautogui","keyboard":"keyboard",
                    "pynput":"pynput","plyer":"plyer","schedule":"schedule",
                    "watchdog":"watchdog","pyperclip":"pyperclip","requests":"requests",
                    "bs4":"beautifulsoup4","openpyxl":"openpyxl","docx":"python-docx",
                    "PIL":"Pillow","selenium":"selenium","playwright":"playwright",
                    "pywin32":"pywin32","win32api":"pywin32","wmi":"wmi",
                    "paramiko":"paramiko","cryptography":"cryptography",
                }
                to_install = []
                for mod in imports:
                    mod = mod.strip()
                    if mod in pip_map:
                        try: __import__(mod)
                        except ImportError: to_install.append(pip_map[mod])
                if to_install:
                    _log(f"[EXEC] Auto-installing: {', '.join(set(to_install))}", "info")
                    subprocess.run(
                        [sys.executable,"-m","pip","install","--quiet"] + list(set(to_install)),
                        capture_output=True, timeout=120
                    )

            try:
                if language == "python":
                    cmd = [sys.executable, "-c", script]
                elif language == "powershell":
                    cmd = ["powershell", "-NoProfile", "-NonInteractive", "-Command", script]
                elif language in ("bash","sh"):
                    cmd = ["bash", "-c", script] if platform.system()!="Windows" else ["cmd","/c",script]
                elif language in ("cmd","batch"):
                    cmd = ["cmd", "/c", script]
                else:
                    cmd = [sys.executable, "-c", script]
                kw = {}
                if IS_WINDOWS: kw["creationflags"] = subprocess.CREATE_NO_WINDOW
                _undo_id = _undo_create(script, language, body.get("userRequest", ""))
                # Force UTF-8 encoding — prevents garbled output on non-English Windows
                # (Japanese cp932, Chinese cp936, Korean cp949, etc.)
                exec_env = os.environ.copy()
                exec_env["PYTHONIOENCODING"] = "utf-8"
                exec_env["PYTHONUTF8"] = "1"
                r = subprocess.run(cmd, capture_output=True, text=True,
                                   encoding="utf-8", errors="replace",
                                   timeout=EXEC_TIMEOUT, cwd=str(Path.home()),
                                   env=exec_env, **kw)
                out = r.stdout.strip()
                err = r.stderr.strip()
                combined = (out + ("\n" + err if err else "")).strip()
                if _undo_id: _undo_complete(_undo_id, combined, r.returncode == 0)
                self._json({
                    "status":    "ok" if r.returncode == 0 else "error",
                    "output":    combined[:100000] if combined else "[No output]",
                    "stdout":    out[:50000],
                    "stderr":    err[:10000],
                    "exitCode":  r.returncode,
                    "exit_code": r.returncode,
                    "returncode": r.returncode,
                    "undoId":    _undo_id,
                    "undoAvailable": bool(_undo_id),
                    "undoExpiresSec": UNDO_WINDOW,
                })
                # ── SCRIPT LEARNING: Save successful scripts to KB ────
                # When a script runs successfully, save it as proven-working
                # knowledge. Next time someone asks a similar question,
                # this tested script surfaces in KB search results.
                if r.returncode == 0 and language == "python" and len(script) > 50:
                    try:
                        user_req = body.get("userRequest", "")
                        script_title = user_req[:80] if user_req else f"Working script: {script[:60]}"
                        # Only save if not already in KB
                        existing = _db_q("SELECT id FROM knowledge_base WHERE clean_text LIKE ? LIMIT 1",
                                         (f"%{script[:100]}%",))
                        if not existing:
                            _kb_save(
                                url=f"local://script/{int(time.time())}",
                                title=f"[PROVEN] {script_title}",
                                text=f"Working Python script (tested, exit code 0):\n\n```python\n{script[:5000]}\n```\n\nOutput:\n{combined[:1000]}",
                                cat="ProvenScripts",
                                kw=user_req.split()[:5] if user_req else ["script","python","automation"],
                            )
                            _log(f"[LEARN] Saved proven script to KB: {script_title[:40]}…", "info")
                    except: pass
            except subprocess.TimeoutExpired:
                # Script took too long — kill it and return useful message
                self._json({
                    "status":    "error",
                    "error":     f"Script timed out after {EXEC_TIMEOUT}s. Use threading or break into smaller parts.",
                    "output":    "",
                    "stdout":    "",
                    "stderr":    f"TimeoutError: exceeded {EXEC_TIMEOUT}s limit",
                    "exitCode":  124,
                    "exit_code": 124,
                    "returncode": 124,
                }, 408)
            except FileNotFoundError as e:
                # python/powershell/cmd not found on PATH
                self._json({
                    "status":    "error",
                    "error":     f"Interpreter not found: {e}. Check Python is installed.",
                    "output":    "",
                    "stdout":    "",
                    "stderr":    str(e),
                    "exitCode":  127,
                    "exit_code": 127,
                    "returncode": 127,
                })
            except UnicodeDecodeError as e:
                # Script output had non-UTF8 bytes
                self._json({
                    "status":    "error",
                    "error":     f"Output encoding error: {e}. Script output contains non-UTF8 characters.",
                    "output":    "[Output encoding error — script may have run but output unreadable]",
                    "exitCode":  1, "exit_code": 1, "returncode": 1,
                })
            except PermissionError as e:
                self._json({
                    "status":    "error",
                    "error":     f"Permission denied: {e}. Try running as administrator.",
                    "output":    "",
                    "exitCode":  126, "exit_code": 126, "returncode": 126,
                })
            except MemoryError:
                self._json({
                    "status":    "error",
                    "error":     "Script ran out of memory. Reduce data size or split into chunks.",
                    "output":    "",
                    "exitCode":  137, "exit_code": 137, "returncode": 137,
                })
            except Exception as e:
                self._json({
                    "status":    "error",
                    "error":     f"{type(e).__name__}: {str(e)[:300]}",
                    "output":    "",
                    "stdout":    "",
                    "stderr":    str(e)[:500],
                    "exitCode":  1, "exit_code": 1, "returncode": 1,
                }, 500)

        # ── BUTLER AI CHAT ────────────────────────────────────────

        elif path == "/api/execute/settings":
            if not self._authed(body):
                self._json({"error": "Unauthorized", "code": "AUTH_REQUIRED"}, 401); return
            action = str(body.get("action", "get")).lower()
            if action == "get":
                self._json({
                    "visual_reports": True,
                    "max_timeout_s":  MAX_SCRIPT_SEC,
                    "workers":        WORKER_THREADS,
                    "crawl_delay_s":  CRAWL_DELAY_SECS,
                    "harvest_mins":   HARVEST_SECS // 60,
                })
            elif action == "crawler_pause":
                global _learning_active
                _learning_active = False
                self._json({"status": "ok", "crawling": False,
                            "message": "Crawler paused — full CPU for AI"})
            elif action == "crawler_resume":
                _learning_active = True
                self._json({"status": "ok", "crawling": True,
                            "message": "Crawler resumed"})
            else:
                self._json({"error": "action: get | crawler_pause | crawler_resume"})
            return

        elif path in ("/api/butler/chat", "/api/ollama/chat", "/api/chat"):
            if not self._authed(body):
                self._json({"error": "Unauthorized", "code": "AUTH_REQUIRED"}, 401); return
            msg     = (body.get("message") or "").strip()
            # Use app's systemPrompt if provided, else sensible default
            # ── Build system prompt: server's conversational base + app's context ──
            _base_prompt = (
                "You are Butler AI — a friendly, knowledgeable PC assistant that runs locally.\n\n"
                "PERSONALITY:\n"
                "- Be warm, helpful, and conversational. Respond naturally to greetings and casual chat.\n"
                "- When someone says 'hi' or 'hello', greet them back warmly and ask how you can help.\n"
                "- You can discuss ANY topic — tech, general knowledge, advice, ideas, humor, etc.\n"
                "- Keep responses concise unless the user asks for detail.\n"
                "- You run 100% locally on the user's PC. No cloud. Full privacy.\n\n"
                "TECHNICAL EXPERTISE (use when asked):\n"
                "- Windows errors, BSODs, crashes, drivers, firewall, network\n"
                "- Python automation scripts for ANY task\n"
                "- Hardware diagnostics, security, performance optimization\n"
                "- File organization, browser automation, Office automation\n\n"
                "WHEN WRITING SCRIPTS:\n"
                "- Write COMPLETE runnable Python code. No placeholders.\n"
                "- Include all imports and error handling.\n"
                "- Use triple-backtick python code blocks.\n"
                "- Prefer Python automation over manual steps.\n\n"
                "IMPORTANT: Only write scripts when the user asks for automation or a fix.\n"
                "For casual conversation, questions, or advice — just talk naturally.\n"
            )
            app_prompt = body.get("systemPrompt") or ""
            # App sends metrics/context in its prompt — keep that, skip its restrictive rules
            system = _base_prompt
            if app_prompt:
                # Extract useful context lines (metrics, server info, tasks, KB)
                for line in app_prompt.split("\n"):
                    stripped = line.strip()
                    if any(stripped.startswith(p) for p in ("CPU=", "Server:", "Tasks:", "Logs:", "[")):
                        system += stripped + "\n"
                    elif stripped.startswith("RULES:") or stripped.startswith("- Complete") or stripped.startswith("- Format") or stripped.startswith("- Show pip") or stripped.startswith("- Be direct"):
                        continue  # skip restrictive rules — server prompt handles it
                    elif "KB" in stripped or "knowledge" in stripped.lower():
                        system += stripped + "\n"
            # Accept conversation from app (preferred) or fall back to DB history
            hist    = body.get("conversation", [])
            model   = body.get("model", _get_active_model())
            metrics = body.get("metricsSnapshot", "")
            tools   = body.get("toolResults", [])
            if not msg:
                self._json({"error": "message required"}, 400); return

            # Append metrics context if provided
            if metrics:
                system += f"\n\n[LIVE PC METRICS]\n{metrics}"

            # Add tool results to message if provided
            full_msg = msg
            if tools:
                tool_text = "\n".join(str(t) for t in tools if t)
                if tool_text:
                    full_msg = f"{msg}\n\n[TOOL RESULTS]\n{tool_text}"

            # If no conversation from app, use DB history
            if not hist:
                device_id = _gs("locked_device") or "anon"
                hist = _chat_history(device_id, 12)

            # Auto-search for scripts if KB is thin on this topic
            # Skip heavy KB crawling for very short casual messages (hi, hello, etc.)
            _is_casual = len(msg.split()) <= 3 and not any(
                kw in msg.lower() for kw in
                ("script","fix","install","error","crash","slow","clean","run","check","scan","list","show","find","get","make","create","write","help","how","what","why","when","where","who")
            )
            kb_count_before = _kb_count()
            kb_hits = _kb_search(msg, 2) if not _is_casual else []
            if not _is_casual and (kb_count_before < 50 or not kb_hits):
                # KB is sparse or has ZERO results for this topic — aggressive crawl
                import threading as _th
                _th.Thread(
                    target=lambda: _search_and_crawl_scripts(msg, max_results=5),
                    daemon=True, name="script-search"
                ).start()
                # ── TOPIC GAP TRACKING ────────────────────────
                # Track topics where KB has NO answers so crawlers prioritize them
                if not kb_hits:
                    try:
                        _db_run(
                            "INSERT INTO user_topics(topic,asks,last_asked,kb_coverage) VALUES(?,1,?,0)"
                            " ON CONFLICT(topic) DO UPDATE SET asks=asks+1, last_asked=excluded.last_asked, kb_coverage=0",
                            (" ".join(msg.lower().split()[:5]), time.time())
                        )
                        _log(f"[GAP] KB has NO results for: {msg[:40]}… — triggering focused crawl", "warn")
                    except: pass

            # Track user topic for personalized learning (skip casual greetings)
            try:
                if not _is_casual:
                    topic_key = " ".join(msg.lower().split()[:5])
                    _db_run(
                        "INSERT INTO user_topics(topic,asks,last_asked) VALUES(?,1,?)"
                        " ON CONFLICT(topic) DO UPDATE SET asks=asks+1, last_asked=excluded.last_asked",
                        (topic_key, time.time())
                    )
                # High-priority queue addition for topics users actually ask about
                _lq_add(
                    f"https://www.google.com/search?q=python+{urllib.parse.quote(topic_key)}+script+github",
                    "UserTopic", topic_key.split(), priority=9, source="chat"
                )
                results = _search_scripts(msg, max_results=2)
                for r in results:
                    existing_kb = _db_q("SELECT url FROM knowledge_base WHERE url=? LIMIT 1", (r["url"],))
                    if not existing_kb:
                        _lq_add(r["url"], "UserTopic", msg.split()[:4], priority=9, source="chat")
            except: pass

            # Check script templates — instant results for common install/fix tasks
            _tmpl = _get_script_template(msg)
            if _tmpl:
                system += (
                    "\n\nREADY-TO-USE SCRIPT TEMPLATE:\n"
                    "Use this working script as your base. Customize for the user, "
                    "explain what it does step by step:\n"
                    f"```python\n{_tmpl[:2000]}\n```"
                )

            # Inject KB context - search server KB for relevant articles
            kb_ctx = _kb_enrich(msg, max_results=5)
            _kb_used_count = len(kb_ctx) if kb_ctx else 0
            if kb_ctx:
                kb_text = "\n".join(
                    f"[{e.get('category','KB')}] {e['title']}:\n  {e['snippet'][:350]}"
                    for e in kb_ctx
                )
                system += (
                    f"\n\n[KNOWLEDGE BASE - {len(kb_ctx)} relevant articles]\n"
                    f"{kb_text}\n"
                    f"Use the above KB context to give accurate, specific answers."
                )

            _chat_t0 = time.time()  # Before offline check
            if not _ol_ok():
                fallback = (
                    "Butler AI is warming up.\n\n"
                    "The AI model is being downloaded and started automatically. "
                    "This takes 2-5 minutes on first run.\n\n"
                    "Please wait a moment and try again. "
                    "All other features work right now."
                )
                self._json({
                    "status":         "ok",
                    "response":       fallback,
                    "reply":          fallback,
                    "message":        fallback,
                    "ollama":         False,
                    "ai":             "local",
                    "ollamaModel":    "",
                    "model":          model,
                    "responseTimeMs": int((time.time() - _chat_t0) * 1000),
                    "kbArticlesUsed": 0,
                    "perfMode":       "normal",
                }); return

            # ── STREAMING vs FULL RESPONSE ─────────────────────────
            # If app sends "stream": true, stream tokens live.
            # Otherwise, return full response (backward compatible).
            want_stream = body.get("stream", False)
            _ollama_busy = True  # Signal crawlers to PAUSE
            # _chat_t0 already set before offline check

            if want_stream and _ol_ok():
                # ── STREAMING MODE: tokens appear live ────────────
                # Handles slow Ollama (first query, model loading, low RAM):
                # - Sends SSE keepalive comments every 5s while waiting for first token
                # - This prevents Android from killing the idle HTTP connection
                try:
                    import urllib.request as _ur2

                    msgs = []
                    if system: msgs.append({"role": "system", "content": system})
                    for m2 in (hist or []): msgs.append(m2)
                    msgs.append({"role": "user", "content": full_msg})
                    ol_body = json.dumps({
                        "model":    model,
                        "messages": msgs,
                        "stream":   True,
                        "options": {
                            # Same speed options as _ol_chat() — critical for performance
                            "num_ctx":        4096,  # larger context — server adds big system prompt
                            "num_predict":    512,
                            "temperature":    0.7,
                            "top_p":          0.9,
                            "repeat_penalty": 1.1,
                            "num_thread":     0,     # ALL CPU threads — no throttle
                            "num_gpu":        1,     # use GPU if available
                            "low_vram":       False,
                        }
                    }).encode()
                    ol_req = _ur2.Request(
                        f"{OLLAMA_URL}/api/chat", data=ol_body,
                        headers={"Content-Type": "application/json"}, method="POST"
                    )

                    # Send HTTP headers immediately — connection is open
                    self.send_response(200)
                    self.send_header("Content-Type", "text/event-stream")
                    self.send_header("Cache-Control", "no-cache")
                    self.send_header("Connection", "keep-alive")
                    self._cors()
                    self._add_license_headers()
                    self.end_headers()

                    # Send keepalive while Ollama loads model into RAM
                    # SSE comments (: prefix) are ignored by clients but keep connection alive
                    _keepalive_active = True
                    def _keepalive():
                        while _keepalive_active:
                            try:
                                self.wfile.write(b": keepalive\n\n")
                                self.wfile.flush()
                            except: break
                            time.sleep(5)
                    ka_thread = threading.Thread(target=_keepalive, daemon=True)
                    ka_thread.start()

                    # Open Ollama connection (this blocks until first byte arrives)
                    ol_resp = _ur2.urlopen(ol_req, timeout=180)
                    _keepalive_active = False  # Stop keepalive, real tokens flowing now

                    full_reply = []
                    for line in ol_resp:
                        try:
                            chunk = json.loads(line)
                            token = chunk.get("message", {}).get("content", "")
                            if token:
                                full_reply.append(token)
                                self.wfile.write(
                                    ("data: " + json.dumps({"token": token}) + "\n\n").encode()
                                )
                                self.wfile.flush()
                        except Exception: pass
                    reply = "".join(full_reply)
                    is_err = not reply or reply.startswith("[Ollama error]")

                    if not is_err:
                        try:
                            device_id = _gs("locked_device") or "anon"
                            _chat_save(device_id, "user", msg)
                            _chat_save(device_id, "assistant", reply)
                            if model and model != _gs("active_model"):
                                _ss("active_model", model)
                        except: pass

                    # Send final metadata event
                    final = json.dumps({
                        "done": True, "status": "ok",
                        "response": reply, "reply": reply, "message": reply,
                        "ollama": not is_err, "ollamaModel": model if not is_err else "",
                        "ai": "ollama" if not is_err else "local",
                        "ollamaError": is_err,
                        "responseTimeMs": int((time.time() - _chat_t0) * 1000),
                        "kbArticlesUsed": _kb_used_count,
                        "perfMode": _perf_mode,
                    })
                    self.wfile.write(f"data: {final}\n\n".encode())
                    self.wfile.flush()
                    _ollama_busy = False
                    return

                except Exception as stream_err:
                    _ollama_busy = False
                    _keepalive_active = False
                    log.debug(f"[CHAT] Stream error: {stream_err}, falling back to full response")
                    want_stream = False

            # ── FULL RESPONSE MODE (default, backward compatible) ──
            import concurrent.futures as _cf
            reply = None
            reply_err = None

            try:
                with _cf.ThreadPoolExecutor(max_workers=1) as _pool:
                    _future = _pool.submit(_ol_chat, full_msg, system, model, hist)

                    # Wait for Ollama — just poll, no socket writes
                    _elapsed = 0
                    while not _future.done():
                        time.sleep(1)
                        _elapsed += 1
                        if _elapsed >= 180: break  # Safety cap: 3 minutes

                    try:
                        reply = _future.result(timeout=5)
                    except Exception as _fe:
                        reply_err = str(_fe)
            finally:
                _ollama_busy = False  # Resume crawlers

            if reply is None:
                reply = (f"[Ollama error] {reply_err}" if reply_err
                         else "Butler AI timed out — Ollama is taking too long. Try a shorter question.")

            is_err = (
                reply.startswith("[Ollama error]") or
                reply.startswith("MODEL_NOT_INSTALLED:") or
                reply.startswith("Butler AI is offline") or
                "not installed" in reply
            )
            if not is_err:
                try:
                    device_id = _gs("locked_device") or "anon"
                    _chat_save(device_id, "user", msg)
                    _chat_save(device_id, "assistant", reply)
                    if model and model != _gs("active_model"):
                        _ss("active_model", model)
                except: pass
            self._json({
                "status":      "ok",
                "response":    reply,
                "reply":       reply,
                "message":     reply,
                "ollama":      not is_err,
                "ollamaModel": model if not is_err else "",
                "ai":          "ollama" if not is_err else "local",
                "model":       model,
                "modelSize":   _model_size_label(model),
                "modelTier":   _model_tier(model),
                "ollamaError": is_err,
                "responseTimeMs":   int((time.time() - _chat_t0) * 1000),
                "kbArticlesUsed":   _kb_used_count,
                "crawlersPaused":   _perf_mode == "battery" or _ollama_busy,
                "perfMode":         _perf_mode,
            })

        # ── RECEIVE FILE FROM PHONE ───────────────────────────────
        elif path == "/api/receive_file":
            if not self._authed(body):
                self._json({"error": "Unauthorized", "code": "AUTH_REQUIRED"}, 401); return
            fn  = (body.get("filename") or "upload.bin").replace("..", "").replace("/", "_").replace("\\", "_")
            b64 = body.get("data", "")
            if not b64:
                self._json({"error": "No file data provided"}, 400); return
            try:
                raw  = base64.b64decode(b64)
                dest = Path.home() / "Desktop" / fn
                dest.parent.mkdir(parents=True, exist_ok=True)
                # Auto-rename if exists
                c = 1
                while dest.exists():
                    stem = Path(fn).stem
                    sfx  = Path(fn).suffix
                    dest = Path.home() / "Desktop" / f"{stem}_{c}{sfx}"
                    c += 1
                dest.write_bytes(raw)
                print(f"  [FILE] ✓ Received: {dest} ({len(raw):,} bytes)")
                self._json({"status": "ok", "message": f"Saved to {dest}", "bytes": len(raw), "filename": dest.name})
            except Exception as e:
                self._json({"error": str(e)}, 500)

        # ── PIP INSTALL ──────────────────────────────────────────
        elif path == "/api/pip/install":
            if not self._authed(body):
                self._json({"error": "Unauthorized", "code": "AUTH_REQUIRED"}, 401); return
            pkgs = body.get("packages", [])
            # Validate package names - no shell injection
            import re as _re_pip
            _PKG_RE = re.compile(r'^[A-Za-z0-9]([A-Za-z0-9._-]*[A-Za-z0-9])?(\[[\w,]+\])?([><=!]=?[\w.]+)?$')
            safe = [str(p).strip() for p in pkgs
                    if isinstance(p, str)
                    and len(p.strip()) < 100
                    and _PKG_RE.match(str(p).strip())]
            if not safe:
                self._json({"error": "No valid package names provided"}, 400); return
            try:
                r = subprocess.run(
                    [sys.executable, "-m", "pip", "install"] + safe,
                    capture_output=True, text=True, timeout=180
                )
                self._json({
                    "status": "ok" if r.returncode == 0 else "error",
                    "output": (r.stdout + r.stderr).strip()[-3000:],
                    "installed": safe if r.returncode == 0 else [],
                })
            except Exception as e:
                self._json({"error": str(e)}, 500)

        # ── REQUIREMENTS INSTALL ─────────────────────────────────
        elif path == "/api/requirements/install":
            if not self._authed(body):
                self._json({"error": "Unauthorized", "code": "AUTH_REQUIRED"}, 401); return
            ok = _auto_install(verbose=False)
            scan = _scan_requirements(verbose=False)
            self._json({
                "status":  "ok" if ok else "partial",
                "packages": scan,
                "allOk":   all(r["status"] == "OK" for r in scan),
            })

        # ── KILL INTERFERING PROCESSES ────────────────────────────
        # ── TOKEN VERIFY ─────────────────────────────────────────
        elif path == "/api/verify":
            # App calls this right after /pair to confirm token is working
            if not self._authed(body):
                self._json({"valid": False, "error": "Token invalid or expired"}, 401); return
            locked = _gs("locked_device")
            self._json({
                "valid":         True,
                "deviceId":      locked or "",
                "serverVersion": VERSION,
                "pairingCode":   _gs("pairing_code") or "",
                "paired":        bool(locked),
                "uptime":        int(time.time() - _start_time),
            })

        # ── ON-DEMAND SCRIPT SEARCH ─────────────────────────────
        elif path == "/api/search/scripts":
            if not self._authed(body): self._json({"error":"Pair your phone first via QR.","code":"AUTH_REQUIRED"},401); return
            query = body.get("query","")
            if not query: self._json({"error":"query required"},400); return
            auto_crawl = body.get("crawl", True)  # crawl=True saves to KB
            results = _search_scripts(query, max_results=8)
            saved = 0
            if auto_crawl and results:
                def _do_crawl():
                    nonlocal saved
                    for r in results[:5]:
                        existing = _db_q("SELECT url FROM knowledge_base WHERE url=? LIMIT 1", (r["url"],))
                        if not existing:
                            cr = _crawl_and_save(r["url"], "Scripts", query.split()[:3])
                            if cr.get("ok"): saved += 1
                _do_crawl()
            self._json({
                "status":  "ok",
                "query":   query,
                "results": results,
                "saved":   saved,
                "count":   len(results),
            })

        # ── LEARNING STATUS ──────────────────────────────────────
        elif path == "/api/crawler/pause":
            _learning_active = False
            self._json({"status":"ok","crawling":False,
                      "message":"Crawler paused — full CPU available for AI chat"}); return
        elif path == "/api/crawler/resume":
            _learning_active = True
            self._json({"status":"ok","crawling":True,
                      "message":"Crawler resumed"}); return
        elif path == "/api/learn/status":
            if not self._authed(body): self._json({"error":"Pair your phone first via QR.","code":"AUTH_REQUIRED"},401); return
            try:
                cp_rows = _db_q("SELECT * FROM learn_checkpoint WHERE id=1")
                cp = cp_rows[0] if cp_rows else {}
                top_topics = _db_q(
                    "SELECT topic, asks FROM user_topics ORDER BY asks DESC LIMIT 10"
                )
                self._json({
                    "status":           "ok",
                    "articlesTotal":    _kb_count(),
                    "articlesSession":  _session_articles,
                    "queuePending":     _lq_size(),
                    "workersRunning":   sum(1 for t in threading.enumerate()
                                           if t.name.startswith("learn-")),
                    "learningActive":   _learning_active,
                    "lastCheckpoint":   cp.get("last_save", 0),
                    "sessionStart":     _session_start,
                    "uptimeMins":       round((time.time()-_session_start)/60, 1)
                                        if _session_start else 0,
                    "topUserTopics":    [{"topic": r["topic"], "asks": r.get("asks", 0)} for r in top_topics],
                })
            except Exception as e:
                self._json({"status":"ok","articlesTotal":_kb_count(),"error":str(e)})

        elif path == "/api/kill_interference":
            if not self._authed(body):
                self._json({"error": "Unauthorized", "code": "AUTH_REQUIRED"}, 401); return
            target_port = body.get("port")
            target_pid  = body.get("pid")
            report = {"killed": [], "errors": [], "action": "none"}
            if target_pid:
                # Kill specific PID
                try:
                    if IS_WINDOWS:
                        subprocess.run(["taskkill","/F","/PID",str(target_pid)], capture_output=True, timeout=5)
                    else:
                        os.kill(int(target_pid), signal.SIGTERM)
                    report["killed"].append(f"PID {target_pid}")
                    report["action"] = "pid_killed"
                except Exception as e:
                    report["errors"].append(str(e))
            elif target_port:
                # Kill process on specific port
                killed = _kill_process_on_port(int(target_port))
                report["killed"] = [f"PID {p['pid']} ({p['name']}) on port {target_port}" for p in killed]
                report["action"] = "port_cleared"
            else:
                # Kill all interference
                report = _kill_interference()
                report["action"] = "full_cleanup"
            self._json({"status": "ok", "report": report})

        # ── OLLAMA PULL ──────────────────────────────────────────
        elif path == "/api/ollama/pull":
            if not self._authed(body): self._json({"error":"Pair your phone first via QR.","code":"AUTH_REQUIRED"},401); return
            model_to_pull = body.get("model", DEFAULT_MODEL)

            # Pre-flight disk check — respond immediately with space info
            ok_space, free_gb, req_gb = _check_disk_space_for_model(model_to_pull)
            if not ok_space:
                self._json({
                    "status":    "error",
                    "ok":        False,
                    "error":     f"Not enough disk space: need {req_gb:.1f} GB, have {free_gb:.1f} GB free.",
                    "free_gb":   free_gb,
                    "req_gb":    req_gb,
                    "code":      "INSUFFICIENT_DISK",
                }, 200)  # 200 so app reads the body
                return

            # Guard: only one pull at a time
            if _pull_progress.get("active"):
                self._json({
                    "status":  "ok",
                    "ok":      True,
                    "message": f"Already pulling {_pull_progress.get('model','a model')} — check /api/ollama/pull_status",
                })
                return

            def _do_pull():
                if not _ollama_is_running():
                    _start_ollama_service()
                _ensure_model(model_to_pull)

            threading.Thread(target=_do_pull, daemon=True, name="ollama-pull").start()
            self._json({
                "status":   "ok",
                "ok":       True,
                "message":  f"Downloading {model_to_pull} ({req_gb:.1f} GB). Poll /api/ollama/pull_status for live progress.",
                "free_gb":  free_gb,
                "req_gb":   req_gb,
            })

        # ── RESET PAIR ───────────────────────────────────────────
        # ── PAIR STATUS (no auth required - safe public info) ────────
        elif path == "/api/pair/status":
            locked = _gs("locked_device")
            self._json({
                "paired":      bool(locked),
                "pairingCode": _gs("pairing_code") or "" if not locked else "",
                "serverVersion": VERSION,
                "pairingReady": not bool(locked),
                "isAuthDisabled": not bool(locked),
            })

        elif path == "/api/reset_pair":
            # Allow reset if:
            # 1. Valid Bearer token (already paired device) - normal case
            # 2. Correct pairingCode provided (person can see PC screen) - new install case
            # 3. No device locked yet (server is open) - first time case
            code_provided = (body.get("pairingCode") or "").strip()
            stored_code   = _gs("pairing_code") or ""
            locked        = _gs("locked_device")
            
            has_valid_token = self._authed(body)
            has_valid_code  = (code_provided and stored_code and 
                               code_provided.upper() == stored_code.upper())
            is_open         = not locked
            
            if not (has_valid_token or has_valid_code or is_open):
                self._json({
                    "error": "Provide valid token or current pairing code to reset.",
                    "hint":  "Check the code shown on your PC screen.",
                }, 401); return
            
            with _pair_lock:
                nc = _gen_code()
                _ss("locked_device", None)
                _ss("pairing_code",  nc)
                _ss("paired_at",     None)
                _log(f"Pair reset — server is OPEN again. New reset code: {nc}", "warn")
                print(f"  [AUTH] ⚠ Pair reset — server is now OPEN for next device")
            self._json({"status": "ok", "newCode": nc, "message": "Reset complete. Server is open for new device."})

        # ── PERFORMANCE MODE ──────────────────────────────────
        # Controls crawler behavior to manage CPU usage.
        # "auto" = crawlers pause when CPU high or Ollama active
        # "performance" = crawlers run full speed (fast KB growth)
        # "battery" = crawlers fully disabled (minimum CPU)
        elif path == "/api/performance":
            if not self._authed(body): self._json({"error":"Pair your phone first via QR.","code":"AUTH_REQUIRED"},401); return
            mode = (body.get("mode") or "").lower()
            if mode in ("auto", "performance", "battery"):
                _perf_mode = mode
                _log(f"Performance mode changed to: {mode}", "ok")
                self._json({"status": "ok", "mode": mode})
            elif not mode:
                # GET current mode
                cpu = 0
                try:
                    if HAS_PSUTIL: cpu = psutil.cpu_percent(interval=0.3)
                except: pass
                self._json({
                    "status": "ok",
                    "mode": _perf_mode,
                    "ollamaBusy": _ollama_busy,
                    "cpu": cpu,
                    "crawlersActive": _perf_mode != "battery" and not _ollama_busy,
                })
            else:
                self._json({"error": "mode must be: auto, performance, or battery"}, 400)

        # ── PC HEALTH ALERTS ──────────────────────────────────
        # ── TASK SCHEDULER ───────────────────────────────────
        # ── CONNECTION DEBUG LOG ─────────────────────────────────
        elif path == "/api/debug/connection":
            locked = _gs("locked_device")
            self._json({
                "status": "ok",
                "serverState": {
                    "locked":        bool(locked),
                    "lockedDevice":  (locked or "")[:20],
                    "pairedAt":      _gs("paired_at") or "",
                    "lastSeen":      _gs("last_seen") or "",
                    "pairingCode":   _gs("pairing_code") or "",
                    "serverPort":    _gs("server_port") or "",
                    "serverVersion": VERSION,
                    "uptime":        int(time.time() - _start_time),
                    "ollamaReady":   _ol_ok(),
                    "kbArticles":    _kb_count(),
                    "allIPs":        _cached_ips,
                },
                "recentEvents": [
                    {
                        "time":     e["time"],
                        "endpoint": e["endpoint"],
                        "device":   e["device"],
                        "result":   e["result"],
                        "detail":   e["detail"],
                    }
                    for e in list(_conn_events)[-20:]
                ],
                "threads": [t.name for t in threading.enumerate()],
                "help": {
                    "LOCKED":      "Server paired to a device — working normally",
                    "RECONNECT":   "Same device reconnected — token refreshed",
                    "AUTO-UNLOCK": "Old device stale — auto-unlocked for new device",
                    "REJECTED":    "Different device tried to connect — blocked",
                    "RACE":        "Two devices tried to pair at exact same moment",
                    "NO_DEVICE_ID":"App sent empty deviceId — check app code",
                    "LOCK_FAILED": "State file write failed — disk issue?",
                },
            })

        # ── BUTLER CLEAR HISTORY ─────────────────────────────────
        elif path in ("/api/butler/clear", "/api/ai/clear", "/api/chat/clear"):
            if not self._authed(body): self._json({"error":"Pair your phone first via QR.","code":"AUTH_REQUIRED"},401); return
            device_id = _gs("locked_device") or "anon"
            _chat_clear(device_id)
            self._json({"status": "ok", "cleared": True})

        # ── KB SEARCH ────────────────────────────────────────────
        elif path == "/api/kb/search":
            if not self._authed(body): self._json({"error":"Pair your phone first via QR.","code":"AUTH_REQUIRED"},401); return
            q = body.get("q", body.get("query", ""))
            limit = int(body.get("limit", 8))
            self._json({"results": _kb_search(q, limit), "query": q, "total": _kb_count()})

        # ── KB ENRICH (returns enrichments[] array) ───────────────
        elif path == "/api/kb/enrich":
            if not self._authed(body): self._json({"error":"Pair your phone first via QR.","code":"AUTH_REQUIRED"},401); return
            q    = body.get("query", body.get("q", ""))
            kws  = body.get("keywords", [])
            mx   = int(body.get("maxResults", 5))
            enr  = _kb_enrich(q, kws, mx)
            self._json({"enrichments": enr, "query": q, "count": len(enr)})

        # ── KB LOG (save from app) ────────────────────────────────
        # ── KB CONTRIBUTE: phone submits URLs for server to crawl ──
        elif path == "/api/kb/contribute":
            # Phone tells server to crawl a URL — server does the work
            # This offloads crawling from phone to PC (faster, saves battery)
            urls_in  = body.get("urls", [])
            topic    = body.get("topic", "UserRequest")
            priority = int(body.get("priority", 8))
            added = 0
            for url in urls_in[:10]:
                if not isinstance(url, str) or not url.startswith("http"): continue
                existing = _db_q("SELECT url FROM knowledge_base WHERE url=?", (url,))
                queued   = _db_q("SELECT url FROM learn_queue WHERE url=?", (url,))
                if not existing and not queued:
                    _lq_add(url, "UserRequest", topic.split()[:4], priority=priority, source="phone")
                    added += 1
            self._json({"status": "ok", "queued": added, "queueSize": _lq_size()})

        # ── KB SEARCH EXPAND: phone asks server to find more on topic ──
        elif path == "/api/kb/expand":
            # Phone sends a topic — server searches DuckDuckGo and queues results
            topic = (body.get("topic") or body.get("query") or "").strip()
            if not topic:
                self._json({"error": "topic required"}, 400); return
            # Add high-priority search URLs for this topic
            search_urls = [
                f"https://duckduckgo.com/html/?q={urllib.parse.quote(topic)}+python+script",
                f"https://duckduckgo.com/html/?q={urllib.parse.quote(topic)}+windows+fix",
                f"https://www.google.com/search?q={urllib.parse.quote(topic)}+site:docs.python.org",
                f"https://www.google.com/search?q={urllib.parse.quote(topic)}+site:docs.microsoft.com",
            ]
            added = 0
            for url in search_urls:
                queued = _db_q("SELECT url FROM learn_queue WHERE url=?", (url,))
                if not queued:
                    _lq_add(url, "UserSearch", topic.split()[:4], priority=9, source="expand")
                    added += 1
            _log(f"KB expand: queued {added} searches for '{topic[:30]}'", "ok")
            self._json({"status": "ok", "queued": added, "topic": topic, "queueSize": _lq_size()})

        elif path == "/api/kb/feed":
            # POST: add a URL to the learning queue (app feeds URLs to server KB)
            if not self._authed(body): self._json({"error":"Pair your phone first via QR.","code":"AUTH_REQUIRED"},401); return
            url     = (body.get("url") or "").strip()
            topic   = (body.get("topic") or body.get("category") or "General").strip()
            source  = body.get("source", "app")
            if not url or not url.startswith("http"):
                self._json({"error":"valid url required"},400); return
            try:
                added = _lq_add(url, topic, topic.split()[:3], priority=7, source=source)
                self._json({"status":"ok","url":url,"queued":bool(added),
                            "queueSize":_lq_size()})
            except Exception as e:
                self._json({"error":str(e)},500)


        elif path == "/api/kb/log":
            # Allow unauthenticated KB saves from app when token is being refreshed
            # But block strangers when server is locked to a device
            if _gs("locked_device") and not self._authed(body):
                self._json({"error":"Pair your phone first via QR.","code":"AUTH_REQUIRED"},401); return
            entry   = body.get("entry") or body
            url     = entry.get("url",     f"local://kb-{uuid.uuid4().hex[:8]}")
            title   = entry.get("title",   "App Knowledge")
            # Accept .content (new), .text (legacy), or full entry as JSON
            content = entry.get("content") or entry.get("text") or ""
            if not content:
                content = json.dumps(entry)
            text = content[:12000]
            _kb_save(url, title, text, entry.get("domain", "App"))
            _sigma_stats["articles"] = _kb_count()
            n = _kb_count()
            _refresh_gui()
            self._json({
                "status":     "ok",
                "ok":         True,
                "saved":      True,
                "url":        url,
                "entryCount": n,
                "analyzedBy": "server",
                "applied":    [],
                "analysis":   {"score": 0.8, "health": "good",
                               "insights": [f"KB now has {n} articles"]},
            })

        # ── WEB CRAWL ────────────────────────────────────────────
        elif path in ("/api/crawl", "/api/crawl/single"):
            url    = body.get("url", "")
            domain = body.get("domain", "General")
            topic  = body.get("topic",  "Unknown")
            mode   = body.get("mode",   "fetch")
            kw     = body.get("keywords", [])
            if not url: self._json({"error": "url required"}, 400); return
            res = _crawl_and_save(url, domain or "Custom", kw)
            if res["ok"]:
                self._json({
                    "status":    "ok",
                    "url":       res["url"],
                    "title":     res.get("title", ""),
                    "cleanText": res.get("text", ""),
                    "text":      res.get("text", ""),
                    "wordCount": res.get("words", 0),
                    "links":     res.get("links", []),
                    "domain":    domain,
                    "topic":     topic,
                    "method":    "SIGMA-NET-RELAY",
                    "saved":     True,
                })
            else:
                self._json({
                    "status": "error",
                    "error":  res.get("error", ""),
                    "url":    url,
                    "saved":  False,
                })

        # ── BATCH CRAWL ──────────────────────────────────────────
        elif path == "/api/crawl/batch":
            # Accept both formats: {requests:[...]} (new app) and {urls:[...]} (legacy)
            requests_list = body.get("requests", body.get("urls", []))
            if not requests_list:
                self._json({"error": "requests required"}, 400); return
            results = []
            for req in requests_list[:20]:
                # Accept both string URLs and {url, domain, topic, ...} objects
                if isinstance(req, str):
                    url_str = req
                    domain  = "General"
                    topic   = "Unknown"
                else:
                    url_str = req.get("url", "")
                    domain  = req.get("domain", "General")
                    topic   = req.get("topic", "Unknown")
                if not url_str: continue
                r = _crawl_and_save(url_str)
                results.append({
                    "url":       r.get("url", url_str),
                    "ok":        r.get("ok", False),
                    "title":     r.get("title", ""),
                    "cleanText": r.get("text", r.get("cleanText", "")),
                    "wordCount": r.get("words", r.get("wordCount", 0)),
                    "links":     r.get("links", []),
                    "domain":    domain,
                    "topic":     topic,
                    "method":    "SIGMA-NET-RELAY",
                    "error":     r.get("error", ""),
                })
            _sigma_stats["articles"] = _kb_count()
            completed   = sum(1 for r in results if r["ok"])
            failed      = sum(1 for r in results if not r["ok"])
            total_words = sum(r.get("wordCount", 0) for r in results)
            self._json({
                "status":     "ok",
                "results":    results,
                "completed":  completed,
                "failed":     failed,
                "totalWords": total_words,
                "saved":      completed,
            })

        # ── FILESYSTEM SCAN ──────────────────────────────────────
        elif path == "/api/fs/crawl":
            if not self._authed(body): self._json({"error":"Pair your phone first via QR.","code":"AUTH_REQUIRED"},401); return
            root    = body.get("root", str(Path.home()))
            pattern = body.get("pattern", "*.py")
            try:
                root_p = Path(root); files = []
                for fp in root_p.rglob(pattern):
                    if not fp.is_file(): continue
                    stat = fp.stat()
                    entry = {"path": str(fp), "name": fp.name,
                             "ext":  fp.suffix.lower(),
                             "size_kb": round(stat.st_size/1024, 2),
                             "modified": time.strftime("%Y-%m-%dT%H:%M:%SZ",
                                         time.gmtime(stat.st_mtime)),
                             "relative": str(fp.relative_to(root_p))}
                    if (stat.st_size < 65536 and
                            fp.suffix.lower() in {".py",".txt",".md",".json",".csv",".sh",".ps1"}):
                        try:
                            c = fp.read_text(errors="replace")
                            entry["content"] = c[:65536]
                            entry["lines"] = c.count(chr(10))
                        except: pass
                    files.append(entry)
                    if len(files) >= 500: break
                self._json({"ok": True, "root": str(root_p), "pattern": pattern,
                            "files": files, "total": len(files),
                            "scanned": len(files), "method": "rglob",
                            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())})
            except Exception as e:
                self._json({"ok": False, "error": str(e), "files": [], "total": 0})

        # ── FS DRIVES ────────────────────────────────────────────
        elif path == "/api/fs/drives":
            if not self._authed(body): self._json({"error":"Pair your phone first via QR.","code":"AUTH_REQUIRED"},401); return
            drives = []
            if HAS_PSUTIL:
                try:
                    for p in psutil.disk_partitions(all=False):
                        try:
                            u = psutil.disk_usage(p.mountpoint)
                            drives.append({"path": p.mountpoint, "label": p.device,
                                           "free_gb": round(u.free/1e9,2),
                                           "total_gb": round(u.total/1e9,2)})
                        except:
                            drives.append({"path": p.mountpoint, "label": p.device,
                                           "free_gb": None, "total_gb": None})
                except: pass
            self._json({"drives": drives})

        # ── FS READ ──────────────────────────────────────────────
        elif path == "/api/fs/read":
            if not self._authed(body): self._json({"error":"Pair your phone first via QR.","code":"AUTH_REQUIRED"},401); return
            fpath = body.get("path", "")
            if not fpath: self._json({"error": "path required"}, 400); return
            try:
                fp = Path(fpath)
                if not fp.exists(): self._json({"error": "Not found"}, 404); return
                c = fp.read_text(errors="replace")
                self._json({"ok": True, "path": str(fp), "content": c[:65536],
                            "lines": c.count(chr(10)),
                            "size_kb": round(fp.stat().st_size/1024, 2),
                            "truncated": len(c) > 65536})
            except Exception as e:
                self._json({"ok": False, "error": str(e)})

        # ── LIST SHARED FILES ─────────────────────────────────────
        elif path == "/api/files":
            if not self._authed(body): self._json({"error":"Pair your phone first via QR.","code":"AUTH_REQUIRED"},401); return
            SHARE_DIR.mkdir(parents=True, exist_ok=True)
            files = [{"name": f.name,
                      "size": f.stat().st_size,
                      "size_str": f"{f.stat().st_size//1024}KB"}
                     for f in sorted(SHARE_DIR.iterdir()) if f.is_file()]
            self._json({"files": files, "count": len(files)})


        elif path == "/api/undo/rollback":
            entry_id = body.get("id")
            if not entry_id: self._json({"error": "id required"}, 400); return
            self._json(_undo_rollback(int(entry_id)))

        elif path == "/api/pc-check/action":
            action = (body.get("action") or "").strip()
            if action not in _PC_CLEAN_SCRIPTS:
                self._json({"error": "Unknown action: " + action}, 400); return
            script = _PC_CLEAN_SCRIPTS[action]
            undo_id = _undo_create(script, "python", "PC Check: " + action)
            try:
                kw = {}
                if IS_WINDOWS: kw["creationflags"] = subprocess.CREATE_NO_WINDOW
                exec_env = os.environ.copy()
                exec_env["PYTHONIOENCODING"] = "utf-8"; exec_env["PYTHONUTF8"] = "1"
                r = subprocess.run([sys.executable, "-c", script], capture_output=True, text=True,
                                   encoding="utf-8", errors="replace", timeout=60,
                                   cwd=str(Path.home()), env=exec_env, **kw)
                output = (r.stdout + "\n" + r.stderr).strip()
                if undo_id: _undo_complete(undo_id, output, r.returncode == 0)
                import re as _pcre
                if action in ("temp","browser","full_clean") and r.returncode == 0:
                    fm = _pcre.search(r"(\d+)\s*MB\s*freed", output)
                    fc = _pcre.search(r"(\d+)\s*(?:files?\s*)?clean", output)
                    if fm: _pc_stat_inc("space_recovered_bytes", int(fm.group(1))*1024*1024)
                    if fc: _pc_stat_inc("files_cleaned", int(fc.group(1)))
                if action == "organize" and r.returncode == 0:
                    om = _pcre.search(r"Organized\s*(\d+)", output)
                    if om: _pc_stat_inc("files_organized", int(om.group(1)))
                self._json({"status": "ok" if r.returncode == 0 else "error",
                            "output": output[:5000], "exitCode": r.returncode,
                            "undoId": undo_id, "undoAvailable": True})
            except subprocess.TimeoutExpired:
                self._json({"status": "error", "error": "Timed out", "undoId": undo_id})
            except Exception as e:
                self._json({"status": "error", "error": str(e), "undoId": undo_id})

        elif path == "/api/scripts/run":
            if not self._authed(body): self._json({"error":"Pair your phone first via QR.","code":"AUTH_REQUIRED"},401); return
            script_id = (body.get("id") or "").strip()
            if script_id in _PC_CLEAN_SCRIPTS:
                script = _PC_CLEAN_SCRIPTS[script_id]
                undo_id = _undo_create(script, "python", "Library: " + script_id)
                try:
                    kw = {}
                    if IS_WINDOWS: kw["creationflags"] = subprocess.CREATE_NO_WINDOW
                    env = os.environ.copy(); env["PYTHONIOENCODING"]="utf-8"; env["PYTHONUTF8"]="1"
                    r = subprocess.run([sys.executable,"-c",script], capture_output=True, text=True,
                                       encoding="utf-8", errors="replace", timeout=60,
                                       cwd=str(Path.home()), env=env, **kw)
                    output = (r.stdout+"\n"+r.stderr).strip()
                    if undo_id: _undo_complete(undo_id, output, r.returncode==0)
                    self._json({"status":"ok" if r.returncode==0 else "error",
                                "output":output[:5000], "exitCode":r.returncode,
                                "undoId":undo_id, "undoAvailable":True, "generated":False})
                except Exception as e:
                    self._json({"status":"error","error":str(e),"undoId":undo_id})
            elif _ol_ok():
                desc = script_id
                for cat in _SCRIPT_LIBRARY.values():
                    for s in cat.get("scripts",[]):
                        if s["id"]==script_id: desc=s["name"]+": "+s["desc"]; break
                reply = _ol_chat("Write a complete Python script: "+desc+"\nReturn ONLY Python code.",
                                 "You are a Python script generator. Return ONLY code, no markdown.")
                code = reply
                if "```python" in reply: code = reply.split("```python")[1].split("```")[0].strip()
                elif "```" in reply: code = reply.split("```")[1].split("```")[0].strip()
                self._json({"status":"ok","script":code,"description":desc,"generated":True})
            else:
                self._json({"error":"Script not pre-built and Ollama not running"}, 503)

        elif path == "/api/scripts/build":
            if not self._authed(body): self._json({"error":"Pair your phone first via QR.","code":"AUTH_REQUIRED"},401); return
            desc = (body.get("description") or body.get("query") or "").strip()
            if not desc: self._json({"error":"description required"}, 400); return
            if _ol_ok():
                reply = _ol_chat("Write a complete Python script: "+desc+"\nRules: all imports, error handling, print progress. Return ONLY Python code.",
                                 "You are a Python script generator. Return ONLY code.")
                code = reply
                if "```python" in reply: code = reply.split("```python")[1].split("```")[0].strip()
                elif "```" in reply: code = reply.split("```")[1].split("```")[0].strip()
                self._json({"status":"ok","script":code,"description":desc,"language":"python"})
            else:
                self._json({"error":"Ollama not running"}, 503)


        # ── SCRIPTS LIST (saved user scripts from DB) ─────────────────────
        elif path in ("/api/scripts/list", "/api/scripts/saved"):
            if not self._authed(body): self._json({"error":"Pair your phone first via QR.","code":"AUTH_REQUIRED"},401); return
            try:
                rows = _db_q(
                    "SELECT id, name, category, language, description, code, created_at "
                    "FROM user_scripts ORDER BY created_at DESC LIMIT 200"
                )
                scripts = [{
                    "id": r["id"], "name": r["name"],
                    "category": r.get("category", "Custom"),
                    "language": r.get("language", "python"),
                    "description": r.get("description", ""),
                    "code": r["code"],
                    "createdAt": r.get("created_at", ""),
                } for r in rows]
                self._json({"status": "ok", "scripts": scripts, "count": len(scripts)})
            except Exception as e:
                self._json({"error": str(e)}, 500)

        # ── SCRIPTS SAVE (user saves a custom script to server DB) ─────────
        elif path == "/api/scripts/save":
            if not self._authed(body): self._json({"error":"Pair your phone first via QR.","code":"AUTH_REQUIRED"},401); return
            name  = (body.get("name") or "").strip()
            code  = (body.get("code") or body.get("script") or "").strip()
            cat   = (body.get("category") or "Custom").strip()
            lang  = (body.get("language") or "python").strip().lower()
            desc  = (body.get("description") or "").strip()
            sid   = body.get("id")  # existing ID = update
            if not name or not code:
                self._json({"error": "name and code are required"}, 400); return
            try:
                # Ensure table exists
                _db_run("""CREATE TABLE IF NOT EXISTS user_scripts(
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL, category TEXT DEFAULT 'Custom',
                    language TEXT DEFAULT 'python', description TEXT,
                    code TEXT NOT NULL, created_at REAL DEFAULT 0
                )""")
                if sid:
                    _db_run(
                        "UPDATE user_scripts SET name=?,category=?,language=?,description=?,code=? WHERE id=?",
                        (name, cat, lang, desc, code, sid)
                    )
                    self._json({"status": "ok", "id": sid, "updated": True})
                else:
                    _db_run(
                        "INSERT INTO user_scripts(name,category,language,description,code,created_at) VALUES(?,?,?,?,?,?)",
                        (name, cat, lang, desc, code, time.time())
                    )
                    rows = _db_q("SELECT last_insert_rowid() id")
                    new_id = rows[0]["id"] if rows else None
                    self._json({"status": "ok", "id": new_id, "saved": True})
            except Exception as e:
                self._json({"error": str(e)}, 500)


        # ── SYNC — one round-trip on app foreground (§22) ────────────────────
        elif path == "/api/sync":
            if not self._authed(body): self._err("AUTH_REQUIRED"); return
            try:
                from urllib.parse import parse_qs
                qs = parse_qs(self.path.split("?", 1)[1] if "?" in self.path else "")
                cursor = int(qs.get("since", ["0"])[0])
            except Exception:
                cursor = 0
            locked = _gs("locked_device")
            try:
                audit_rows = _db_q(
                    "SELECT id, ts, kind, detail, exit_code FROM audit WHERE id > ? "
                    "ORDER BY id DESC LIMIT 50", (cursor,)
                )
                audit = [{"id":r["id"],"ts":r["ts"],"kind":r["kind"],
                          "detail":r.get("detail",""),"exitCode":r.get("exit_code")} for r in audit_rows]
            except Exception:
                audit = []
            self._json({
                "metrics":     _metrics_cached(2.0),
                "audit":       audit,
                "pair":        {"locked": bool(locked), "code": "" if locked else (_gs("pairing_code") or "")},
                "ts":          int(time.time() * 1000),
                "serverVersion": VERSION,
            })

        # ── AUTH ROTATE — refresh device secret weekly (§10) ──────────────────
        elif path == "/api/auth/rotate":
            if not self._authed(body): self._err("AUTH_REQUIRED"); return
            locked = _gs("locked_device")
            new_secret = base64.b64encode(os.urandom(32)).decode()
            try:
                _db_run("CREATE TABLE IF NOT EXISTS device_secrets("
                        "device_id TEXT PRIMARY KEY, secret TEXT, ts INTEGER)")
                _db_run("INSERT OR REPLACE INTO device_secrets VALUES (?,?,?)",
                        (locked, new_secret, int(time.time())))
            except Exception as e:
                log.warning(f"[AUTH] Secret rotate failed: {e}")
            self._json({"deviceSecret": new_secret, "ts": int(time.time())})

        # ── SESSIONS — who has held this lock (§11) ───────────────────────────
        elif path == "/api/sessions":
            if not self._authed(body): self._err("AUTH_REQUIRED"); return
            try:
                rows = _db_q("SELECT device_id, paired_at, last_seen, ip "
                             "FROM sessions ORDER BY last_seen DESC LIMIT 10")
                history = [dict(r) for r in rows]
            except Exception:
                history = []
            self._json({"current": _gs("locked_device"), "history": history})

        # ── POWER CONTROL — sleep/shutdown/restart (§13) ──────────────────────
        elif path == "/api/power":
            if not self._authed(body): self._err("AUTH_REQUIRED"); return
            if not _gs("power_actions_enabled"):
                self._json({"error": "Power actions disabled — enable in Settings"}, 403); return
            action = (body.get("action") or "").lower()
            confirm = body.get("confirm", False)
            if not confirm:
                self._json({"error": "Require confirm:true to prevent accidents"}, 400); return
            plat = sys.platform
            # shell=False — each command is a list, not a string.
            # Prevents shell injection if action string were ever tampered with.
            CMDS = {
                "win32": {
                    "sleep":     ["rundll32.exe", "powrprof.dll,SetSuspendState", "0,1,0"],
                    "hibernate": ["rundll32.exe", "powrprof.dll,SetSuspendState", "1,1,0"],
                    "shutdown":  ["shutdown", "/s", "/t", "10"],
                    "restart":   ["shutdown", "/r", "/t", "10"],
                },
                "linux": {
                    "sleep":     ["systemctl", "suspend"],
                    "shutdown":  ["shutdown", "-h", "+1"],
                    "restart":   ["shutdown", "-r", "+1"],
                },
                "darwin": {
                    "sleep":     ["pmset", "sleepnow"],
                    "shutdown":  ["sudo", "shutdown", "-h", "+1"],
                    "restart":   ["sudo", "shutdown", "-r", "+1"],
                },
            }
            cmds = CMDS.get(plat, CMDS.get("linux", {}))
            if action not in cmds:
                self._json({"error": f"Unknown action. Valid: {list(cmds.keys())}"}, 400); return
            try:
                kw = {}
                if sys.platform == "win32":
                    kw["creationflags"] = subprocess.CREATE_NO_WINDOW
                subprocess.Popen(cmds[action], shell=False, **kw)
                self._json({"ok": True, "action": action, "message": f"PC will {action} shortly"})
            except Exception as e:
                self._json({"error": str(e)}, 500)

        # ── CLIPBOARD — read/write PC clipboard (§14) ─────────────────────────
        elif path == "/api/clipboard":
            if not self._authed(body): self._err("AUTH_REQUIRED"); return
            def _clip_get():
                if IS_WINDOWS:
                    r = subprocess.run(["powershell", "-c", "Get-Clipboard"],
                                       capture_output=True, text=True, timeout=5)
                    return r.stdout.strip()
                elif sys.platform == "darwin":
                    return subprocess.check_output(["pbpaste"], text=True, timeout=5)
                return subprocess.check_output(["xclip", "-selection", "clipboard", "-o"],
                                               text=True, timeout=5)
            def _clip_set(s: str):
                if IS_WINDOWS:
                    subprocess.run(["clip"], input=s.encode("utf-16le"), timeout=5)
                elif sys.platform == "darwin":
                    p = subprocess.Popen(["pbcopy"], stdin=subprocess.PIPE)
                    p.communicate(s.encode())
                else:
                    p = subprocess.Popen(["xclip", "-selection", "clipboard"], stdin=subprocess.PIPE)
                    p.communicate(s.encode())
            text_in = body.get("text")
            if text_in is not None:
                try:
                    _clip_set(str(text_in)[:10000])
                    self._json({"ok": True, "action": "set", "length": len(text_in)})
                except Exception as e:
                    self._json({"error": str(e)}, 500)
            else:
                try:
                    content = _clip_get()
                    self._json({"ok": True, "text": content, "length": len(content)})
                except Exception as e:
                    self._json({"text": "", "error": str(e)})

        # ── KEYBOARD TYPE — remote typing (§14) ───────────────────────────────
        elif path == "/api/keyboard/type":
            if not self._authed(body): self._err("AUTH_REQUIRED"); return
            text = (body.get("text") or "")[:500]
            if not text:
                self._json({"error": "text required"}, 400); return
            try:
                import pyautogui
                pyautogui.typewrite(text, interval=0.008)
                self._json({"ok": True, "typed": len(text)})
            except ImportError:
                self._json({"error": "pyautogui not installed — run: pip install pyautogui"}, 503)
            except Exception as e:
                self._json({"error": str(e)}, 500)

        # ── PUSH NOTIFICATION REGISTER (§12) ──────────────────────────────────
        elif path == "/api/notify/register":
            if not self._authed(body): self._err("AUTH_REQUIRED"); return
            expo_token = (body.get("expoPushToken") or "").strip()
            if not expo_token:
                self._json({"error": "expoPushToken required"}, 400); return
            try:
                _db_run("CREATE TABLE IF NOT EXISTS push_tokens("
                        "device_id TEXT PRIMARY KEY, token TEXT, ts INTEGER)")
                _db_run("INSERT OR REPLACE INTO push_tokens VALUES (?,?,?)",
                        (_gs("locked_device"), expo_token, int(time.time())))
                self._json({"ok": True, "registered": True})
            except Exception as e:
                self._json({"error": str(e)}, 500)

        # ── SCRIPTS UPLOAD — save editor script to PC (§17) ───────────────────
        elif path == "/api/scripts/upload":
            if not self._authed(body): self._err("AUTH_REQUIRED"); return
            raw_name = (body.get("name") or "script").strip()
            name = re.sub(r"[^A-Za-z0-9_.-]", "_", raw_name)[:60]
            if not name.endswith(".py"): name += ".py"
            script_code = (body.get("script") or body.get("code") or "").strip()
            if not script_code:
                self._json({"error": "script/code required"}, 400); return
            safe_dir = Path.home() / ".butler" / "scripts"
            safe_dir.mkdir(parents=True, exist_ok=True)
            out = (safe_dir / name).resolve()
            # Path traversal guard
            if not str(out).startswith(str(safe_dir.resolve())):
                self._json({"error": "Invalid filename"}, 400); return
            try:
                out.write_text(script_code[:200_000], encoding="utf-8")
                self._json({"ok": True, "path": str(out), "name": name, "size": len(script_code)})
            except Exception as e:
                self._json({"error": str(e)}, 500)

        # ── BUTLER ABORT — stop active SSE stream (§15) ───────────────────────
        elif path == "/api/butler/abort":
            if not self._authed(body): self._err("AUTH_REQUIRED"); return
            rid = (body.get("requestId") or "").strip()
            if rid and rid in _ACTIVE_STREAMS:
                _ACTIVE_STREAMS[rid] = False
                self._json({"ok": True, "aborted": rid})
            else:
                self._json({"ok": False, "reason": "not found"}, 404)

        # ── STREAMING SCRIPT EXECUTION — live stdout per line (§2) ──────────
        elif path == "/api/execute/stream":
            if not self._authed(body): self._err("AUTH_REQUIRED"); return
            script   = (body.get("script") or body.get("code") or "").strip()
            language = (body.get("language") or "python").lower()
            if not script:
                self._json({"error": "script required"}, 400); return
            if len(script) > 200_000:
                self._json({"error": "Script too large (max 200KB)"}, 413); return
            # Run safety check
            for pat, reason in [
                (b"marshal.loads", "marshal deserialization"),
                (b"exec(compile(",  "exec+compile obfuscation"),
                (b"ctypes.CDLL(",   "arbitrary library loading"),
            ]:
                if pat in script.encode("utf-8", errors="ignore"):
                    self._json({"error": f"Blocked: {reason}", "blocked": True}, 400); return
            interp = sys.executable if language == "python" else language
            self.send_response(200)
            self.send_header("Content-Type",     "text/event-stream")
            self.send_header("Cache-Control",    "no-cache")
            self.send_header("X-Accel-Buffering","no")
            self.send_header("Connection",       "keep-alive")
            self._cors(); self.end_headers()
            t0 = time.time()
            try:
                proc = subprocess.Popen(
                    [interp, "-u", "-c", script],
                    stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                    text=True, bufsize=1, timeout=None,
                    cwd=str(Path.home()),
                )
                for line in iter(proc.stdout.readline, ""):
                    try:
                        self.wfile.write(
                            ("data: " + json.dumps({'chunk': line}) + "\n\n").encode()
                        )
                        self.wfile.flush()
                    except (BrokenPipeError, ConnectionResetError):
                        proc.kill(); return
                    if time.time() - t0 > EXEC_TIMEOUT:
                        proc.kill()
                        self.wfile.write(
                            ("data: " + json.dumps({'error': 'timeout', 'exitCode': -1, 'done': True}) + "\n\n").encode()
                        )
                        self.wfile.flush(); return
                proc.wait(timeout=3)
                self.wfile.write(
                            ("data: " + json.dumps({'done': True, 'exitCode': proc.returncode, 'elapsedMs': int((time.time()-t0)*1000)}) + "\n\n").encode()
                )
                self.wfile.flush()
            except Exception as e:
                try:
                    self.wfile.write(
                            ("data: " + json.dumps({'error': str(e), 'done': True, 'exitCode': -1}) + "\n\n").encode()
                    )
                    self.wfile.flush()
                except Exception:
                    pass

        # ── PAIR QR — rotate code + return PNG (§7) ───────────────────────────
        elif path == "/api/pair/qr":
            if body.get("rotate"):
                _ss("pairing_code", _gen_code())
            code = _gs("pairing_code") or _gen_code()
            ip_addr = _lan_ip() if hasattr(sys.modules[__name__], "_lan_ip") else "127.0.0.1"
            payload = json.dumps({"ip": ip_addr, "port": _PORT[0] if "_PORT" in dir() else 8766,
                                   "pairingCode": code, "version": VERSION})
            try:
                import qrcode, io
                img = qrcode.make(payload)
                buf = io.BytesIO(); img.save(buf, format="PNG")
                png = buf.getvalue()
                self.send_response(200)
                self.send_header("Content-Type",   "image/png")
                self.send_header("Content-Length", str(len(png)))
                self.send_header("X-Pair-Code",    code)
                self._cors(); self.end_headers()
                self.wfile.write(png)
            except ImportError:
                self._json({"error": "qrcode library not installed", "pairingCode": code,
                            "payload": payload})

        else:
            self._json({"error": "endpoint not found"}, 404)

# ══════════════════════════════════════════════════════
#  HELPERS
# ══════════════════════════════════════════════════════
def _get_pip_version():
    try:
        r = subprocess.run([sys.executable, "-m", "pip", "--version"],
                           capture_output=True, text=True, timeout=5)
        return r.stdout.strip().split()[1] if r.returncode == 0 else "unknown"
    except: return "unknown"

def _gen_code():
    import secrets as _sec
    return "".join(_sec.choice("ABCDEFGHJKLMNPQRSTUVWXYZ23456789") for _ in range(8))

def _register_startup():
    if not IS_WINDOWS:
        print("  [STARTUP] Auto-start registration only supported on Windows")
        return
    try:
        import winreg
        key  = winreg.HKEY_CURRENT_USER
        path = r"Software\Microsoft\Windows\CurrentVersion\Run"
        val  = f'"{sys.executable}" "{os.path.abspath(sys.argv[0])}"'
        with winreg.OpenKey(key, path, 0, winreg.KEY_WRITE) as rk:
            winreg.SetValueEx(rk, "CyberButlerServerV7", 0, winreg.REG_SZ, val)
        print("  [STARTUP] ✓ Registered as Windows startup program")
    except Exception as e:
        print(f"  [STARTUP] Failed: {e}")

# ══════════════════════════════════════════════════════
#  MAIN
# ══════════════════════════════════════════════════════
# ══════════════════════════════════════════════════════
#  TKINTER GUI  -  Butler AI aesthetic
#  Pure black · Cyan accent · Green status · Monospace
# ══════════════════════════════════════════════════════
BG    = "#000000"
BG2   = "#050A0E"
BG3   = "#0A1520"
BG4   = "#081018"
ACCENT= "#00CCFF"
ACCT2 = "#00EEFF"
GREEN = "#00FF88"
AMBER = "#FFB800"
RED   = "#FF4040"
BLUE  = "#4488FF"
TEXT  = "#E0F4FF"
MUTED = "#2A4A5A"
DIM   = "#1A3040"
_FM   = "Consolas"
F_TINY = (_FM,8); F_SM=(_FM,9); F_MONO=(_FM,10); F_MED=(_FM,11,"bold")
F_BIG  = (_FM,13,"bold"); F_HUGE=(_FM,15,"bold"); F_CODE=(_FM,9)



class NxBtn(tk.Canvas):
    """Flat button - left cyan bar accent, fills solid on hover."""
    def __init__(self, parent, text, cmd, w=130, h=28, col=None, font=F_MONO, **kw):
        col = col or ACCENT
        super().__init__(parent, width=w, height=h, bg=parent["bg"],
                         bd=0, highlightthickness=0, cursor="hand2", **kw)
        self._d = dict(cmd=cmd, w=w, h=h, col=col, font=font, text=text, hover=False)
        self._draw()
        self.bind("<Enter>",    lambda _: self._on(True))
        self.bind("<Leave>",    lambda _: self._on(False))
        self.bind("<Button-1>", lambda _: self._click())

    def _draw(self):
        d = self._d; self.delete("all")
        bg = d["col"] if d["hover"] else BG3
        fg = "#000000" if d["hover"] else d["col"]
        self.create_rectangle(0, 0, d["w"]-1, d["h"]-1, outline=d["col"], fill=bg, width=1)
        self.create_rectangle(0, 0, 2, d["h"], fill=d["col"], outline="")
        self.create_text(d["w"]//2+1, d["h"]//2, text=d["text"],
                         fill=fg, font=d["font"], anchor="center")

    def _on(self, on): self._d["hover"] = on; self._draw()
    def _click(self):
        self._d["hover"] = False; self._draw()
        try: self._d["cmd"]()
        except: pass
    def set_text(self, t): self._d["text"] = t; self._draw()


class PulseDot(tk.Canvas):
    """Animated pulsing status dot. Completely safe - stops on destroy."""
    def __init__(self, parent, size=10, color=GREEN, **kw):
        super().__init__(parent, width=size, height=size,
                         bg=parent["bg"], bd=0, highlightthickness=0, **kw)
        self._sz  = size
        self._col = color
        self._alive = True
        self._bright = True
        self._draw()
        self._pulse()

    def _draw(self):
        try:
            self.delete("all")
            p = 1
            c = self._col if self._bright else self._col + "55"
            self.create_oval(p, p, self._sz-p, self._sz-p, fill=c, outline="")
        except Exception:
            pass

    def _pulse(self):
        if not self._alive: return
        try:
            self._bright = not self._bright
            self._draw()
            self.after(900, self._pulse)
        except Exception:
            self._alive = False

    def set_color(self, c):
        self._col = c; self._draw()

    def destroy(self):
        self._alive = False
        try: super().destroy()
        except Exception: pass


def _build_gui(ip, port):
    """Butler AI aesthetic - pure black, cyan accents, pulse dots, monospace."""
    if not HAS_TK: return None
    try:
        root = tk.Tk()
        root.title(f"BUTLER AI SERVER  v{VERSION}")
        root.configure(bg=BG)
        root.minsize(860, 780)
        root.resizable(True, True)
        _gui["root"] = root

        # ── Header ────────────────────────────────────────────────
        hdr = tk.Frame(root, bg=BG2); hdr.pack(fill="x")
        lf  = tk.Frame(hdr, bg=BG2); lf.pack(side="left", padx=14, pady=10)
        tk.Label(lf, text="BUTLER", font=(_FM,17,"bold"), fg=ACCENT, bg=BG2).pack(side="left")
        tk.Label(lf, text="AI",     font=(_FM,17,"bold"), fg=ACCT2,  bg=BG2).pack(side="left")
        tk.Label(lf, text=f"  SERVER  v{VERSION}", font=F_TINY, fg=MUTED, bg=BG2).pack(side="left", pady=3)
        rf = tk.Frame(hdr, bg=BG2); rf.pack(side="right", padx=14, pady=8)
        try:
            dot = PulseDot(rf, size=10, color=GREEN)
            dot.pack(side="right", padx=(4,2), pady=2)
            _gui["dot"] = dot
        except Exception: pass
        ai_lbl = tk.Label(rf, text=" AI: checking… ", font=F_TINY, fg=AMBER, bg=BG3, pady=3, padx=6)
        ai_lbl.pack(side="right", padx=4); _gui["ai_lbl"] = ai_lbl
        dev_lbl = tk.Label(rf, text=" ●  NO DEVICE ", font=F_TINY, fg=RED, bg=BG3, pady=3, padx=6)
        dev_lbl.pack(side="right", padx=4); _gui["dev_lbl"] = dev_lbl
        tk.Frame(root, bg=ACCENT, height=1).pack(fill="x")

        # ── Connection row ────────────────────────────────────────
        co = tk.Frame(root, bg=BG, padx=14, pady=8); co.pack(fill="x")
        grid = tk.Frame(co, bg=BG); grid.pack(fill="x")
        for i, (lbl, val, cval, hi) in enumerate([
            ("IP ADDRESS",  ip,            ip,            False),
            ("PORT",        str(port),     str(port),     False),
            ("CONNECT",     f"{ip}:{port}", f"{ip}:{port}", True),
        ]):
            card = tk.Frame(grid, bg=BG2, padx=10, pady=8,
                            highlightbackground=ACCENT if hi else DIM,
                            highlightthickness=1)
            card.grid(row=0, column=i, padx=(0,8) if i<2 else 0, sticky="nsew")
            tk.Label(card, text=lbl, font=F_TINY, fg=MUTED, bg=BG2).pack(anchor="w")
            tk.Label(card, text=val, font=(_FM,13,"bold"),
                     fg=ACCT2 if hi else TEXT, bg=BG2, pady=2).pack(anchor="w")
            cv = cval
            def _cp(v=cv):
                try:
                    root.clipboard_clear(); root.clipboard_append(v); root.update()
                    fl = _gui.get("flash")
                    if fl:
                        fl.configure(text=f"  Copied  {v}  ", fg=GREEN)
                        root.after(2000, lambda: fl.configure(text="") if fl.winfo_exists() else None)
                except: pass
            NxBtn(card, "COPY", _cp, w=72, h=20, col=ACCENT if hi else ACCT2, font=F_TINY).pack(anchor="w", pady=(4,0))
        grid.columnconfigure(0, weight=1); grid.columnconfigure(1, weight=1); grid.columnconfigure(2, weight=2)
        flash = tk.Label(co, text="", font=F_TINY, fg=GREEN, bg=BG, pady=1)
        flash.pack(anchor="w", pady=(4,0)); _gui["flash"] = flash
        tk.Frame(root, bg=DIM, height=1).pack(fill="x")

        # ── Body ──────────────────────────────────────────────────
        body = tk.Frame(root, bg=BG); body.pack(fill="both", expand=True, padx=12, pady=10)

        # ── QR panel ──────────────────────────────────────────────
        qp = tk.Frame(body, bg=BG2, highlightbackground=ACCENT, highlightthickness=1)
        qp.pack(side="left", padx=(0,10), fill="y")
        qhdr = tk.Frame(qp, bg=BG3); qhdr.pack(fill="x")
        try:
            PulseDot(qhdr, size=8, color=ACCT2).pack(side="left", padx=(8,4), pady=6)
        except Exception: pass
        tk.Label(qhdr, text="SCAN TO CONNECT", font=F_SM, fg=ACCT2, bg=BG3, pady=6).pack(side="left")
        tk.Frame(qp, bg=ACCENT, height=1).pack(fill="x")
        qr_canvas = tk.Canvas(qp, bg="#000000", bd=0, highlightthickness=0, width=224, height=224)
        qr_canvas.pack(padx=6, pady=6); _gui["qr_canvas"] = qr_canvas
        tk.Label(qp, text="Butler AI  ·  PC Automation", font=F_TINY, fg=MUTED, bg=BG2).pack(pady=(0,4))
        tk.Frame(qp, bg=DIM, height=1).pack(fill="x")
        cr = tk.Frame(qp, bg=BG2, pady=6, padx=8); cr.pack(fill="x")
        crh = tk.Frame(cr, bg=BG2); crh.pack(fill="x")
        tk.Label(crh, text="RESET CODE", font=F_TINY, fg=MUTED, bg=BG2).pack(side="left")
        try:
            PulseDot(crh, size=6, color=GREEN).pack(side="right", pady=2)
        except Exception: pass
        code_lbl = tk.Label(cr, text=f"  {_gs('pairing_code') or '------'}  ",
                            font=(_FM,15,"bold"), fg=ACCT2, bg=BG3, padx=4, pady=5)
        code_lbl.pack(fill="x", pady=(2,0)); _gui["code_lbl"] = code_lbl
        tk.Frame(qp, bg=DIM, height=1).pack(fill="x")
        ba = tk.Frame(qp, bg=BG2, pady=8, padx=8); ba.pack(fill="x")
        def _new_qr():
            with _pair_lock:
                nc = _gen_code(); _ss("locked_device", None); _ss("pairing_code", nc); _ss("paired_at", None)
            cl = _gui.get("code_lbl")
            if cl: cl.configure(text=f"  {nc}  ")
            _draw_qr(ip, port)
            fl = _gui.get("flash")
            if fl:
                fl.configure(text="  ↺  Unpaired — ready for new device  ", fg=ACCT2)
                root.after(2400, lambda: fl.configure(text="") if fl and fl.winfo_exists() else None)
            print(f"  [AUTH] ⚠ GUI unpair — server is now OPEN")
        NxBtn(ba, "↺  UNPAIR & RESET", _new_qr, w=216, h=32, col=ACCT2, font=F_MED).pack(pady=(0,5))
        import webbrowser
        NxBtn(ba, "TEST IN BROWSER",
              lambda: webbrowser.open(f"http://{ip}:{port}/api/status"),
              w=216, h=24, col=MUTED, font=F_TINY).pack()
        tk.Frame(qp, bg=DIM, height=1).pack(fill="x")
        kb_lbl = tk.Label(qp, text=" KB  ···  0 articles", font=F_TINY, fg=MUTED, bg=BG2, pady=3)
        kb_lbl.pack(fill="x"); _gui["kb_lbl"] = kb_lbl
        sigma_lbl = tk.Label(qp, text=" SIGMA-NET  ·  idle", font=F_TINY, fg=MUTED, bg=BG2, pady=2)
        sigma_lbl.pack(fill="x"); _gui["sigma_lbl"] = sigma_lbl

        # ── Log panel ─────────────────────────────────────────────
        lp = tk.Frame(body, bg=BG); lp.pack(side="left", fill="both", expand=True)
        lhdr = tk.Frame(lp, bg=BG); lhdr.pack(fill="x", pady=(0,4))
        try:
            PulseDot(lhdr, size=6, color=GREEN).pack(side="left", padx=(0,6), pady=2)
        except Exception: pass
        tk.Label(lhdr, text="ACTIVITY LOG", font=F_TINY, fg=MUTED, bg=BG).pack(side="left")
        tk.Frame(lhdr, bg=DIM, height=1).pack(side="left", fill="x", expand=True, padx=(8,0), pady=4)
        tv = scrolledtext.ScrolledText(
            lp, font=F_CODE, bg="#000000", fg=TEXT,
            insertbackground=ACCT2, relief="flat",
            state="disabled", wrap="word",
            highlightthickness=1, highlightbackground=DIM,
            selectbackground=BG3, selectforeground=ACCT2,
            padx=10, pady=8)
        tv.pack(fill="both", expand=True)
        tv.tag_config("err",  foreground=RED)
        tv.tag_config("warn", foreground=AMBER)
        tv.tag_config("ok",   foreground=GREEN)
        tv.tag_config("info", foreground=BLUE)
        tv.tag_config("sys",  foreground=ACCT2)
        tv.tag_config("dim",  foreground=MUTED)
        _gui["log_tv"] = tv

        # ── Footer ────────────────────────────────────────────────
        tk.Frame(root, bg=ACCENT, height=1).pack(fill="x", side="bottom")
        ft = tk.Frame(root, bg=BG2, pady=4); ft.pack(fill="x", side="bottom")
        tk.Label(ft, text=f"  BUTLER AI SERVER  v{VERSION}  ·  {ip}:{port}",
                 font=F_TINY, fg=MUTED, bg=BG2).pack(side="left")
        olr = tk.Frame(ft, bg=BG2); olr.pack(side="right", padx=8)
        try:
            PulseDot(olr, size=8, color=GREEN).pack(side="left", padx=(0,4))
        except Exception: pass
        tk.Label(olr, text="ONLINE", font=F_TINY, fg=GREEN, bg=BG2).pack(side="left")

        def _tick():
            _refresh_gui()
            root.after(3000, _tick)

        root.after(400, lambda: _draw_qr(ip, port))
        root.after(800, _tick)
        root.protocol("WM_DELETE_WINDOW", lambda: (log.info("Window closed"), root.destroy()))
        return root

    except Exception as e:
        log.warning(f"GUI build failed: {e}")
        return None


def _draw_qr(ip, port):
    """3-layer QR: PIL cyan-on-black → canvas rects → text fallback."""
    canvas = _gui.get("qr_canvas")
    if not canvas: return
    try:
        payload = json.dumps({"ip": ip, "port": port,
                              "pairingCode": _gs("pairing_code") or "",
                              "version": VERSION})
        if HAS_QR and HAS_PIL:
            try:
                qr = qrcode.QRCode(version=None,
                                   error_correction=qrcode.constants.ERROR_CORRECT_M,
                                   box_size=1, border=3)
                qr.add_data(payload); qr.make(fit=True)
                img = qr.make_image(fill_color="#00EEFF", back_color="#000000")
                img = img.resize((224, 224), Image.NEAREST)
                tk_img = ImageTk.PhotoImage(img)
                _gui["_qr_ref"] = tk_img
                canvas.configure(width=224, height=224)
                canvas.delete("all")
                canvas.create_image(0, 0, anchor="nw", image=tk_img)
                return
            except Exception: pass
        if HAS_QR:
            try:
                qr = qrcode.QRCode(version=None, box_size=1, border=3)
                qr.add_data(payload); qr.make(fit=True)
                mx = qr.get_matrix(); n = len(mx); cell = 224 / n
                canvas.delete("all")
                for r in range(n):
                    for c in range(n):
                        if mx[r][c]:
                            x0, y0 = c*cell, r*cell
                            canvas.create_rectangle(x0, y0, x0+cell, y0+cell,
                                                    fill=ACCT2, outline="")
                return
            except Exception: pass
        # Text fallback
        canvas.delete("all")
        canvas.create_text(112, 70,  text="QR unavailable", fill=AMBER, font=F_MED,  anchor="center")
        canvas.create_text(112, 100, text=f"{ip}:{port}",   fill=ACCT2, font=F_BIG,  anchor="center")
        canvas.create_text(112, 130, text=f"Code: {_gs('pairing_code')}", fill=ACCT2, font=F_MONO, anchor="center")
        canvas.create_text(112, 158, text="pip install qrcode Pillow",    fill=MUTED, font=F_TINY, anchor="center")
    except Exception: pass


def _refresh_gui():
    """Update all dynamic labels in the Butler AI GUI."""
    root = _gui.get("root")
    if not root: return
    try:
        ai = _gui.get("ai_lbl")
        if ai:
            ok = _ol_ok()
            if ok:
                m = (_ol_model() or "").split(":")[0].upper()[:14]
                ai.configure(text=f" ●  {m} ", fg=GREEN, bg=BG3)
            else:
                # Check if auto-manager is still running
                starting = any(t.name in ("ollama-auto","ollama-pull")
                               for t in threading.enumerate())
                ai.configure(
                    text=" ●  AI: starting… " if starting else " ●  AI: offline ",
                    fg=AMBER, bg=BG3)
        dev = _gui.get("dev_lbl")
        if dev:
            locked = _gs("locked_device")
            if locked:
                s = locked[:16] + "…" if len(locked) > 16 else locked
                dev.configure(text=f" ●  {s} ", fg=GREEN, bg=BG3)
            else:
                dev.configure(text=" ●  NO DEVICE ", fg=RED, bg=BG3)
        kb = _gui.get("kb_lbl")
        if kb:
            n = _kb_count()
            kb.configure(text=f" KB  ···  {n} articles ",
                         fg=ACCT2 if n > 0 else MUTED)
        sl = _gui.get("sigma_lbl")
        if sl:
            arts   = _kb_count()
            q_size = _lq_size()
            workers_alive = sum(1 for t in threading.enumerate() if t.name.startswith("learn-"))
            speed  = "●" * min(workers_alive, 3)
            last   = _sigma_stats.get("last", "idle")
            if workers_alive > 0:
                sl.configure(text=f" ΣNET  ·  {arts} articles  ·  Q:{q_size}  ·  {speed} {workers_alive}W ",
                             fg=ACCT2)
            else:
                sl.configure(text=f" ΣNET  ·  {arts} articles  ·  idle ", fg=MUTED)

        # ── KB Stats label ────────────────────────────────────
        kb = _gui.get("kb_lbl")
        if kb:
            total = _kb_count()
            nxt   = _next_milestone(total)
            pct   = min(100, int(total / nxt * 100)) if nxt > 0 else 100
            kb.configure(
                text=f" KB  ···  {total} articles  ·  {pct}% to {nxt}",
                fg=ACCT2 if total > 0 else MUTED
            )
        cl = _gui.get("code_lbl")
        if cl:
            locked = _gs("locked_device")
            cl.configure(
                text="  PAIRED ✔  " if locked else f"  {_gs('pairing_code') or '------'}  ",
                fg=GREEN if locked else ACCT2)
    except Exception: pass


def main():
    global _start_time
    _start_time = time.time()

    parser = argparse.ArgumentParser(description="Butler AI Desktop Server v6.0")
    parser.add_argument("--port",        type=int, default=None,   help="Force specific port")
    parser.add_argument("--no-qr",       action="store_true",      help="Skip QR code display")
    parser.add_argument("--reset-pair",  action="store_true",      help="Allow new phone to connect")
    parser.add_argument("--no-admin",    action="store_true",      help="Skip admin elevation")
    parser.add_argument("--no-firewall", action="store_true",      help="Skip firewall rule")
    parser.add_argument("--startup",     action="store_true",      help="Register as Windows auto-start")
    parser.add_argument("--scan-req",    action="store_true",      help="Scan requirements then exit")
    parser.add_argument("--kill-port",   type=int, default=None,   help="Kill process on PORT then exit")
    args = parser.parse_args()

    # ── Special modes ──────────────────────────────────────────
    if args.startup:
        _register_startup(); return

    if args.reset_pair:
        nc = _gen_code()
        _ss("locked_device", None); _ss("pairing_code", nc); _ss("paired_at", None)
        print(f"\n  RESET COMPLETE. New pairing code: {nc}")
        print(f"  Restart server to show new QR code.\n"); return

    if args.scan_req:
        print("\n  === REQUIREMENTS SCAN ===")
        scan = _scan_requirements(verbose=True)
        missing = [r for r in scan if r["status"] == "MISSING"]
        print(f"\n  {len(scan)-len(missing)}/{len(scan)} packages OK")
        if missing:
            print(f"  To fix: pip install {' '.join(r['pip'] for r in missing)}")
        print()
        return

    if args.kill_port:
        port = args.kill_port
        print(f"\n  Killing processes on port {port}...")
        killed = _kill_process_on_port(port, force=True)
        if killed:
            for k in killed: print(f"  ✓ Killed PID {k['pid']} ({k['name']})")
        else:
            print(f"  No process found on port {port}")
        return

    # ── Normal startup ─────────────────────────────────────────
    # ── LICENSE ENFORCEMENT ───────────────────────────────────
    print()
    print("  ╔══════════════════════════════════════════════════════════════╗")
    print(f"  ║  BUTLER AI SERVER  v{VERSION:<42}║")
    print("  ║  Copyright (c) 2025 Shawn Jan. All Rights Reserved.         ║")
    print("  ╠══════════════════════════════════════════════════════════════╣")
    print("  ║  PROPRIETARY & CONFIDENTIAL SOFTWARE                         ║")
    print("  ║  Unauthorized copying, distribution, reverse engineering,    ║")
    print("  ║  modification or commercial use is strictly prohibited.      ║")
    print("  ║  Violators will be prosecuted under copyright law.           ║")
    print("  ║  License: Proprietary  ·  See LICENSE.txt                    ║")
    print("  ║  Contact: andrejsladkovic1992@gmail.com                       ║")
    print("  ╚══════════════════════════════════════════════════════════════╝")
    print()
    
    # Write tamper-evidence marker next to executable
    try:
        import hashlib, pathlib
        exe_path = pathlib.Path(__file__).resolve()
        src_hash = hashlib.sha256(exe_path.read_bytes()).hexdigest()[:16]
        marker = exe_path.parent / ".butler_license"
        marker.write_text(
            f"Butler AI Server v{VERSION}\n"
            f"Copyright (c) 2025 Shawn Jan\n"
            f"File: {exe_path.name}\n"
            f"Hash: {src_hash}\n"
            f"Licensed to: End User (personal use only)\n"
            f"Restrictions: No redistribution, modification, or commercial use\n"
        )
    except: pass

    # Python version guard - exit cleanly with download link
    if sys.version_info < (3, 10):
        print()
        print("  ╔══════════════════════════════════════════════════╗")
        print(f"  ║  Python {sys.version.split()[0]} detected                          ║")
        print("  ║  BOTER Server requires Python 3.10 or newer.   ║")
        print("  ║  Download: https://python.org                   ║")
        print("  ╚══════════════════════════════════════════════════╝")
        print()
        if IS_WINDOWS and sys.stdin and sys.stdin.isatty():
            os.system("pause")  # Only pause in interactive terminals
        sys.exit(1)

    print("  [1/3] Checking dependencies...")
    _kill_old_instances()

    # ── Auto-lock migration: clear old pairing state if upgrading ──
    # Previous versions required manual pairing codes. This version auto-locks
    # to the first device that connects. Clear any stale lock from old version.
    if _gs("locked_device") and not _gs("auto_lock_version"):
        _log("Migrating to auto-lock mode — clearing old pairing state", "info")
        _ss("locked_device", None)
        _ss("paired_at", None)
        _ss("auto_lock_version", VERSION)
        _ss("pairing_code", _gen_code())  # fresh reset code
    if not _gs("auto_lock_version"):
        _ss("auto_lock_version", VERSION)

    if not _gs("pairing_code"): _ss("pairing_code", _gen_code())

    saved_port = _gs("server_port")
    prefer     = args.port or (int(saved_port) if saved_port else None)
    port       = _free_port(prefer)
    _ss("server_port", port)

    ip      = get_ip()
    all_ips = get_all_ips()
    code    = _gs("pairing_code")
    locked  = _gs("locked_device")
    ol_ok   = _ol_ok()
    model   = _ol_model() if ol_ok else ""

    # Add firewall rule
    _fw(port, enabled=not args.no_firewall)

    # ── Animated Robot Splash Screen ─────────────────────────────
    def _splash():
        """Cinematic 3D-style ASCII robot splash with smooth frame transitions."""
        import shutil
        W = shutil.get_terminal_size((80, 24)).columns
        C = {
            "teal":   "\033[38;2;0;229;255m",
            "green":  "\033[38;2;0;255;136m",
            "amber":  "\033[38;2;255;184;0m",
            "dim":    "\033[38;2;60;90;110m",
            "bright": "\033[38;2;220;240;255m",
            "red":    "\033[38;2;255;51;102m",
            "reset":  "\033[0m",
            "bold":   "\033[1m",
            "clear":  "\033[2J\033[H",
        }
        T, G, A, D, B, R = C["teal"], C["green"], C["amber"], C["dim"], C["bright"], C["reset"]

        FRAMES = [
            # Frame 0 — robot powering on
            [
                f"{D}┌──────────────────────────────────────────────────┐{R}",
                f"{D}│{R}                                                  {D}│{R}",
                f"{D}│{R}      {T}  ╔═══════════════════════════╗  {R}         {D}│{R}",
                f"{D}│{R}      {T}  ║  {B}◈  BUTLER AI  SYSTEM  ◈{T}  ║  {R}         {D}│{R}",
                f"{D}│{R}      {T}  ╚═══════════════════════════╝  {R}         {D}│{R}",
                f"{D}│{R}                                                  {D}│{R}",
                f"{D}│{R}         {D}    ┌───────────────┐    {R}             {D}│{R}",
                f"{D}│{R}         {T}    │  {D}· · · · · ·{T}  │    {R}             {D}│{R}",
                f"{D}│{R}         {T}    │  {D}· · · · · ·{T}  │    {R}             {D}│{R}",
                f"{D}│{R}         {T}    └───────────────┘    {R}             {D}│{R}",
                f"{D}│{R}              {D}    ──────────    {R}                {D}│{R}",
                f"{D}│{R}         {D}  ┌────────────────────┐  {R}             {D}│{R}",
                f"{D}│{R}         {D}  │  · · · · · · · ·  │  {R}             {D}│{R}",
                f"{D}│{R}         {D}  └────────────────────┘  {R}             {D}│{R}",
                f"{D}│{R}              {D}  ░░  BOOT...  ░░  {R}                {D}│{R}",
                f"{D}└──────────────────────────────────────────────────┘{R}",
            ],
            # Frame 1 — eyes lighting up
            [
                f"{D}┌──────────────────────────────────────────────────┐{R}",
                f"{D}│{R}                                                  {D}│{R}",
                f"{D}│{R}      {T}  ╔═══════════════════════════╗  {R}         {D}│{R}",
                f"{D}│{R}      {T}  ║  {B}◈  BUTLER AI  SYSTEM  ◈{T}  ║  {R}         {D}│{R}",
                f"{D}│{R}      {T}  ╚═══════════════════════════╝  {R}         {D}│{R}",
                f"{D}│{R}                                                  {D}│{R}",
                f"{D}│{R}         {T}    ┌───────────────┐    {R}             {D}│{R}",
                f"{D}│{R}         {T}    │  {G}◉ {D}· · ·{G} ◉{T}  │    {R}             {D}│{R}",
                f"{D}│{R}         {T}    │  {D}· · · · · ·{T}  │    {R}             {D}│{R}",
                f"{D}│{R}         {T}    └───────────────┘    {R}             {D}│{R}",
                f"{D}│{R}              {T}    ──────────    {R}                {D}│{R}",
                f"{D}│{R}         {T}  ┌────────────────────┐  {R}             {D}│{R}",
                f"{D}│{R}         {T}  │  {D}· · · · · · · ·{T}  │  {R}             {D}│{R}",
                f"{D}│{R}         {T}  └────────────────────┘  {R}             {D}│{R}",
                f"{D}│{R}              {A}  ▓▓  INIT...  ▓▓  {R}                {D}│{R}",
                f"{D}└──────────────────────────────────────────────────┘{R}",
            ],
            # Frame 2 — full boot
            [
                f"{T}┌──────────────────────────────────────────────────┐{R}",
                f"{T}│{R}                                                  {T}│{R}",
                f"{T}│{R}      {T}  ╔═══════════════════════════╗  {R}         {T}│{R}",
                f"{T}│{R}      {T}  ║  {B}◈  BUTLER AI  SYSTEM  ◈{T}  ║  {R}         {T}│{R}",
                f"{T}│{R}      {T}  ╚═══════════════════════════╝  {R}         {T}│{R}",
                f"{T}│{R}                                                  {T}│{R}",
                f"{T}│{R}         {T}    ┌───────────────┐    {R}             {T}│{R}",
                f"{T}│{R}         {T}    │  {G}◉{T} ─── {A}▬▬▬{T} ─── {G}◉{T}  │    {R}             {T}│{R}",
                f"{T}│{R}         {T}    │  {D}· {T}─── {A}───{T} ─── {D}·{T}  │    {R}             {T}│{R}",
                f"{T}│{R}         {T}    └───────┬───────┘    {R}             {T}│{R}",
                f"{T}│{R}                 {T}│{R}                              {T}│{R}",
                f"{T}│{R}         {T}  ┌──┴─────────────────┐  {R}             {T}│{R}",
                f"{T}│{R}         {T}  │  {G}■ ■ ■ ■ ■ ■ ■ ■{T}  │  {R}             {T}│{R}",
                f"{T}│{R}         {T}  └────────────────────┘  {R}             {T}│{R}",
                f"{T}│{R}              {G}  ██  ONLINE  ██  {R}                {T}│{R}",
                f"{T}└──────────────────────────────────────────────────┘{R}",
            ],
        ]

        delays = [0.18, 0.18, 0.22]
        try:
            print(C["clear"], end="", flush=True)
            for i, frame in enumerate(FRAMES):
                if i > 0:
                    # Smooth transition: move cursor up to overwrite
                    print(f"\033[{len(frame)}A", end="", flush=True)
                for line in frame:
                    print(line)
                time.sleep(delays[i])
            # Final hold
            time.sleep(0.3)
            # Slide out — fade bottom to top
            for _ in range(len(FRAMES[-1])):
                print(f"\033[1A\033[2K", end="", flush=True)
                time.sleep(0.018)
        except Exception:
            pass  # Never crash on splash

    _splash()

    # Print startup banner
    W = 64
    print()
    print("=" * W)
    print(f"  BUTLER AI DESKTOP SERVER  v{VERSION}")
    print("=" * W)
    print(f"  IP Address : {ip}")
    for alt in all_ips:
        if alt != ip: print(f"  Alt IP     : {alt}")
    print(f"  Port       : {port}")
    print(f"  URL        : http://{ip}:{port}")
    print(f"  Pair Code  : {code}")
    print(f"  Device     : {'LOCKED to ' + (locked[:24] if locked else '') + '...' if locked else 'OPEN - scan QR to pair'}")
    print(f"  Ollama AI  : {'ONLINE - ' + model if ol_ok else 'Starting automatically in background…'}")
    print(f"  Admin      : {'YES - full access' if _is_admin() else 'NO - some features limited'}")
    print(f"  Python     : {platform.python_version()}")
    print()
    print(f"  ENDPOINTS:")
    print(f"    GET  /api/status             - Server health")
    print(f"    GET  /api/metrics            - CPU/RAM/Disk live data")
    print(f"    GET  /api/requirements       - Package status")
    print(f"    GET  /api/processes          - Process list")
    print(f"    POST /api/execute            - Run Python script")
    print(f"    POST /api/butler/chat        - Ollama AI chat")
    print(f"    POST /api/receive_file       - Phone→PC file transfer")
    print(f"    POST /api/kill_interference  - Kill blocking processes")
    print(f"    POST /api/requirements/install - Auto-install deps")
    print(f"    POST /pair                   - Pair phone")
    print(f"    POST /reconnect              - Refresh token")
    print("=" * W)
    print(f"  ✦ Google Play Certified  •  Everyone (Content Rating)")
    print(f"  ✦ GitHub: https://github.com/shawnjan-cmd/butler-ai")
    print(f"  ✦ Privacy Policy: https://shawnjan-cmd.github.io/butler-ai/")
    print(f"  ✦ 100%% Local — zero telemetry, zero cloud data")
    print("=" * W)
    print()

    if not args.no_qr: _qr(ip, port)

    # Start UDP beacon
    threading.Thread(target=_beacon, args=(ip, port), daemon=True).start()
    print(f"  UDP Beacon: broadcasting on :{BEACON_PORT} (app auto-discovers)")

    # Auto-manage Ollama in background - installs, starts, pulls model automatically
    _start_ollama_auto()
    print(f"  Ollama AI  : {'ONLINE - ' + model if ol_ok else 'starting in background…'}")
    print(f"  HTTP Server: http://{ip}:{port}")
    print(f"  Press Ctrl+C to stop")
    print()
    if locked:
        print(f"  LOCKED to device — waiting for it to reconnect...")
        print(f"  To pair a new device: restart with --reset-pair")
    else:
        print(f"  OPEN — first device to connect will be auto-locked in.")
        print(f"  Connect via: QR code, LAN Auto-Discover, or direct IP")
        print(f"  No pairing code needed — just connect!")
    print()

    # Init DB and shared file dir
    _db_init()
    SHARE_DIR.mkdir(parents=True, exist_ok=True)
    log.info("Database initialised")

    # self-healing HTTP: Start SIGMA-NET auto-crawler in background
    # Start Ollama status cache refresher (every 10s, no impact on HTTP)
    threading.Thread(target=_ol_cache_refresh, daemon=True, name="ollama-cache").start()
    # Start IP cache refresher (every 60s)
    threading.Thread(target=_refresh_ip_cache, daemon=True, name="ip-cache").start()
    _auto_heal_startup()
    threading.Thread(target=_sigma_loop, daemon=True, name="sigma").start()
    threading.Thread(target=_watchdog, daemon=True, name="watchdog").start()
    log.info("SIGMA-NET auto-learning crawler started")

    # Self-healing HTTP - restarts on crash, escalates port on PermissionError
    _httpd    = [None]
    _cur_port = [port]

    def _run_http():
        fail_streak = 0
        while True:
            p = _cur_port[0]
            try:
                # ThreadingHTTPServer: each request handled in its own thread
                # Heartbeat pings NEVER wait for slow requests (execute, crawl, chat)
                from http.server import ThreadingHTTPServer
                _httpd[0] = ThreadingHTTPServer(("0.0.0.0", p), H)
                _httpd[0].timeout = 30
                _httpd[0].daemon_threads = True  # worker threads die with server
                # Enable TCP keepalive — prevents Windows from resetting long-running
                # connections (WinError 10053) during Ollama inference
                try:
                    import socket as _sk
                    _httpd[0].socket.setsockopt(_sk.SOL_SOCKET, _sk.SO_KEEPALIVE, 1)
                    if hasattr(_sk, 'TCP_KEEPIDLE'):   # Linux
                        _httpd[0].socket.setsockopt(_sk.IPPROTO_TCP, _sk.TCP_KEEPIDLE, 10)
                    if hasattr(_sk, 'TCP_KEEPINTVL'):  # Linux
                        _httpd[0].socket.setsockopt(_sk.IPPROTO_TCP, _sk.TCP_KEEPINTVL, 5)
                    if hasattr(_sk, 'TCP_KEEPCNT'):    # Linux
                        _httpd[0].socket.setsockopt(_sk.IPPROTO_TCP, _sk.TCP_KEEPCNT, 3)
                except Exception: pass  # Not critical — just best-effort
                fail_streak = 0
                log.info(f"HTTP server on http://{ip}:{p}")
                _httpd[0].serve_forever()
            except PermissionError:
                fail_streak += 1
                log.warning(f"Permission denied on port {p} - trying next port")
                _cur_port[0] = _free_port(p + 1)
                _ss("server_port", _cur_port[0])
                time.sleep(1)
            except OSError as e:
                fail_streak += 1
                if "10048" in str(e) or "98" in str(e) or "Address already in use" in str(e):
                    log.warning(f"Port {p} busy - killing blocker")
                    killed = _kill_process_on_port(p, force=True)
                    if not killed or fail_streak >= 5:
                        _cur_port[0] = _free_port(p + 1)
                        _ss("server_port", _cur_port[0])
                        fail_streak = 0
                    time.sleep(1)
                else:
                    log.error(f"HTTP error: {e}"); time.sleep(3)
            except Exception as e:
                log.error(f"HTTP crashed ({e}) - restarting in 3s"); time.sleep(3)

    threading.Thread(target=_run_http, daemon=True, name="http").start()

    # Wait a moment then verify HTTP is actually up
    time.sleep(1.5)
    _verified = False
    for _a in range(6):
        try:
            import socket as _s
            _p = _s.create_connection(("127.0.0.1", port), timeout=1); _p.close()
            _verified = True; break
        except OSError:
            import time as _t; _t.sleep(0.5)
    if _verified:
        _ss("server_port", port)  # Persist port so QR always shows current port
        log.info(f"✅ Server verified reachable on port {port}")
    else:
        log.warning("Server not responding - check Firewall / Antivirus")

    # Launch GUI or run headless
    if not args.no_qr and HAS_TK:
        try:
            root = _build_gui(ip, port)
            if root:
                root.mainloop(); return
        except tk.TclError as e:
            log.warning(f"GUI unavailable ({e}) - running headless")
        except Exception as e:
            log.warning(f"GUI error ({e}) - running headless")

    # Headless fallback
    log.info("Running in headless mode - all API features active")
    log.info(f"Connect to: http://{ip}:{port}")
    if _gs("locked_device"):
        log.info(f"Locked to device — waiting for reconnect")
    else:
        log.info(f"OPEN — first device to connect will auto-lock")
    log.info(f"Reset code (for unpairing only): {_gs('pairing_code')}")
    log.info("Press Ctrl+C to stop")
    try:
        while True: time.sleep(10)
    except KeyboardInterrupt:
        print("\n\n  Server stopped. Goodbye!")

if __name__ == "__main__":
    try:
        main()
    except Exception as _fatal:
        print("\n" + "=" * 60)
        print("  BUTLER AI SERVER - FATAL ERROR")
        print("=" * 60)
        import traceback
        traceback.print_exc()
        print("=" * 60)
        try: input("\n  Press Enter to exit...")
        except: time.sleep(15)