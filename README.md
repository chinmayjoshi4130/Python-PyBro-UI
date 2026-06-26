# pybro

`pybro` is a minimal Python UI runtime for automation scripts.

It parses declarative UI code with AST and serves the result in a browser.
Use it when you want a quick form-based interface, live script output, or simple dashboard behavior without adding a frontend stack.

> **Note**
> `pybro` was built for my Termux workspace on Android and is actively used there through Chrome, Brave, and DuckDuckGo.  
> I have tested most of the core functionality, but device and browser coverage is still incomplete.  
> If you find a bug, compatibility issue, or rough edge, please open an issue with reproduction steps and device/browser details.

> ⚠️ **Early Development Notice**
> `pybro` is under active development and may change rapidly.  
> Expect breaking changes, incomplete documentation, and the occasional bug.  
> It is already used daily by its creator, but it has not yet been broadly tested in production environments.  
> **Feedback, bug reports, and pull requests are extremely welcome.**

---

## ✅ Working Now

* **Static AST Architecture** – compiles UI layout tokens without executing arbitrary global code.
* **Reactive Client-Side Calculations** – math processing happens instantly in the browser sandbox.
* **Real-Time Updates (SSE)** – callbacks and OS commands push output to all connected browsers live.
* **Bi-directional Form State** – input changes are broadcast to connected clients via Server-Sent Events.
* **Per-Token Custom Styling** – every component accepts optional `css` (inline styles) and `class_` (CSS class).
* **Global Theme Overrides** – `ui.root_css({...})` lets you change colours, fonts, and radii across the whole dashboard.
* **Variable Resolution** – the AST parser can follow simple top-level variable assignments, so you can write `HEADERS = [...]` and use it directly in `ui.table(HEADERS, ...)`.
* **Localhost and Shared Deployment Modes** – safe localhost mode and authenticated team-sharing mode.
* **OS Command Execution** – shell commands can be triggered from the UI after explicit browser confirmation.
* **Volatile Memory Lifespan** – no disk tracking; quitting the process wipes server state and temporary files from RAM.

---

## 🚧 In Progress / Experimental

* **Multi-file project bundling** – being extended so Mode 2 can ship more than a single script.
* **Dependency support** – external package handling is planned for distributed execution workflows.
* **Built-in TLS / SSL** – HTTPS support is being explored for safer shared-network usage.
* **Plugin-style imports** – external helper modules and callable registration are planned for future releases.

---

## 🛠️ Installation

```bash
pip install -e .
```

From the `pybro_ui/` directory.

This makes the `pybro` command available locally.

---

## 📐 Supported UI Tokens & Attributes

Every visual token accepts optional keyword arguments:

| Argument | Description |
| :--- | :--- |
| `css` | Dictionary of inline CSS property/value pairs applied to the component wrapper (or the title element). |
| `class_` | String that adds a CSS class to the component wrapper (or the title element). |

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

### Token catalogue

| Call | Component | Description |
| :--- | :--- | :--- |
| `ui.title(text)` | Structural | Header block. |
| `ui.row_start()` | Structural | Begins a horizontal flex row. |
| `ui.row_end()` | Structural | Ends the current row and returns to vertical stacking. |
| `ui.input_text(id, label)` | Input | Text entry field. |
| `ui.checkbox(id, label)` | Input | True/False toggle. |
| `ui.dropdown(id, label, options)` | Input | Drop-down selection; options can be inline or a previously defined list variable. |
| `ui.text_area(id, label)` | Output | Read-only output textarea. |
| `ui.math_compute(target_id, formula)` | Evaluation | Client-side expression with `{placeholder}` substitution. |
| `ui.button_callback(text, function, target_id?)` | Handshake | Triggers a Python backend function. Optional third argument binds the output to a specific textarea or terminal. |
| `ui.os_command(cmd, desc, target_id)` | System Execution | Runs a shell command after a browser confirmation prompt. |
| `ui.table(headers, rows)` | Reporting | Static table. Data may be inlined or passed via variables. |
| `ui.root_css(vars_dict)` | Theme | Overrides global CSS custom properties. |

---

## ⚡ Quick Start

1. Write a blueprint script:

```python
from pybro import ui

def run_scan(form):
    return f"Scanning {form.get('host')}..."

ui.root_css({"--accent": "#e94560"})
ui.title("Network Scanner", css={"fontSize": "2rem"})

ui.row_start(css={"gap": "2rem"})
ui.input_text("host", "Target Host", css={"border": "2px solid var(--accent)"})
ui.checkbox("verbose", "Verbose Logging")
ui.row_end()

ui.text_area("scan_output", "Scan Result")
ui.button_callback(
    "Start Scan",
    "run_scan",
    target_id="scan_output",
    css={"background": "linear-gradient(45deg, #e94560, #0f3460)", "border": "none"},
)
```

2. Run it:

```bash
pybro my_tool.py
```

Open `http://localhost:8080` in any browser.

3. Try the included example:

```bash
pybro src/pybro/mytool.py
```

---

## 🔐 Deployment Modes

### Mode 0 – Localhost

```bash
pybro my_tool.py
```

Locks the server to `127.0.0.1`. Ideal for personal tools.

### Mode 1 – Shared Team Hub

```bash
pybro my_tool.py --shared --key mysecret
```

Binds to `0.0.0.0`. Anyone on your LAN can connect if they supply the correct key,
either in the URL `?key=...` or the `X-Pybro-Key` header.

If you omit `--key`, a random hex token is generated and printed.

### Mode 2 – Distributed Sandbox Client

```bash
pybro --connect 192.168.1.45:8080 --key mysecret
```

Downloads the remote project to a temporary sandbox, runs callbacks locally, and deletes the temporary files on exit.
Use `--keep-script` to preserve the downloaded project directory.

---

## 🔧 Technical Notes

* Simple top-level list/dict assignments are resolved by the AST parser. Complex expressions and function calls are not yet supported.
* OS commands must match the exact string defined in the script. They run with a 5-second timeout and captured output.
* Real-time updates use Server-Sent Events (SSE), and form state changes are broadcast to all connected clients.
* The engine requires Python >= 3.8.
* Python module imports are supported for helper code, but future plugin-style callable registration is still evolving.

---

## 🗺️ Roadmap

* Tabs and multipage layouts.
* Custom CSS and JS injection with security gating.
* Script signing and verification for distributed execution.
* More input widgets: sliders, date pickers, password fields, file upload stubs.
* Optional persistent state with a `--state-file` flag.

---

## 📦 Project Structure

```text
pybro_ui/
├── pyproject.toml
├── README.md
└── src/
    └── pybro/
        ├── __init__.py      # exports the `ui` stub
        ├── index.html       # frontend (static, zero-dependency)
        ├── mytool.py        # example script
        └── server.py        # runtime engine
```

---

## 📄 License

MIT – do whatever you want, just don’t blame us if you point an OS command at something dangerous.
