#!/usr/bin/env python3
"""Auto-login for the SLIIT FortiGate captive portal.

Works on macOS and Windows. Reads credentials from credentials.json
(same directory as this script) and authenticates against the FortiGate
captive portal. No-ops silently when already online or not on SLIIT WiFi.

Requires: Python 3.8+ (stdlib only, no pip installs).
"""

from __future__ import annotations

import json
import os
import platform
import re
import ssl
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse

try:
    import tkinter as tk
    _HAS_TK = True
except ImportError:
    _HAS_TK = False

# ---------------------------------------------------------------------------
# Paths — everything lives next to this script
# ---------------------------------------------------------------------------
SCRIPT_DIR = Path(__file__).resolve().parent
CONFIG_PATH = SCRIPT_DIR / "credentials.json"
LOG_PATH = SCRIPT_DIR / "sliit-login.log"
ATTEMPTS_PATH = SCRIPT_DIR / "login_attempts.json"

# ---------------------------------------------------------------------------
# Captive-portal probe — OS-aware
# ---------------------------------------------------------------------------
if platform.system() == "Darwin":
    PROBE_URL = "http://captive.apple.com/hotspot-detect.html"
    SUCCESS_MARKER = "<TITLE>Success</TITLE>"
elif platform.system() == "Windows":
    PROBE_URL = "http://www.msftconnecttest.com/connecttest.txt"
    SUCCESS_MARKER = "Microsoft Connect Test"
else:
    # Linux / fallback
    PROBE_URL = "http://detectportal.firefox.com/success.txt"
    SUCCESS_MARKER = "success"

TIMEOUT = 10
USER_AGENT = "Mozilla/5.0 sliit-login"

FAILURE_WINDOW_SECONDS = 30  # rolling window for failure tracking
FAILURE_THRESHOLD = 3        # failures within window before password prompt

# Suppress noisy InsecureRequestWarning tracebacks on stderr
import warnings
warnings.filterwarnings("ignore")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def log(msg: str) -> None:
    line = f"[{datetime.now().isoformat(timespec='seconds')}] {msg}"
    print(line)
    try:
        with open(LOG_PATH, "a") as f:
            f.write(line + "\n")
    except OSError:
        pass


def _ssl_ctx(insecure: bool) -> ssl.SSLContext:
    ctx = ssl.create_default_context()
    if insecure:
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
    return ctx


def fetch(url: str, data: dict | None = None, insecure: bool = False):
    body = urllib.parse.urlencode(data).encode() if data is not None else None
    req = urllib.request.Request(url, data=body, headers={"User-Agent": USER_AGENT})
    return urllib.request.urlopen(req, context=_ssl_ctx(insecure), timeout=TIMEOUT)


# ---------------------------------------------------------------------------
# Portal detection
# ---------------------------------------------------------------------------
def probe() -> tuple[bool, str, str]:
    """Hit the OS captive-portal probe. Return (is_online, body, final_url)."""
    try:
        resp = fetch(PROBE_URL)
        body = resp.read().decode("utf-8", errors="ignore")
        return SUCCESS_MARKER in body, body, resp.geturl()
    except Exception:
        return False, "", ""


def find_portal_url(body: str, final_url: str) -> str | None:
    m = re.search(r'(https?://auth\.sliit\.lk:\d+/fgtauth\?[0-9a-fA-F]+)', body)
    if m:
        return m.group(1)
    if "fgtauth" in final_url:
        return final_url
    m = re.search(r'window\.location\s*=\s*["\']([^"\']+)["\']', body)
    if m and "fgtauth" in m.group(1):
        return m.group(1)
    return None


