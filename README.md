# pybro

`pybro` is a minimal, zero‑dependency Python UI runtime for automation scripts.  
It parses declarative UI code statically using Python’s AST and serves the result in any modern browser.  
Use it when you want a quick form‑based interface, live script output, or a simple dashboard without adding a front‑end stack.

> **Note**  
> `pybro` was built for my Termux workspace on Android and is actively used there with Chrome, Brave, and DuckDuckGo.  
> Most core functionality has been tested, but device and browser coverage is still incomplete.  
> If you find a bug, compatibility issue, or rough edge, please open an issue with reproduction steps and device/browser details.

> ⚠️ **Early Development Notice**  
> `pybro` is under active development and may change rapidly.  
> Expect breaking changes, incomplete documentation, and the occasional bug.  
> It is already used daily by its creator, but it has not yet been broadly tested in production environments.  
> **Feedback, bug reports, and pull requests are extremely welcome.**

---

## ✅ Working Now

* **Static AST Architecture** – compiles UI layout tokens without executing arbitrary global code.
* **Reactive Client‑Side Calculations** – math processing happens instantly in the browser sandbox.
* **Real‑Time UI Updates (SSE)** – token changes (e.g., callback patches, file‑watcher) are pushed to all connected browsers instantly.
* **Bi‑directional Form State** – input changes are synchronised across clients via Server‑Sent Events.
* **Per‑Token Custom Styling** – every component accepts optional `css` (inline styles) and `class_` (CSS class).
* **Global Theme Overrides** – `ui.root_css({...})` lets you change colours, fonts, and radii across the whole dashboard.
* **Variable Resolution** – the AST parser can follow simple top‑level variable assignments, so you can write `HEADERS = [...]` and use it directly in `ui.table(HEADERS, ...)`.
* **Multi‑Page & Tab Support** – `ui.page_start`/`ui.page_end` and `ui.tab_group_start`/`ui.tab_end` create navigable pages with local tab bars.
* **Dynamic Token Patches** – callback functions can return a list of patch actions to change labels, CSS, table rows, dropdown options, and more – the UI updates instantly.
* **Localhost and Shared Deployment Modes** – safe localhost mode and authenticated team‑sharing mode.
* **OS Command Execution** – shell commands can be triggered from the UI after explicit browser confirmation. Output is displayed directly in a terminal div (blocking execution).
* **Volatile Memory Lifespan** – no disk tracking; quitting the process wipes server state and temporary files from RAM.
* **Multi‑file Projects** – the engine automatically adds your script’s directory to `sys.path`, so you can import helper modules from the same folder.
* **Keyword Arguments in the AST** – `target_id`, `css`, and `class_` are all recognised as named arguments (e.g. `ui.button_callback("Label", "func", target_id="output")`).
* **File Watcher (`--watch`)** – automatically reloads the script on file changes; re‑compiles tokens and refreshes all connected browsers.
* **SSE Heartbeat** – the server keeps SSE connections alive with a periodic comment, preventing silent drops on mobile or proxy networks.
* **Debounced Form Sync** – the front‑end batches rapid input changes before sending them to the server, reducing network load.
* **Explicit Button Types** – all dynamic buttons carry `type="button"` to avoid accidental form submissions.

---

## 🚧 In Progress / Experimental

* **Multi‑file project bundling** – Mode 2 can now download an entire project directory (all `.py` files) when a shared key is used. Use with `--connect`.
* **Dependency auto‑installation** – with `--allow-deps`, a temporary virtual environment is created and required packages (listed in `pybro.toml`) are installed inside it.
* **Built‑in TLS / SSL** – HTTPS is supported via `--ssl`. You can either let pybro generate a self‑signed certificate (Python ≥ 3.9, full builds only) or provide your own with `--cert-file` and `--key-file`.
* **Signed token‑tree distribution** – in shared mode, the master builds a cryptographically signed project tree (HMAC‑SHA256) that the client verifies before execution. Served at `/token-tree`.

