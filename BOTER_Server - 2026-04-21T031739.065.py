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
import argparse, base64, hashlib, hmac, json, os, platform, random
import socket, subprocess, sys, threading, time, uuid, signal
import sqlite3, re, mimetypes, logging
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
from collections import deque
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

VERSION        = "7.0.0"
CRAWL_WORKERS  = 2    # same as WORKER_THREADS — kept for compatibility
CRAWL_TIMEOUT  = 18
HARVEST_SECS   = 45 * 60   # auto-learn every 45 minutes
SHARE_DIR      = Path.home() / "boter_shared"
DB_PATH        = Path.home() / ".butler_server_v7.db"

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
DEFAULT_MODEL  = os.environ.get("BUTLER_MODEL", "qwen2.5-coder:7b")

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
STATE_FILE     = Path.home() / ".butler_server_state_v7.json"
SECRET_FILE    = Path.home() / ".butler_server_secret_v7.bin"

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
    missing = [r["pip"] for r in scan if r["status"] == "MISSING"]
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

def _ss(k, v):
    with _sl:
        _state[k] = v
        # Async disk write - never blocks HTTP handler
        threading.Thread(target=_save_state, args=(_state.copy(),),
                         daemon=True, name="state-save").start()

# ══════════════════════════════════════════════════════
#  FIREWALL
# ══════════════════════════════════════════════════════
def _fw(port, enabled=True):
    if not enabled: return
    if IS_WINDOWS:
        name = f"Cyber-Botler v7 port {port}"
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
                "type":        "butler_beacon",
                "ip":          ip,
                "allIPs":      all_ips,
                "port":        port,
                "pairingCode": _gs("pairing_code") or "",
                "version":     VERSION,
                "locked":      bool(_gs("locked_device")),
                "os":          platform.system(),
                "ts":          int(time.time()),
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
                    m  = ms[0]["name"] if ms else ""
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
        body = json.dumps({"model": model, "messages": msgs, "stream": False}).encode()
        req  = urllib.request.Request(
            f"{OLLAMA_URL}/api/chat", data=body,
            headers={"Content-Type": "application/json"}, method="POST"
        )
        with urllib.request.urlopen(req, timeout=120) as r:
            d = json.loads(r.read())
        return d.get("message", {}).get("content", "No response.")
    except urllib.error.HTTPError as e:
        if e.code == 404:
            return (f"MODEL_NOT_INSTALLED: \'{model}\' is not installed.\n\n"
                    f"Run: ollama pull {model}")
        return f"[Ollama error] HTTP {e.code}: {e.reason}"
    except urllib.error.URLError:
        return ("Butler AI is offline - Ollama not running.\n\n"
                f"1. Download: https://ollama.ai\n2. Run: ollama pull {model}")
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
        tmp = tempfile.mktemp(suffix=".exe")
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


def _pick_best_model() -> str:
    """
    Auto-select the best Ollama model based on available RAM.
    Bigger model = smarter answers but needs more RAM.
    
    If user set BUTLER_MODEL env var, that overrides auto-selection.
    
    RAM thresholds:
      16GB+ → qwen2.5-coder:7b   (best quality, ~4.7GB model)
      10GB+ → qwen2.5-coder:7b   (tight but works)
       6GB+ → qwen2.5-coder:3b   (good quality, ~2GB model)
       4GB+ → qwen2.5-coder:1.5b (decent, ~1GB model)
       <4GB → tinyllama           (basic, ~0.6GB model)
    """
    # If user explicitly set a model, respect that
    if os.environ.get("BUTLER_MODEL"):
        return os.environ["BUTLER_MODEL"]
    
    if not HAS_PSUTIL:
        return "qwen2.5-coder:7b"  # default when can't check RAM
    
    try:
        total_gb = psutil.virtual_memory().total / (1024**3)
        avail_gb = psutil.virtual_memory().available / (1024**3)
        
        # Use available RAM (not total) — respects what's actually free
        if avail_gb >= 8 or total_gb >= 16:
            best = "qwen2.5-coder:7b"
        elif avail_gb >= 5 or total_gb >= 10:
            best = "qwen2.5-coder:7b"
        elif avail_gb >= 3 or total_gb >= 6:
            best = "qwen2.5-coder:3b"
        elif avail_gb >= 2 or total_gb >= 4:
            best = "qwen2.5-coder:1.5b"
        else:
            best = "tinyllama"
        
        log.info(f"[MODEL] RAM: {total_gb:.1f}GB total, {avail_gb:.1f}GB free → selected: {best}")
        return best
    except:
        return DEFAULT_MODEL