def parse_form(page: str, portal_url: str) -> tuple[str, str]:
    magic_match = (
        re.search(r'name=["\']?magic["\']?\s+value=["\']?([0-9a-fA-F]+)', page)
        or re.search(r'fgtauth\?([0-9a-fA-F]+)', portal_url)
    )
    if not magic_match:
        raise RuntimeError("Could not locate magic token in portal response.")
    magic = magic_match.group(1)

    action_match = re.search(
        r'<form[^>]+action=["\']?([^"\' >]+)', page, re.IGNORECASE
    )
    p = urlparse(portal_url)
    if action_match:
        action = action_match.group(1)
        if action.startswith("http"):
            post_url = action
        elif action.startswith("/"):
            post_url = f"{p.scheme}://{p.netloc}{action}"
        else:
            post_url = f"{p.scheme}://{p.netloc}/{action}"
    else:
        post_url = f"{p.scheme}://{p.netloc}/"
    return magic, post_url


# ---------------------------------------------------------------------------
# Failure tracking
# ---------------------------------------------------------------------------
def _load_attempts() -> dict:
    if ATTEMPTS_PATH.exists():
        try:
            with open(ATTEMPTS_PATH) as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError):
            pass
    return {"failures": []}


def _save_attempts(data: dict) -> None:
    try:
        with open(ATTEMPTS_PATH, "w") as f:
            json.dump(data, f)
    except OSError:
        pass


def record_failure() -> None:
    """Append current timestamp to the failure log."""
    data = _load_attempts()
    data["failures"].append(time.time())
    _save_attempts(data)


def check_failure_threshold() -> bool:
    """Return True if >= FAILURE_THRESHOLD failures in the last FAILURE_WINDOW_SECONDS."""
    data = _load_attempts()
    now = time.time()
    recent = [t for t in data["failures"] if now - t <= FAILURE_WINDOW_SECONDS]
    data["failures"] = recent
    _save_attempts(data)
    return len(recent) >= FAILURE_THRESHOLD


def clear_failures() -> None:
    """Reset failure log after a successful login."""
    _save_attempts({"failures": []})


# ---------------------------------------------------------------------------
# Credentials
# ---------------------------------------------------------------------------
def save_credentials(creds: dict) -> None:
    """Write credentials.json with the given dict."""
    with open(CONFIG_PATH, "w") as f:
        json.dump(creds, f, indent=2)
    if platform.system() == "Darwin":
        try:
            os.chmod(CONFIG_PATH, 0o600)
        except OSError:
            pass


def load_credentials() -> dict:
    creds = {}
    if CONFIG_PATH.exists():
        try:
            with open(CONFIG_PATH) as f:
                creds = json.load(f)
        except (json.JSONDecodeError, OSError):
            pass
    if not creds.get("username") or not creds.get("password"):
        creds = show_setup_dialog()
        if not creds:
            raise SystemExit("Setup cancelled. credentials.json not created.")
        save_credentials(creds)
        log(f"Credentials saved for {creds['username']}.")
    return creds


# ---------------------------------------------------------------------------
# GUI dialogs (tkinter — stdlib, zero extra installs)
# ---------------------------------------------------------------------------
def _require_tk() -> None:
    if not _HAS_TK:
        raise SystemExit(
            "tkinter is not available in this Python installation.\n"
            "Please create credentials.json manually (see credentials.example.json)."
        )


def _centre(root: tk.Tk) -> None:
    """Centre the window on screen after all widgets are packed."""
    root.update_idletasks()
    w = root.winfo_reqwidth()
    h = root.winfo_reqheight()
    sw = root.winfo_screenwidth()
    sh = root.winfo_screenheight()
    root.geometry(f"{w}x{h}+{(sw - w) // 2}+{(sh - h) // 2}")