---

## 🛠️ Installation

```bash
pip install -e .
```

From the pybro_ui/ directory.
This makes the pybro command available locally.

---

📐 Supported UI Tokens & Attributes

Every visual token accepts optional keyword arguments:

Argument Description
css Dictionary of inline CSS property/value pairs applied to the component wrapper (or the title element).
class_ String that adds a CSS class to the component wrapper (or the title element).

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

Call Component Description Example
Structural   
ui.page_start("Name") Page Begins a named page. ui.page_start("Dashboard")
ui.page_end() Page Ends the current page. ui.page_end()
ui.tab_group_start() Tab Group Opens a tab container inside the current page. ui.tab_group_start()
ui.tab_start("Name") Tab Starts a named tab. ui.tab_start("Settings")
ui.tab_end() Tab Ends the current tab. ui.tab_end()
ui.tab_group_end() Tab Group Ends the tab group. ui.tab_group_end()
ui.row_start() Layout Begins a horizontal flex row. ui.row_start()
ui.row_end() Layout Ends the current row and returns to vertical stacking. ui.row_end()
Visual   
ui.title(text) Heading Header block. ui.title("Main Dashboard")
ui.input_text(id, label) Input Text entry field. ui.input_text("username", "Enter Username")
ui.checkbox(id, label) Input True/False toggle. ui.checkbox("remember_me", "Remember Me")
ui.dropdown(id, label, options) Input Drop‑down selection; options can be inline or a previously defined list variable. ui.dropdown("theme", "Select Theme", ["Light", "Dark"])
ui.text_area(id, label) Output Read‑only output textarea. ui.text_area("logs", "System Logs")
ui.math_compute(target_id, formula) Evaluation Client‑side expression with {placeholder} substitution. ui.math_compute("total", "{price} * {quantity}")
ui.button_callback(text, function, target_id?) Handshake Triggers a Python backend function. target_id can be passed as third positional argument or as a keyword argument (target_id="output"). ui.button_callback("Submit", "process_data", "result_box")
ui.os_command(cmd, desc, target_id) System Runs a shell command after a browser confirmation prompt. Output is displayed when the command finishes (blocking). ui.os_command("ping -c 4 google.com", "Ping Test", "ping_output")
ui.table(headers, rows) Reporting Static table. Data may be inlined or passed via variables. ui.table(["Name", "Age"], [["Alice", 30], ["Bob", 25]])
ui.root_css(vars_dict) Theme Overrides global CSS custom properties. ui.root_css({"--primary-color": "#007bff"})

Callback form data

Callback functions receive a single dict containing the current values of all input widgets, keyed by their id.
Checkbox values are bool, all others are str. Example:

```python
def my_callback(form):
    print(form['host'])          # "192.168.1.1"
    print(form['verbose'])       # True or False
```

Dynamic UI Updates (Token Patches)

A callback can return a list of patch dictionaries to modify the live interface instantly.
Supported actions: set_text, set_label, set_css, set_class, insert_table_row, set_table_rows, set_options.
See TECHNICAL.md for full details.

---

⚡ Quick Start

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

Open http://localhost:8080 in any browser.

3. Try the included example:

```bash
pybro examples/mytool.py
```

---

🔐 Deployment Modes

Mode 0 – Localhost

```bash
pybro my_tool.py
```

Locks the server to 127.0.0.1. Ideal for personal tools.

Mode 1 – Shared Team Hub

```bash
pybro my_tool.py --shared --key mysecret
```

Binds to 0.0.0.0. Anyone on your LAN can connect if they supply the correct key, either in the URL ?key=... or the X-Pybro-Key header.
If you omit --key, a random hex token is generated and printed.
When a key is active, you can optionally add --connectable to build a signed project token tree for secure distribution.

Mode 2 – Distributed Sandbox Client (experimental)

