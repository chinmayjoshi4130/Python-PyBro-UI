# Pybro

Pybro is a zero‑dependency UI sketchpad for Python developers.  
Write your backend logic (APIs, data pipelines, automation scripts), wrap it in a reactive UI using pure Python, and launch a live browser interface in under 10 seconds.

Use Pybro to validate workflows and gather team feedback before committing to a heavy frontend stack.  
No Node.js, no build systems, no HTML required.

> **Note**  
> Pybro was built for Termux on Android and is used daily with Chrome, Brave, and DuckDuckGo — making it the perfect companion for prototyping on the go.  
> Most core functionality is well‑tested, but device and browser coverage is still growing.  
> If you hit a bug, please open an issue with reproduction steps and your device / browser details.

> ⚠️ **Early Development**  
> Pybro is under active development and may change rapidly.  
> Expect breaking changes, incomplete docs, and the occasional rough edge.  
> It is prototyping‑first, though many internal automations run on it long‑term without issue.  
> Broad testing is still underway — feedback, bug reports, and pull requests are extremely welcome.

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
- **Dynamic token patches** – callbacks can return patch actions (`set_text`, `insert_table_row`, `toggle_section`, `set_progress`, etc.) that modify the live UI instantly. Patches target tokens by `target_id` (no fragile indexes).
- **Localhost & shared deployment** – safe single‑user mode and authenticated team‑sharing mode.
- **Distributed sandbox client** – Mode 2 downloads the signed project tree and mirrors the master’s UI, with automatic CSS detection.
- **OS command execution** – shell commands run after explicit browser confirmation; output goes to a terminal div (blocking, with timeout). Uses `shlex.split()` to avoid shell injection.
- **Volatile memory lifespan** – quitting the server wipes all temporary state; nothing is persisted to disk by default. Perfect for throwaway prototypes.
- **Multi‑file projects** – the engine adds your script’s directory to `sys.path` so you can import helper modules.
- **Keyword argument support** – `target_id`, `css`, `class_` are all recognised as named arguments.
- **File watcher (`--watch`)** – auto‑reloads the script on changes, re‑compiles tokens, and refreshes all browsers.
- **SSE heartbeat** – keeps connections alive on mobile or proxy networks.
- **Debounced form sync** – batches rapid input changes to reduce network load.
- **Explicit button types** – dynamic buttons carry `type="button"` to avoid accidental form submissions.
- **Modern widget set** – password fields, toggle switches, sliders, date pickers, progress bars, Markdown blocks, and generic HTML5 inputs are built in.

---

## 🚧 In progress / experimental

- **Auto‑install dependencies** – with `--allow-deps`, a temporary venv is created and `pybro.toml` requirements are installed.
- **Built‑in TLS / SSL** – HTTPS is supported via `--ssl`. You can provide your own certificate or let Pybro generate a self‑signed one (Python ≥ 3.9).
- **Signed token‑tree distribution** – in shared mode, the master builds an HMAC‑SHA256 signed tree that the client verifies before execution.
- **Persistent state** – optional `--state-file` flag to save/load form state across restarts (planned).

---

## 📦 Installation

```bash
pip install -e .
```

Run this from the pybro_ui/ directory.
It makes the pybro command available in your current environment.

---

##⚡ Quick start

### 1. Write a blueprint script

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

### 2. Run it

```bash
pybro my_tool.py
```

Open http://localhost:8080 in any browser.

### 3. Try an example

```bash
pybro examples/mytool.py
```

---

## 🔐 Deployment modes

### Mode 0 – Localhost

```bash
pybro my_tool.py
```

Server listens only on 127.0.0.1. Ideal for personal tools.

### Mode 1 – Shared Team Hub

```bash
pybro my_tool.py --shared --key mysecret
```

Binds to 0.0.0.0. Anyone on your LAN can connect with the correct key (via ?key=... or the X-Pybro-Key header).
If you omit --key, a random token is generated and printed.
Add --connectable to build a signed project tree for secure distribution.

### Mode 2 – Distributed Sandbox Client (experimental)

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

| Call | Description |
| :--- | :--- |
| `ui.page_start("Name")` | Start a named page |
| `ui.page_end()` | End the current page |
| `ui.tab_group_start()` | Open a tab container |
| `ui.tab_start("Name")` | Start a named tab |
| `ui.tab_end()` | End the current tab |
| `ui.tab_group_end()` | Close the tab group |
| `ui.row_start()` | Begin a horizontal flex row |
| `ui.row_end()` | End the current row |
| `ui.section_start("id", visible=True)` | Start a hideable section |
| `ui.section_end()` | End the section |

### Visual tokens

