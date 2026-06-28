# Pybro

**Pybro** is a zero‑dependency Python dashboard runtime for automation scripts.  
It parses declarative UI code using Python’s AST and serves a live, reactive interface in any modern browser.  
Use it when you need a quick form‑based tool, live script output, or a simple team dashboard – without touching a front‑end stack.

> **Note**  
> Pybro was built for Termux on Android and is used daily with Chrome, Brave, and DuckDuckGo.  
> Most core functionality is well‑tested, but device and browser coverage is still growing.  
> If you hit a bug, please open an issue with reproduction steps and your device / browser details.

> ⚠️ **Early Development**  
> Pybro is under active development and may change rapidly.  
> Expect breaking changes, incomplete docs, and the occasional rough edge.  
> It is already used in production by its creator, but broad testing is still underway.  
> **Feedback, bug reports, and pull requests are extremely welcome.**

---

## ✅ What’s working

- **Static AST compilation** – the UI layout is built from your script without executing arbitrary global code.
- **Reactive client‑side math** – expressions like `{price} * {quantity}` update instantly in the browser.
- **Real‑time UI updates (SSE)** – token changes (callbacks, file watcher) are pushed to all connected browsers.
- **Bi‑directional form state** – input changes are synced across clients via Server‑Sent Events.
- **Per‑widget styling** – every component accepts `css` (inline) and `class_` (CSS class).
- **Global theme overrides** – `ui.root_css({...})` changes colours, fonts, and radii everywhere.
- **Simple variable resolution** – the parser follows top‑level assignments so you can define `HEADERS = [...]` and use it directly in `ui.table(HEADERS, ...)`.
- **Multi‑page & tab navigation** – `ui.page_start` / `ui.page_end` and `ui.tab_group_start` / `ui.tab_end` create full page structures with local tab bars.
- **Dynamic token patches** – callbacks can return patch actions (`set_text`, `insert_table_row`, `toggle_section`, etc.) that modify the live UI instantly.
- **Localhost & shared deployment** – safe single‑user mode and authenticated team‑sharing mode.
- **OS command execution** – shell commands run after explicit browser confirmation; output goes to a terminal div (blocking, with timeout).
- **Volatile memory lifespan** – quitting the server wipes all temporary state; nothing is persisted to disk by default.
- **Multi‑file projects** – the engine adds your script’s directory to `sys.path` so you can import helper modules.
- **Keyword argument support** – `target_id`, `css`, `class_` are all recognised as named arguments.
- **File watcher (`--watch`)** – auto‑reloads the script on changes, re‑compiles tokens, and refreshes all browsers.
- **SSE heartbeat** – keeps connections alive on mobile or proxy networks.
- **Debounced form sync** – batches rapid input changes to reduce network load.
- **Explicit button types** – dynamic buttons carry `type="button"` to avoid accidental form submissions.

---

## 🚧 In progress / experimental

- **Project bundling** – Mode 2 can now download an entire project directory and serve it locally (`--connect`).
- **Auto‑install dependencies** – with `--allow-deps`, a temporary venv is created and `pybro.toml` requirements are installed.
- **Built‑in TLS / SSL** – HTTPS is supported via `--ssl`. You can provide your own certificate or let Pybro generate a self‑signed one (Python ≥ 3.9).
- **Signed token‑tree distribution** – in shared mode, the master builds an HMAC‑SHA256 signed tree that the client verifies before execution.

---

## 📦 Installation

```bash
pip install -e .
```

Run this from the pybro_ui/ directory.
It makes the pybro command available in your current environment.

---

##⚡ Quick start

1. Write a blueprint script

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

2. Run it

```bash
pybro my_tool.py
```

Open http://localhost:8080 in any browser.

3. Try an example

```bash
pybro examples/mytool.py
```

---

## 🔐 Deployment modes

Mode 0 – Localhost

```bash
pybro my_tool.py
```

Server listens only on 127.0.0.1. Ideal for personal tools.

Mode 1 – Shared Team Hub

```bash
pybro my_tool.py --shared --key mysecret
```

Binds to 0.0.0.0. Anyone on your LAN can connect with the correct key (via ?key=... or the X-Pybro-Key header).
If you omit --key, a random token is generated and printed.
Add --connectable to build a signed project tree for secure distribution.

Mode 2 – Distributed Sandbox Client (experimental)

```bash
pybro --connect 192.168.1.45:8080 --key mysecret
```

Downloads the remote project to a temporary directory, executes callbacks locally, and cleans up on exit.
Use --keep-script to preserve the downloaded files.
If the remote project lists dependencies in pybro.toml, add --allow-deps to install them in an ephemeral venv.
Tip: on the same machine, use --port 8081 to avoid conflicts with the master.

---

## 📐 Supported UI tokens