```bash
pybro --connect 192.168.1.45:8080 --key mysecret
```

Downloads the remote project (multiple files, if bundled) to a temporary sandbox, runs callbacks locally, and deletes the temporary files on exit.
Use --keep-script to preserve the downloaded project directory.
If the remote project declares external dependencies (via pybro.toml), pass --allow-deps to auto‑install them in a temporary venv.

Tip: If you run both the master and a client on the same machine, give the client a different port with --port 8081 to avoid conflicts.

---

🧪 Advanced Options

Flag Effect
--port 9090 Change the listening port (default 8080).
--verbose Print Apache‑style HTTP request logs.
--key <secret> Set the security key explicitly (shared mode or --connect).
--keep-script In Mode 2, retain the downloaded project directory after shutdown.
--ssl Serve over HTTPS. Use with --cert-file/--key-file or let pybro generate a self‑signed cert (Python ≥ 3.9).
--cert-file <path> Path to TLS certificate file (PEM) for --ssl.
--key-file <path> Path to TLS private key file (PEM) for --ssl.
--allow-deps In Mode 2, auto‑install external dependencies from pybro.toml into an ephemeral venv.
--entrypoint <file> In Mode 2, specify the main script filename (default: main.py or first .py).
--os-timeout <int> Timeout in seconds for OS commands (default 5).
--watch Watch the script file for changes; re‑compile tokens and push UI updates live.

---

🔧 Technical Notes

· Simple top‑level list/dict assignments are resolved by the AST parser. Complex expressions and function calls are not yet supported. We aim to add constant folding and basic import resolution in a future release.
· OS commands must match the exact string defined in the script. They run with a configurable timeout (default 5 seconds) and capture the output. Because commands are executed with shell=True (for pipes/redirects), only trusted script authors should define OS commands. A future allow‑list is planned.
· Real‑time UI updates use Server‑Sent Events (SSE). Form state changes and token updates are broadcast to all connected clients. For a single‑user tool this is seamless; multi‑user sessions with isolated state are a potential future enhancement.
· The signed token‑tree (HMAC‑SHA256) ensures code integrity when distributing projects in shared mode.
· In local/shared master mode, the script’s directory is automatically added to sys.path, so from scanner import ... works without manual sys.path hacks.
· The button_callback token recognises target_id as a keyword argument; both positional and keyword forms are valid.
· The engine requires Python ≥ 3.8; some optional features (auto SSL, TOML parsing) need 3.9+.

---

🗺️ Roadmap

· Improved developer experience
  · Clear parser error messages with line numbers when unsupported syntax is encountered.
  · ~~--watch flag that auto‑reloads the script on file changes~~ ✅ done
· New built‑in widgets
  · Password field, sliders, date pickers, file upload stubs.
  · ui.markdown(text) token that renders a static markdown block.
  · Dark/light theme toggle linked to the existing CSS variable system.
· Layout & navigation
  · ~~Tabs and multipage layouts~~ ✅ done
· Security hardening
  · Configurable command allow‑list for os_command.
  · Full sandboxing options for Mode 2 clients.
· Advanced scripting
  · Optional persistent state with a --state-file flag.
  · Custom CSS/JS injection with security gating.

---

📦 Project Structure

```text
pybro_ui/
├── pyproject.toml
├── README.md
├── TECHNICAL.md
├── LICENSE
├── examples/
│   ├── mytool.py               # canonical simple example
│   └── netsweep/               # multi‑file project example
│       ├── main.py
│       ├── scanner.py
│       ├── utils.py
│       └── pybro.toml
└── src/
    └── pybro/
        ├── __init__.py         # exports the `ui` stub
        ├── index.html          # frontend (static, zero‑dependency)
        └── server.py           # runtime engine
```

---

📚 Documentation & License

· Full technical reference: TECHNICAL.md
· License: LICENSE (MIT)

---

MIT – do whatever you want, just don’t blame us if you point an OS command at something dangerous.
