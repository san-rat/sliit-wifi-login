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
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse

# ---------------------------------------------------------------------------
# Paths — everything lives next to this script
# ---------------------------------------------------------------------------
SCRIPT_DIR = Path(__file__).resolve().parent
CONFIG_PATH = SCRIPT_DIR / "credentials.json"
LOG_PATH = SCRIPT_DIR / "sliit-login.log"

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
# Credentials
# ---------------------------------------------------------------------------
def load_credentials() -> dict:
    if not CONFIG_PATH.exists():
        raise SystemExit(
            f"Missing credentials file: {CONFIG_PATH}\n"
            f"Copy credentials.example.json to credentials.json and fill it in."
        )
    with open(CONFIG_PATH) as f:
        creds = json.load(f)
    if not creds.get("username") or not creds.get("password"):
        raise SystemExit("credentials.json must contain 'username' and 'password'.")
    return creds


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
    try:
        page = fetch(portal_url, insecure=True).read().decode("utf-8", errors="ignore")
        magic, post_url = parse_form(page, portal_url)
    except (urllib.error.URLError, RuntimeError) as e:
        log(f"Failed to read portal form: {e}")
        return 1

    creds = load_credentials()
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
        return 0
    log("Login submitted but verification failed — check credentials.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