def show_setup_dialog() -> dict | None:
    """Blocking dialog to collect username + password on first run.
    Returns a dict with 'username' and 'password', or None if cancelled."""
    _require_tk()
    result = {}

    root = tk.Tk()
    root.title("SLIIT WiFi — First Time Setup")
    root.resizable(False, False)
    root.attributes("-topmost", True)
    root.configure(padx=24, pady=20)

    tk.Label(root, text="SLIIT WiFi Setup",
             font=("Helvetica", 14, "bold")).grid(
        row=0, column=0, columnspan=2, pady=(0, 4), sticky="w")
    tk.Label(root, text="Enter your SLIIT portal credentials.",
             font=("Helvetica", 10), fg="#555555").grid(
        row=1, column=0, columnspan=2, sticky="w", pady=(0, 12))

    # Username
    tk.Label(root, text="Username", anchor="w", width=12).grid(
        row=2, column=0, sticky="w", pady=4)
    username_var = tk.StringVar()
    username_entry = tk.Entry(root, textvariable=username_var, width=28)
    username_entry.grid(row=2, column=1, pady=4, padx=(8, 0))

    # Password
    tk.Label(root, text="Password", anchor="w", width=12).grid(
        row=3, column=0, sticky="w", pady=4)
    password_var = tk.StringVar()
    pass_frame = tk.Frame(root)
    pass_frame.grid(row=3, column=1, pady=4, padx=(8, 0))
    password_entry = tk.Entry(pass_frame, textvariable=password_var,
                              show="*", width=22)
    password_entry.pack(side="left")

    def toggle_pw():
        if password_entry.cget("show") == "*":
            password_entry.config(show="")
            eye_btn.config(text="Hide")
        else:
            password_entry.config(show="*")
            eye_btn.config(text="Show")

    eye_btn = tk.Button(pass_frame, text="Show", command=toggle_pw,
                        relief="flat", cursor="hand2", width=4)
    eye_btn.pack(side="left", padx=(6, 0))

    # Error label
    error_var = tk.StringVar()
    tk.Label(root, textvariable=error_var, fg="red",
             font=("Helvetica", 9)).grid(
        row=4, column=0, columnspan=2, sticky="w")

    def on_save():
        u = username_var.get().strip()
        p = password_var.get()
        if not u or not p:
            error_var.set("Both fields are required.")
            return
        result["username"] = u
        result["password"] = p
        root.destroy()

    tk.Button(root, text="Save & Connect", command=on_save,
              bg="#0055cc", fg="white", font=("Helvetica", 10, "bold"),
              relief="flat", cursor="hand2", padx=12, pady=6).grid(
        row=5, column=0, columnspan=2, pady=(16, 0))

    root.protocol("WM_DELETE_WINDOW", root.destroy)
    username_entry.focus()
    _centre(root)
    root.mainloop()

    return result if result else None


