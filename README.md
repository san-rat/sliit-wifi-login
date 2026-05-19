# SLIIT WiFi Auto-Login

Automatically logs into the SLIIT university WiFi (FortiGate captive portal) so you never have to type your credentials again.

- **Zero dependencies** — Python 3.8+ standard library only
- **Cross-platform** — works on macOS and Windows
- **Lightweight** — single script, runs in under a second, no-ops when already online
- **Automatic** — triggers on network change and runs periodically as a safety net

## Quick Start

### 1. Clone

```sh
git clone https://github.com/notdulain/sliit-wifi-login.git
cd sliit-wifi-login
```

### 2. Add your credentials

```sh
cp credentials.example.json credentials.json
```

Edit `credentials.json` with your SLIIT username and password:

```json
{
  "username": "itXXXXXXXX",
  "password": "your-password-here"
}
```

### 3. Install

**macOS:**

```sh
chmod +x setup-mac.sh
./setup-mac.sh
```

**Windows** (run PowerShell as Administrator):

```powershell
.\setup-windows.ps1
```

That's it. The script will now run automatically whenever you connect to SLIIT WiFi.

## Changing Your Password

Edit `credentials.json` — no restart or reinstall needed. The script reads the file fresh every time it runs.

```sh
# macOS / Linux
nano credentials.json

# Windows
notepad credentials.json
```

## Manual Run

Test the script at any time:

```sh
python3 sliit-login.py
```

## Check Logs

```sh
# macOS / Linux
tail -f sliit-login.log

# Windows
type sliit-login.log
```

Successful output looks like:

```
[2026-05-19T08:35:34] Portal detected: https://auth.sliit.lk:1003/fgtauth?044726bbc1a08385
[2026-05-19T08:35:35] Login successful as it23750760.
[2026-05-19T08:36:03] Already online.
```

## How It Works

1. Probes the OS captive-portal detection URL (Apple's on macOS, Microsoft's on Windows)
2. If the response is a redirect to `auth.sliit.lk`, a captive portal is active
3. Fetches the portal page and extracts the session token (`magic`)
4. POSTs your credentials to the FortiGate authentication endpoint
5. Verifies login by re-probing

The script exits silently when you're not on SLIIT WiFi — safe to leave running anywhere.

## When Does It Run?

| Trigger | macOS | Windows |
|---|---|---|
| At login / boot | Yes | Yes |
| Network change (WiFi join) | Yes (launchd WatchPaths) | Yes (NetworkProfile event) |
| Every 30 min (safety net) | Yes | Yes |

## Disable the macOS "Captive" Popup

macOS shows a small "Captive" window when it detects a portal. Since this script handles login, you can disable it:

```sh
sudo defaults write /Library/Preferences/SystemConfiguration/com.apple.captive.control Active -bool false
```

Reboot once. Re-enable anytime with `-bool true`.

## Uninstall

**macOS:**

```sh
chmod +x uninstall-mac.sh
./uninstall-mac.sh
```

**Windows** (PowerShell as Administrator):

```powershell
.\uninstall-windows.ps1
```

Then delete the folder.

## Security Note

`credentials.json` is gitignored and never committed. The setup scripts set file permissions to owner-only (600) on macOS. On Windows, it lives in your user directory with your account's default permissions.