def _cleanup_unused_models(keep_model: str):
    """
    Remove Ollama models that aren't the active one.
    Saves disk space — each model is 1-5GB.
    Only runs after successful model pull.
    """
    try:
        installed = _ol_models()
        if len(installed) <= 1: return  # nothing to clean
        
        keep_base = keep_model.split(":")[0].lower()
        for m in installed:
            m_base = m.split(":")[0].lower()
            if m_base == keep_base or m.lower() == keep_model.lower():
                continue  # keep the active model
            # Delete unused model
            try:
                exe = _find_ollama_exe() or "ollama"
                cmd = [exe, "rm", m] if isinstance(exe, str) else ["ollama", "rm", m]
                kw = {}
                if IS_WINDOWS: kw["creationflags"] = subprocess.CREATE_NO_WINDOW
                subprocess.run(cmd, timeout=30, capture_output=True, **kw)
                log.info(f"[MODEL] Cleaned unused model: {m}")
            except: pass
    except: pass


def _ensure_model(model=None):
    """
    Pull the best model for this PC's RAM if not already installed.
    Auto-selects model size, pulls it, cleans up old models.
    """
    if model is None:
        model = _pick_best_model()
    
    # Update DEFAULT_MODEL globally so chat uses the right one
    global DEFAULT_MODEL
    DEFAULT_MODEL = model
    _ss("active_model", model)
    
    models = _ol_models()
    # Check if selected model (or its base name) is already present
    base = model.split(":")[0].lower()
    for m in models:
        if m.lower() == model.lower() or m.lower().startswith(base):
            log.info(f"✓ Model already installed: {m}")
            _log(f"AI model ready: {m}", "ok")
            # Clean up other models to save disk space
            _cleanup_unused_models(model)
            return

    log.info(f"Pulling model {model} — this takes 2-5 min depending on connection…")
    _log(f"Downloading AI model: {model} (2-5 min first time)…", "warn")
    exe = _find_ollama_exe()
    cmd = [exe, "pull", model] if exe else ["ollama", "pull", model]
    try:
        kw = {}
        if IS_WINDOWS: kw["creationflags"] = subprocess.CREATE_NO_WINDOW
        r = subprocess.run(cmd, timeout=600, **kw)
        if r.returncode == 0:
            log.info(f"✓ Model {model} downloaded and ready")
            _log(f"AI model ready: {model} ✓", "ok")
            # Clean up old models
            _cleanup_unused_models(model)
        else:
            log.warning(f"ollama pull returned {r.returncode}")
    except subprocess.TimeoutExpired:
        log.warning("Model download timed out — will retry on next start")
    except Exception as e:
        log.warning(f"Model pull error: {e}")


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
        return {
            "cpu":     {"percent": round(cpu, 1), "cores": psutil.cpu_count(logical=False), "logical": psutil.cpu_count()},
            "memory":  {"total": mem.total, "used": mem.used, "percent": round(mem.percent, 1)},
            "disk":    {"total": disk.total, "used": disk.used, "free": disk.free, "percent": round(disk.percent, 1)},
            "network": {"bytes_sent": nio.bytes_sent, "bytes_recv": nio.bytes_recv},
            "uptime":  int(time.time() - psutil.boot_time()),
            "hostname": socket.gethostname(),
            "os":      f"{platform.system()} {platform.release()}",
            "processes": procs,
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
        c.execute("PRAGMA journal_mode=WAL")
        c.execute("PRAGMA synchronous=NORMAL")
        c.execute("PRAGMA cache_size=10000")
        c.execute("PRAGMA temp_store=MEMORY")
        c.commit(); c.close()

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

WORKER_THREADS   = 2    # 2 workers = 2x faster KB growth, still lightweight
CRAWL_DELAY_SECS = 5    # 5s between crawls - fast growth, still polite
QUEUE_LOW_WATER  = 20   # refill queue when below this
CHECKPOINT_SECS  = 900  # save checkpoint every 15 minutes

# ── CPU GUARD: Ollama-aware performance management ──────
# When Ollama is processing, crawlers FULLY PAUSE (not just slow down).
# When CPU > 90%, crawlers FULLY PAUSE regardless.
# This prevents the "100% CPU" problem customers see.
_ollama_busy = False     # Set True while Ollama is processing a chat
_perf_mode   = "auto"    # "auto" | "performance" | "battery"
# performance = crawlers run full speed, auto = adaptive, battery = crawlers paused


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
        """Auth check with self-healing tokens."""
        locked = _gs("locked_device")
        if not locked: return True
        ah  = self.headers.get("Authorization", "")
        tok = ah[7:].strip() if ah.startswith("Bearer ") else ""
        if not tok:
            tok = (body or {}).get("token", self.headers.get("X-Fallback-Token", ""))
        if not tok: return False
        valid = _verify_token(tok, locked)
        if valid:
            _ss("last_seen", time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()))
            return True

        # ── Token invalid — try to self-heal ─────────────────────
        # Extract device_id from the broken token to see if it's the right device
        try:
            decoded = base64.urlsafe_b64decode(tok.encode()).decode()
            parts = decoded.rsplit(":", 1)
            if parts:
                raw_parts = parts[0].split(":")
                token_device = raw_parts[0] if raw_parts else ""
                if token_device == locked:
                    # Same device, token just expired or secret changed
                    # Auto-reissue a fresh token
                    new_tok = _make_token(locked)
                    self._healed_token = new_tok  # store for response
                    _ss("last_seen", time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()))
                    _conn_log("AUTH", locked[:20], "SELF-HEAL", "token reissued")
                    return True
        except: pass

        return False

    def do_OPTIONS(self):
        self.send_response(200)
        self._cors()
        self.end_headers()

    def do_GET(self):
        path = self.path.split("?")[0]
        body = {}  # GET requests have no body - needed so _authed(body) doesn't crash
        # Health/status/ping endpoints are NEVER rate-limited - heartbeat must always work
        if path not in ("/health", "/ping", "/api/status", "/status", "/api/pair/status", "/"):
            if not self._chkrate(): return

        # ── STATUS / HEALTH ──────────────────────────────────────
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
                "locked":      bool(locked),
                "pairingCode": _gs("pairing_code") or "" if not locked else "",
                "port":        _gs("server_port") or "",
                "cpu":         round(cpu_pct, 1),
                "ram":         round(ram_pct, 1),
                "memory":      round(ram_pct, 1),
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
        elif path == "/api/learn/status":
            tok = (self.headers.get("Authorization","")[7:].strip()
                   or self.headers.get("X-Fallback-Token",""))
            locked = _gs("locked_device")
            if locked and tok and not _verify_token(tok, locked):
                self._json({"error":"Unauthorized"},401); return
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
            })

        # ── FULL STATUS — all data in one call (reduces app round trips) ─
        elif path == "/api/status/full":
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
                "pairingCode":  _gs("pairing_code") or "",
                "allIPs":       _cached_ips,
                "python":       platform.python_version(),
                "psutil":       HAS_PSUTIL,
                "uptime":       int(time.time() - _start_time),
                "pairingCode":  _gs("pairing_code") or "",
                "serverVersion": VERSION,
                "minAppVersion":  "6.0.0",  # reject app versions older than this
                "pairingReady":   not bool(_gs("locked_device")),
                "latency":      0,
                "endpoints": ["/pair","/reconnect","/api/reset_pair",
                    "/api/status","/health","/api/handshake",
                    "/api/execute","/api/butler/chat","/api/butler/clear",
                    "/api/receive_file","/api/ollama/status","/api/ollama/pull",
                    "/api/metrics","/api/kb/search","/api/kb/enrich",
                    "/api/kb/log","/api/kb/list","/api/crawl","/api/crawl/batch",
                    "/api/fs/drives","/api/fs/crawl","/api/fs/read",
                    "/api/files","/api/download","/api/kill_interference",
                    "/api/pip/install"],
            })

        # ── METRICS ─────────────────────────────────────────────
        elif path == "/api/metrics":
            m = _metrics()
            # App reads BOTH d.cpu.percent AND d.metrics.cpu.percent (nested)
            # Also add "ram" alias for "memory" — some app versions use either
            if "memory" in m:
                m["ram"] = m["memory"]
            self._json({**m, "metrics": m, "timestamp": int(time.time())})

        # ── REQUIREMENTS SCAN ────────────────────────────────────
        elif path == "/api/requirements":
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
            procs = _list_all_processes()
            # Also check our ports
            port_info = {}
            for p in [8766, 8765, 5000, 8080, 8008]:
                blockers = _find_process_on_port(p)
                if blockers: port_info[str(p)] = blockers
            self._json({"processes": procs, "port_conflicts": port_info})

        # ── SYSINFO ──────────────────────────────────────────────
        elif path == "/api/sysinfo":
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
        elif path == "/api/ollama/status":
            if not self._authed(body): self._json({"error":"Unauthorized"},401); return
            ok    = _ol_ok()
            model = _ol_model() if ok else ""
            mods  = _ol_models() if ok else []
            # Check if auto-manager thread is still running (Ollama starting up)
            starting = not ok and any(
                t.name == "ollama-auto" for t in threading.enumerate())
            self._json({
                "available":   ok,
                "activeModel": model,
                "models":      mods,
                "starting":    starting,
                "defaultModel": DEFAULT_MODEL,
            })

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
            if not self._authed(body): self._json({"error":"Unauthorized"},401); return
            SHARE_DIR.mkdir(parents=True, exist_ok=True)
            files = [{"name": f.name, "size": f.stat().st_size,
                      "size_str": f"{f.stat().st_size//1024}KB"}
                     for f in sorted(SHARE_DIR.iterdir()) if f.is_file()]
            self._json({"files": files, "count": len(files)})

        # ── DOWNLOAD FILE ─────────────────────────────────────────
        elif path == "/api/download":
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
                    self._json({"error":"Unauthorized"},401); return
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
            if not self._authed(body): self._json({"error":"Unauthorized"},401); return
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
                _log(f"Reconnected: {device_id[:16]}…", "ok")
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
                self._json({"error": "Unauthorized - pair first via QR or Home tab"}, 401); return
            script   = (body.get("script") or body.get("code") or "").strip()
            language = (body.get("language") or "python").lower()
            if not script:
                self._json({"error": "No script provided"}, 400); return
            if len(script) > 200000:
                self._json({"error": "Script too large (max 200KB)"}, 413); return

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
                self._json({
                    "status":    "ok" if r.returncode == 0 else "error",
                    "output":    combined[:100000] if combined else "[No output]",
                    "stdout":    out[:50000],
                    "stderr":    err[:10000],
                    "exitCode":  r.returncode,
                    "exit_code": r.returncode,
                    "returncode": r.returncode,
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
        elif path == "/api/butler/chat":
            if not self._authed(body):
                self._json({"error": "Unauthorized"}, 401); return
            msg     = (body.get("message") or "").strip()
            # Use app's systemPrompt if provided, else sensible default
            system  = body.get("systemPrompt") or (
                "You are Butler AI - the world's most capable local PC automation and computer expert.\n\n"
                "You run 100%% locally on the user's PC. No cloud. Full system access.\n\n"
                "EXPERTISE - you can fix and automate EVERYTHING:\n"
                "- Windows errors, BSODs, crashes, freezes, slow PC\n"
                "- Driver problems: Device Manager errors, code 43, missing drivers\n"
                "- Firewall and network: blocked apps, port rules, DNS, WiFi issues\n"
                "- Program installation, repair, silent install, uninstall\n"
                "- Registry edits, startup programs, Windows services\n"
                "- Python automation scripts for ANY task, easy to advanced\n"
                "- File organization, batch rename, folder monitoring\n"
                "- Browser automation, web scraping, scheduled tasks\n"
                "- Hardware diagnostics: CPU, RAM, GPU, disk, temperature\n"
                "- Security: remove malware, audit permissions, harden system\n"
                "- Performance: find bottlenecks, optimize boot, clean junk\n"
                "- Office automation: Excel, Word, PDF with Python\n\n"
                "HOW TO RESPOND:\n"
                "1. COMPUTER PROBLEMS: Give the exact fix. Explain the error code,\n"
                "   its cause, and multiple solutions easiest to most thorough.\n"
                "   If Python can automate it, write the script.\n"
                "2. PYTHON SCRIPTS: Write COMPLETE runnable code. No placeholders.\n"
                "   Include imports, pip install commands, error handling, comments.\n"
                "3. DRIVER ISSUES: Identify device, give Device Manager steps,\n"
                "   write Python/PowerShell script to fix automatically.\n"
                "4. FIREWALL: Give Windows Defender steps AND netsh/PowerShell script.\n"
                "5. PERFORMANCE: Use psutil to diagnose, write cleanup script.\n"
                "6. Prefer Python automation over manual steps whenever possible.\n"
                "7. Use KB context for specific accurate answers.\n\n"
                "PYTHON LIBRARIES ALWAYS AVAILABLE:\n"
                "System: psutil, wmi, winreg, win32api, platform, subprocess, ctypes\n"
                "GUI/Input: pyautogui, keyboard, pynput, pygetwindow\n"
                "Files: pathlib, shutil, watchdog, zipfile, glob\n"
                "Schedule: schedule, apscheduler, threading.Timer\n"
                "Network: requests, paramiko, socket, scapy\n"
                "Browser: selenium, playwright, beautifulsoup4\n"
                "Office: openpyxl, python-docx, csv, sqlite3\n"
                "Notify: plyer, winsound, ctypes MessageBox\n"
                "Security: cryptography, hashlib, secrets\n"
                "Clipboard/Screen: pyperclip, Pillow\n"
                "Package Managers: winget, chocolatey, pip, scoop\n\n"
                "SCRIPT WRITING RULES:\n"
                "- For 'install X': write a Python script using subprocess to run\n"
                "  winget install X OR download the installer silently with requests\n"
                "- For 'organize files': use pathlib + shutil, never hardcode paths\n"
                "- For 'schedule task': use Windows Task Scheduler via schtasks.exe\n"
                "- For 'fix error': diagnose first with subprocess/psutil, then fix\n"
                "- For 'automate X': prefer pyautogui or keyboard over manual steps\n"
                "- Always test if software/file exists before acting on it\n"
                "- Scripts must run without admin when possible, request UAC if needed\n"
                "- Add print() progress messages so user knows what is happening\n"
                "- Save scripts to Desktop or Documents unless told otherwise"
            )
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
            kb_count_before = _kb_count()
            kb_hits = _kb_search(msg, 2)
            if kb_count_before < 50 or not kb_hits:
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

            # Track user topic for personalized learning (persistent)
            try:
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

            if not _ol_ok():
                fallback = (
                    "Butler AI is warming up.\n\n"
                    "The AI model is being downloaded and started automatically. "
                    "This takes 2-5 minutes on first run.\n\n"
                    "Please wait a moment and try again. "
                    "All other features work right now."
                )
                self._json({
                    "status": "ok", "response": fallback, "reply": fallback,
                    "message": fallback, "ollama": False, "ai": "local",
                    "ollamaModel": "", "model": model,
                }); return

            # ── STREAMING vs FULL RESPONSE ─────────────────────────
            # If app sends "stream": true, stream tokens live.
            # Otherwise, return full response (backward compatible).
            want_stream = body.get("stream", False)
            _ollama_busy = True  # Signal crawlers to PAUSE
            _chat_t0 = time.time()

            if want_stream and _ol_ok():
                # ── STREAMING MODE: tokens appear live ────────────
                try:
                    import urllib.request as _ur2
                    msgs = []
                    if system: msgs.append({"role": "system", "content": system})
                    for m2 in (hist or []): msgs.append(m2)
                    msgs.append({"role": "user", "content": full_msg})
                    ol_body = json.dumps({"model": model, "messages": msgs, "stream": True}).encode()
                    ol_req = _ur2.Request(
                        f"{OLLAMA_URL}/api/chat", data=ol_body,
                        headers={"Content-Type": "application/json"}, method="POST"
                    )
                    ol_resp = _ur2.urlopen(ol_req, timeout=180)

                    # Send HTTP headers for streaming
                    self.send_response(200)
                    self.send_header("Content-Type", "text/event-stream")
                    self.send_header("Cache-Control", "no-cache")
                    self.send_header("Connection", "keep-alive")
                    self._cors()
                    self._add_license_headers()
                    self.end_headers()

                    full_reply = []
                    for line in ol_resp:
                        try:
                            chunk = json.loads(line)
                            token = chunk.get("message", {}).get("content", "")
                            if token:
                                full_reply.append(token)
                                # Send token as SSE event
                                self.wfile.write(f"data: {json.dumps({'token': token})}\n\n".encode())
                                self.wfile.flush()
                            if chunk.get("done"):
                                break
                        except: continue

                    reply = "".join(full_reply)
                    is_err = not reply or reply.startswith("[Ollama error]")

                    # Save chat history
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
                    return  # Already sent response via streaming

                except Exception as stream_err:
                    _ollama_busy = False
                    # Streaming failed — fall through to non-streaming
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
                "ollamaError": is_err,
                "responseTimeMs":   int((time.time() - _chat_t0) * 1000),
                "kbArticlesUsed":   _kb_used_count,
                "crawlersPaused":   _perf_mode == "battery" or _ollama_busy,
                "perfMode":         _perf_mode,
            })

        # ── RECEIVE FILE FROM PHONE ───────────────────────────────
        elif path == "/api/receive_file":
            if not self._authed(body):
                self._json({"error": "Unauthorized"}, 401); return
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
                self._json({"error": "Unauthorized"}, 401); return
            pkgs = body.get("packages", [])
            # Validate package names - no shell injection
            safe = [p for p in pkgs
                    if isinstance(p, str) and len(p) < 80
                    and p.replace("-","").replace("_","").replace("[","").replace("]","").replace(".","").replace("~","").replace(">=","").replace("<=","").replace("==","").replace(">","").replace("<","").replace(",","").replace(";","").replace(" ","").isalnum()]
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
                self._json({"error": "Unauthorized"}, 401); return
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
            if not self._authed(body): self._json({"error":"Unauthorized"},401); return
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
        elif path == "/api/learn/status":
            if not self._authed(body): self._json({"error":"Unauthorized"},401); return
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
                self._json({"error": "Unauthorized"}, 401); return
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
            if not self._authed(body): self._json({"error":"Unauthorized"},401); return
            model_to_pull = body.get("model", DEFAULT_MODEL)
            def _do_pull():
                # Ensure Ollama is running first
                if not _ollama_is_running():
                    _start_ollama_service()
                _ensure_model(model_to_pull)
            threading.Thread(target=_do_pull, daemon=True, name="ollama-pull").start()
            self._json({"status":"ok","message":f"Pulling {model_to_pull} in background. Check AI status in 2-5 minutes."})

        # ── RESET PAIR ───────────────────────────────────────────
        # ── PAIR STATUS (no auth required - safe public info) ────────
        elif path == "/api/pair/status":
            locked = _gs("locked_device")
            self._json({
                "paired":      bool(locked),
                "pairingCode": _gs("pairing_code") or "" if not locked else "",
                "serverVersion": VERSION,
                "pairingReady": not bool(locked),
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
            if not self._authed(body): self._json({"error":"Unauthorized"},401); return
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
            if not self._authed(body): self._json({"error":"Unauthorized"},401); return
            device_id = _gs("locked_device") or "anon"
            _chat_clear(device_id)
            self._json({"status": "ok", "cleared": True})

        # ── KB SEARCH ────────────────────────────────────────────
        elif path == "/api/kb/search":
            if not self._authed(body): self._json({"error":"Unauthorized"},401); return
            q = body.get("q", body.get("query", ""))
            limit = int(body.get("limit", 8))
            self._json({"results": _kb_search(q, limit), "query": q, "total": _kb_count()})

        # ── KB ENRICH (returns enrichments[] array) ───────────────
        elif path == "/api/kb/enrich":
            if not self._authed(body): self._json({"error":"Unauthorized"},401); return
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

        elif path == "/api/kb/log":
            # Allow unauthenticated KB saves from app when token is being refreshed
            # But block strangers when server is locked to a device
            if _gs("locked_device") and not self._authed(body):
                self._json({"error":"Unauthorized"},401); return
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
            if not self._authed(body): self._json({"error":"Unauthorized"},401); return
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
            if not self._authed(body): self._json({"error":"Unauthorized"},401); return
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
            if not self._authed(body): self._json({"error":"Unauthorized"},401); return
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
            if not self._authed(body): self._json({"error":"Unauthorized"},401); return
            SHARE_DIR.mkdir(parents=True, exist_ok=True)
            files = [{"name": f.name,
                      "size": f.stat().st_size,
                      "size_str": f"{f.stat().st_size//1024}KB"}
                     for f in sorted(SHARE_DIR.iterdir()) if f.is_file()]
            self._json({"files": files, "count": len(files)})

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
    return "".join(random.choices("ABCDEFGHJKLMNPQRSTUVWXYZ23456789", k=8))

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

    parser = argparse.ArgumentParser(description="Cyber-Botler Desktop Server v7.0")
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
        if IS_WINDOWS: os.system("pause")
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

    # Print startup banner
    W = 64
    print()
    print("=" * W)
    print(f"  CYBER-BOTLER DESKTOP SERVER  v{VERSION}")
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
    main()