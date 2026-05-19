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

### 2. Install

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

### 3. First-Time Setup (GUI)

The first time the script runs, a small setup window will appear asking for your SLIIT credentials:

```
┌─────────────────────────────────────┐
│  SLIIT WiFi Setup                   │
│  Enter your SLIIT portal credentials│
│                                     │
│  Username  [ it23xxxxxx           ] │
│  Password  [ ••••••••••    Show   ] │
│                                     │
│         [ Save & Connect ]          │
└─────────────────────────────────────┘
```

Fill in your username and password, click **Save & Connect**, and the script saves `credentials.json` and immediately logs you in. No manual file editing required.

> You can also skip the GUI by creating `credentials.json` manually before running:
> ```sh
> cp credentials.example.json credentials.json
> # then edit credentials.json with your details
> ```

## Changing Your Password

### Option A — Edit the file directly

```sh
# macOS / Linux
nano credentials.json

# Windows
notepad credentials.json
```

No restart or reinstall needed. The script reads the file fresh every time it runs.

### Option B — Automatic prompt (recommended)

If your password has changed and the script fails to log in **3 times within 30 seconds**, a credential update window appears automatically:

```
┌──────────────────────────────────────────┐
│  Login Failed 3 Times                    │
│  Update your username and/or password.   │
│                                          │
│  Username  [ it23xxxxxx              ]   │
│  New Pass  [ ••••••••••••••   Show   ]   │
│                                          │
│  [ Cancel ]          [ Update & Retry ]  │
└──────────────────────────────────────────┘
```

- The **Username** field is pre-filled but editable (in case your student ID also changed)
- Click **Update & Retry** — credentials are saved and a login attempt is made immediately
- Click **Cancel** to dismiss without saving

> **How the 3-failure detection works:** Each failed login records a timestamp in a local `login_attempts.json` file. If 3 or more failures occur within 30 seconds the prompt appears. The counter resets automatically on a successful login.

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
6. If login fails 3 times within 30 seconds, prompts for updated credentials and retries immediately

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

`credentials.json` and `login_attempts.json` are gitignored and never committed. The setup scripts set file permissions to owner-only (600) on macOS. On Windows, they live in your user directory with your account's default permissions.