def show_password_update_dialog(username: str) -> dict | None:
    """Blocking dialog shown after 3 consecutive login failures.
    Returns a dict with 'username' and 'password', or None if cancelled."""
    _require_tk()
    result = {}

    root = tk.Tk()
    root.title("SLIIT WiFi — Update Credentials")
    root.resizable(False, False)
    root.attributes("-topmost", True)
    root.configure(padx=24, pady=20)

    tk.Label(root, text="Login Failed 3 Times",
             font=("Helvetica", 14, "bold"), fg="#cc3300").grid(
        row=0, column=0, columnspan=2, pady=(0, 4), sticky="w")
    tk.Label(root, text="Update your username and/or password below.",
             font=("Helvetica", 10), fg="#555555", wraplength=300,
             justify="left").grid(
        row=1, column=0, columnspan=2, sticky="w", pady=(0, 12))

    # Username (editable, pre-filled)
    tk.Label(root, text="Username", anchor="w", width=14).grid(
        row=2, column=0, sticky="w", pady=4)
    username_var = tk.StringVar(value=username)
    username_entry = tk.Entry(root, textvariable=username_var, width=28)
    username_entry.grid(row=2, column=1, pady=4, padx=(8, 0))

    # New password
    tk.Label(root, text="New Password", anchor="w", width=14).grid(
        row=3, column=0, sticky="w", pady=4)
    password_var = tk.StringVar()
    pass_frame = tk.Frame(root)
    pass_frame.grid(row=3, column=1, pady=4, padx=(8, 0))
    password_entry = tk.Entry(pass_frame, textvariable=password_var,
                              show="*", width=22)
    password_entry.pack(side="left")

    def toggle_pw():
        if password_entry.cget("show") == "*":
            password_entry.config(show="")
            eye_btn.config(text="Hide")
        else:
            password_entry.config(show="*")
            eye_btn.config(text="Show")

    eye_btn = tk.Button(pass_frame, text="Show", command=toggle_pw,
                        relief="flat", cursor="hand2", width=4)
    eye_btn.pack(side="left", padx=(6, 0))

    # Error label
    error_var = tk.StringVar()
    tk.Label(root, textvariable=error_var, fg="red",
             font=("Helvetica", 9)).grid(
        row=4, column=0, columnspan=2, sticky="w")

    # Buttons
    btn_frame = tk.Frame(root)
    btn_frame.grid(row=5, column=0, columnspan=2, pady=(16, 0), sticky="e")

    def on_cancel():
        root.destroy()

    def on_update():
        u = username_var.get().strip()
        p = password_var.get()
        if not u:
            error_var.set("Username cannot be empty.")
            return
        if not p:
            error_var.set("Password cannot be empty.")
            return
        result["username"] = u
        result["password"] = p
        root.destroy()

    tk.Button(btn_frame, text="Cancel", command=on_cancel,
              relief="flat", cursor="hand2", width=8).pack(
        side="left", padx=(0, 8))
    tk.Button(btn_frame, text="Update & Retry", command=on_update,
              bg="#0055cc", fg="white", font=("Helvetica", 10, "bold"),
              relief="flat", cursor="hand2", padx=8, pady=4).pack(side="left")

    root.protocol("WM_DELETE_WINDOW", root.destroy)
    password_entry.focus()
    _centre(root)
    root.mainloop()

    return result if result else None


# ---------------------------------------------------------------------------
# Login flow (extracted so it can be retried after a password update)
# ---------------------------------------------------------------------------
def do_login(portal_url: str, creds: dict) -> int:
    """Fetch the portal form, POST credentials, verify. Returns 0/1."""
    try:
        page = fetch(portal_url, insecure=True).read().decode("utf-8", errors="ignore")
        magic, post_url = parse_form(page, portal_url)
    except (urllib.error.URLError, RuntimeError) as e:
        log(f"Failed to read portal form: {e}")
        return 1

    payload = {
        "magic": magic,
        "username": creds["username"],
        "password": creds["password"],
        "4Tredir": "/",
    }

    try:
        fetch(post_url, data=payload, insecure=True).read()
    except urllib.error.URLError as e:
        log(f"Login POST failed: {e}")
        return 1

    online, _, _ = probe()
    if online:
        log(f"Login successful as {creds['username']}.")
        clear_failures()
        return 0
    log("Login submitted but verification failed — check credentials.")
    return 1


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main() -> int:
    online, body, final_url = probe()
    if online:
        log("Already online.")
        return 0

    portal_url = find_portal_url(body, final_url)
    if not portal_url:
        log("No SLIIT captive portal detected. Exiting.")
        return 0  # not on SLIIT WiFi — silent exit

    log(f"Portal detected: {portal_url}")

    creds = load_credentials()
    result = do_login(portal_url, creds)
    if result == 0:
        return 0

    # Login failed — track and check threshold
    record_failure()
    if check_failure_threshold():
        log("3 consecutive failures — prompting for credentials update.")
        new_creds = show_password_update_dialog(creds["username"])
        if new_creds:
            creds["username"] = new_creds["username"]
            creds["password"] = new_creds["password"]
            save_credentials(creds)
            clear_failures()
            log(f"Credentials updated for {creds['username']}. Retrying login...")
            return do_login(portal_url, creds)
        else:
            log("Credentials update cancelled by user.")

    return 1


if __name__ == "__main__":
    sys.exit(main())