| Call | Type | Example |
| :--- | :--- | :--- |
| `ui.title(text)` | Heading | `ui.title("Dashboard")` |
| `ui.input_text(id, label)` | Text input | `ui.input_text("host", "Target")` |
| `ui.checkbox(id, label)` | Checkbox | `ui.checkbox("verbose", "Verbose")` |
| `ui.dropdown(id, label, options)` | Drop‑down | `ui.dropdown("mode", "Mode", ["A","B"])` |
| `ui.text_area(id, label)` | Read‑only output | `ui.text_area("log", "Log")` |
| `ui.math_compute(target_id, formula)` | Client‑side formula | `ui.math_compute("sum", "{a}+{b}")` |
| `ui.button_callback(text, func, target_id?)` | Python callback button | `ui.button_callback("Run", "my_func", "out")` |
| `ui.os_command(cmd, desc, target_id)` | OS command (with confirmation) | `ui.os_command("ping -c1 1.1.1.1", "Ping", "out")` |
| `ui.table(headers, rows)` | Static table | `ui.table(["Name","Age"], [["A",30]])` |
| `ui.root_css(vars_dict)` | Global theme | `ui.root_css({"--accent":"red"})` |
| `ui.markdown(text)` | Rendered Markdown block | `ui.markdown("## Welcome\n\nHello world")` |
| `ui.slider(id, label, min, max, step=1)` | Range slider | `ui.slider("vol", "Volume", 0, 100, 5)` |
| `ui.password(id, label)` | Password field | `ui.password("secret", "API Key")` |
| `ui.toggle(id, label, checked=False)` | Toggle switch | `ui.toggle("dark", "Dark Mode", True)` |
| `ui.progress(id, label, value=0, max=100)` | Progress bar | `ui.progress("scan", "Scan Progress", 0, 100)` |
| `ui.date(id, label)` | Date picker | `ui.date("start", "Start Date")` |
| `ui.input(id, label, type="text")` | Generic HTML5 input | `ui.input("email", "Email", "email")` |

Callbacks receive a dict of all current input values, keyed by id. Checkboxes are bool, others are str. Slider, password, date, and generic inputs behave identically to input_text from the callback’s perspective.

### Dynamic UI updates (token patches)

Callbacks can return a list of patch dicts to modify the UI instantly.
Supported actions: set_text, set_label, set_css, set_class, insert_table_row, set_table_rows, set_options, toggle_section, set_progress.
All patches target tokens by target_id (sections use section_id). The deprecated token_index has been removed.
See TOKENS.md and CSS_CUSTOM.md for full details.

---

## 🧪 Advanced options

| Flag | Effect |
| :--- | :--- |
| `--port 9090` | Change the listening port (default 8080) |
| `--verbose` | Print Apache‑style HTTP request logs |
| `--key <secret>` | Set the security key explicitly |
| `--keep-script` | Mode 2: retain the downloaded project after exit |
| `--ssl` | Serve over HTTPS |
| `--cert-file <path>` | TLS certificate (PEM) |
| `--key-file <path>` | TLS private key (PEM) |
| `--allow-deps` | Mode 2: install dependencies from `pybro.toml` |
| `--entrypoint <file>` | Mode 2: specify main script filename |
| `--os-timeout <int>` | Timeout for OS commands (seconds, default 5) |
| `--watch` | Watch script for changes and auto‑reload |

---

## 🔧 Technical notes

- Variable resolution: Simple top‑level lists/dicts are resolved at parse time. Complex expressions and function calls are not yet supported.
- OS commands: Must match the exact string defined in the script. They run with a configurable timeout and capture output. Only trusted scripts should define them; an optional allow‑list is available in pybro.toml. Execution uses shlex.split() and shell=False to prevent injection.
- Real‑time updates: Server‑Sent Events (SSE) push token and form‑state changes to all connected browsers.
- Signed token tree: In shared/connectable mode, the master signs the project with HMAC‑SHA256; the client verifies before executing.
- Multi‑file projects: The script’s directory is added to sys.path, so relative imports work.
- button_callback target_id: Can be a positional argument (third) or keyword (target_id="...").
- Patch targeting: All patches use target_id (or section_id for sections). No fragile token indexes.
- Minimum Python: 3.8; some optional features (TOML, auto‑SSL) require 3.9+.

---

## 🗺️ Roadmap

- Developer experience
  - Clear parser error messages with line numbers
  - ~~--watch flag~~ ✅ done
- New built‑in widgets
  - ~~Password field~~ ✅ done
  - ~~Sliders~~ ✅ done
  - ~~Date pickers~~ ✅ done
  - ~~Markdown blocks~~ ✅ done
  - ~~Toggle switches~~ ✅ done
  - ~~Progress bars~~ ✅ done
  - ~~Generic HTML5 inputs~~ ✅ done
  - File upload stubs
  - Dark/light theme toggle
- Layout & navigation
  - ~~Tabs and multi‑page layouts~~ ✅ done
  - ~~Hideable sections with state preservation~~ ✅ done
- Security hardening
  - ~~Command allow‑list (pybro.toml)~~ ✅ done
  - ~~OS command sandboxing (shlex.split, shell=False)~~ ✅ done
  - Full sandboxing options for Mode 2 clients
- Advanced scripting
  - Optional persistent state (--state-file)
  - Custom JS injection with security gates

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
        ├── state.py         ← shared globals & locks
        ├── tree.py          ← tree model & operations
        ├── parser.py        ← AST parser
        ├── handler.py       ← HTTP & SSE handler
        ├── watcher.py       ← file watcher thread
        ├── server.py        ← entry point & CLI
        ├── index.html       ← front‑end shell
        └── static/          ← modular front‑end JS
```

Full technical reference: TECHNICAL.md

---

## 📜 License

MIT – do whatever you want, just don’t blame us if you point an OS command at something dangerous.
