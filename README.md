# pybro

A lightweight, zero‑dependency, AST‑driven UI runtime engine for Python automation scripts.

`pybro` bridges the gap between raw command‑line utility scripts and interactive web dashboards.
It parses declarative UI definitions statically using Python’s abstract syntax trees (AST),
rendering cross‑platform layouts inside any modern mobile or desktop browser without requiring
massive enterprise frameworks (`Node.js`, `Electron`, or heavy web servers).

---

## 🚀 Core Features

* **Static AST Architecture** – compiles UI layout tokens without executing arbitrary global code.
* **Reactive Client‑Side Calculations** – math processing happens instantly in the browser sandbox.
* **Real‑Time Updates (SSE)** – callbacks and OS commands push output to all connected browsers live.
* **Per‑Token Custom Styling** – every component accepts optional `css` (inline styles) and `class_` (CSS class).
* **Global Theme Overrides** – `ui.root_css({...})` lets you change colours, fonts, and radii across the whole dashboard.
* **Three Deployment Modes** – safe localhost, authenticated team‑sharing hub, or distributed peer sandbox.
* **Volatile Memory Lifespan** – no disk tracking; quitting the process instantly wipes all server state from RAM.

---

## 🛠️ Installation

```bash
pip install -e .
```

(from the pybro_ui/ directory)

This makes the pybro command globally available.

---

📐 Supported UI Tokens & Attributes

Every visual token accepts optional keyword arguments:

Argument Description
css Dictionary of inline CSS property/value pairs applied to the component wrapper (or the element itself for titles).
class_ String – adds a CSS class to the component wrapper (or the title element).

The global theme can be changed with:

```python
ui.root_css({"--bg": "#0a0e17", "--accent": "#f97316", ...})
```

Available CSS variables (defaults shown):

```css
--bg: #0b0f19;
--surface: #131a2b;
--border: #2a3350;
--text: #e0e6f0;
--accent: #6e8efb;
--green: #00e676;
--red: #ff5252;
--radius: 12px;
--shadow: 0 8px 24px rgba(0,0,0,0.6);
```

Token catalogue

| Call | Component | Description |
| :--- | :--- | :--- |
| ui.title(text) | Structural | Header block. |
| ui.row_start() | Structural | Begins a horizontal flex row. |
| ui.row_end() | Structural | Ends the current row, returns to vertical stack. |
| ui.input_text(id, label) | Input | Text entry field. |
| ui.checkbox(id, label) | Input | True/False toggle. |
| ui.dropdown(id, label, options) | Input | Drop‑down selection menu. |
| ui.text_area(id, label) | Output | Read‑only output textarea. |
| ui.math_compute(target_id, formula) | Evaluation | Client‑side evaluation. |
| ui.button_callback(text, function, target_id?) | Handshake | Triggers backend function loop. |
| ui.os_command(cmd, desc, target_id) | System Execution | Runs shell commands via secure prompt. |
| ui.table(headers, rows) | Reporting | Static table. Data must be nested arrays. |
| ui.root_css(vars_dict) | Theme | Overrides global CSS custom properties. |


---

⚡ Quick Start

1. Write a blueprint script

```python
from pybro import ui

def run_scan(form):
    return f"Scanning {form.get('host')}..."

# Global theme
ui.root_css({"--accent": "#e94560"})

ui.title("Network Scanner", css={"fontSize": "2rem"})

ui.row_start(css={"gap": "2rem"})
ui.input_text("host", "Target Host", css={"border": "2px solid var(--accent)"})
ui.checkbox("verbose", "Verbose Logging")
ui.row_end()

ui.text_area("scan_output", "Scan Result")
ui.button_callback("Start Scan", "run_scan",
                   target_id="scan_output",
                   css={"background": "linear-gradient(45deg, #e94560, #0f3460)", "border": "none"})
```

2. Run it

```bash
pybro my_tool.py
```

Open http://localhost:8080 in any browser.

---

🔐 Deployment Modes

Mode 0 – Localhost (default)

```bash
pybro my_tool.py
```

Locks the server to 127.0.0.1. Ideal for personal tools.

Mode 1 – Shared Team Hub

```bash
pybro my_tool.py --shared --key mysecret
```

Binds to 0.0.0.0. Anyone on your LAN can connect if they supply the correct key
(either in the URL ?key=... or the X-Pybro-Key header).
If you omit --key, a random hex token is generated and printed.

Mode 2 – Distributed Sandbox Client

```bash
pybro --connect 192.168.1.45:8080 --key mysecret
```

Pulls the UI blueprint and the full Python script from a remote master,
executes all callbacks locally, and deletes the temporary script on exit.
Add --keep-script to retain the downloaded file.

---

🧪 Advanced Options

| Flag | Effect |
| :--- | :--- |
| `--port 9090` | Change the listening port (default 8080). |
| `--verbose` | Print Apache‑style HTTP request logs. |
| `--key` | Reusable in Mode 2 to set the auth key explicitly. |
| `--keep-script` | In Mode 2, do not delete the temporary script. |

---

📦 Project Structure

```text
pybro_ui/
├── pyproject.toml
├── README.md
└── src/
    └── pybro/
        ├── __init__.py      # exports the `ui` stub
        ├── index.html       # frontend (static, zero‑dependency)
        ├── mytool.py        # example script
        └── server.py        # runtime engine
```

---

🔧 Technical Notes

· All list/dict arguments must be inlined – the AST parser cannot follow variable references.
  Example: ui.table(["ID"], [["1"]]) works; ui.table(headers, rows) does not.
· OS commands must match the exact string defined in the script. They run with a 5‑second timeout and captured output.
· Real‑time updates use Server‑Sent Events (SSE) – every connected browser receives output instantly,
  no polling needed.
· Security key is transmitted in plain text over HTTP. For untrusted networks,
  pair pybro with a TLS reverse proxy (Caddy, nginx).
· The engine requires Python ≥ 3.8.

---

📄 License

MIT – do whatever you want, just don’t blame us if you point an OS command at something dangerous.


---