Every visual token accepts the optional keyword arguments css (inline styles) and class_ (CSS class).
The global theme can be set with:

```python
ui.root_css({"--bg": "#0a0e17", "--accent": "#f97316", ...})
```

### Default CSS custom properties:

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

### Structural tokens

Call Description
ui.page_start("Name") Start a named page
ui.page_end() End the current page
ui.tab_group_start() Open a tab container
ui.tab_start("Name") Start a named tab
ui.tab_end() End the current tab
ui.tab_group_end() Close the tab group
ui.row_start() Begin a horizontal flex row
ui.row_end() End the current row

### Visual tokens

Call Type Example
ui.title(text) Heading ui.title("Dashboard")
ui.input_text(id, label) Text input ui.input_text("host", "Target")
ui.checkbox(id, label) Checkbox ui.checkbox("verbose", "Verbose")
ui.dropdown(id, label, options) Drop‑down ui.dropdown("mode", "Mode", ["A","B"])
ui.text_area(id, label) Read‑only output ui.text_area("log", "Log")
ui.math_compute(target_id, formula) Client‑side formula ui.math_compute("sum", "{a}+{b}")
ui.button_callback(text, func, target_id?) Python callback button ui.button_callback("Run", "my_func", "out")
ui.os_command(cmd, desc, target_id) OS command (with confirmation) ui.os_command("ping -c1 1.1.1.1", "Ping", "out")
ui.table(headers, rows) Static table ui.table(["Name","Age"], [["A",30]])
ui.root_css(vars_dict) Global theme ui.root_css({"--accent":"red"})

Callbacks receive a dict of all current input values, keyed by id. Checkboxes are bool, others are str.

Dynamic UI updates (token patches)

Callbacks can return a list of patch dicts to modify the UI instantly.
Supported actions: set_text, set_label, set_css, set_class, insert_table_row, set_table_rows, set_options, toggle_section.
See TOKENS.md and CSS_CUSTOM.md for full details.

---

## 🧪 Advanced options

Flag Effect
--port 9090 Change the listening port (default 8080)
--verbose Print Apache‑style HTTP request logs
--key <secret> Set the security key explicitly
--keep-script Mode 2: retain the downloaded project after exit
--ssl Serve over HTTPS
--cert-file <path> TLS certificate (PEM)
--key-file <path> TLS private key (PEM)
--allow-deps Mode 2: install dependencies from pybro.toml
--entrypoint <file> Mode 2: specify main script filename
--os-timeout <int> Timeout for OS commands (seconds, default 5)
--watch Watch script for changes and auto‑reload

---

## 🔧 Technical notes

· Variable resolution: Simple top‑level lists/dicts are resolved at parse time. Complex expressions and function calls are not yet supported.
· OS commands: Must match the exact string defined in the script. They run with a configurable timeout and capture output. Only trusted scripts should define them; an optional allow‑list is available in pybro.toml.
· Real‑time updates: Server‑Sent Events (SSE) push token and form‑state changes to all connected browsers.
· Signed token tree: In shared/connectable mode, the master signs the project with HMAC‑SHA256; the client verifies before executing.
· Multi‑file projects: The script’s directory is added to sys.path, so relative imports work.
· button_callback target_id: Can be a positional argument (third) or keyword (target_id="...").
· Minimum Python: 3.8; some optional features (TOML, auto‑SSL) require 3.9+.

---

## 🗺️ Roadmap

· Developer experience
  · Clear parser error messages with line numbers
  · ~~--watch flag~~ ✅ done
· New built‑in widgets
  · Password field, sliders, date pickers, file upload stubs
  · ui.markdown(text) for static Markdown blocks
  · Dark/light theme toggle
· Layout & navigation
  · ~~Tabs and multi‑page layouts~~ ✅ done
· Security hardening
  · Configurable command allow‑list (already available via pybro.toml)
  · Full sandboxing options for Mode 2 clients
· Advanced scripting
  · Optional persistent state (--state-file)
  · Custom CSS/JS injection with security gates

---

## 📚 Documentation & Project Structure

```
pybro_ui/
├── README.md               ← this file
├── LICENSE
├── pyproject.toml
├── docs/
│   ├── TECHNICAL.md         ← architecture & internals
│   ├── TOKENS.md            ← full token & patch reference
│   ├── CSS_CUSTOM.md        ← styling & customisation guide
│   └── pybro.toml           ← annotated config template
├── examples/
│   ├── mytool.py
│   ├── netsweep/            (multi‑file project example)
│   └── ...
└── src/
    └── pybro/
        ├── __init__.py      ← the `ui` stub
        ├── server.py        ← runtime engine
        ├── index.html       ← front‑end shell
        └── static/          ← modular front‑end JS
```

Full technical reference: TECHNICAL.md

---

## 📜 License

MIT – do whatever you want, just don’t blame us if you point an OS command at something dangerous.
