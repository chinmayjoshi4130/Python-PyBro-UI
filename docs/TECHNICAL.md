# Pybro Technical & User Manual

This document is the complete guide to pybro, a zero‑dependency Python UI runtime for automation scripts. It covers everything from installation and quick start to the internal architecture, API references, and security model. Use it as your single source of truth for both using and extending pybro.

---

## 1. What is Pybro?

Pybro parses declarative UI code from a Python automation script using the standard AST module, compiles it into a list of JSON tokens, and serves them through a lightweight HTTP server. A static frontend (`index.html`) renders the tokens as a responsive web dashboard with real‑time updates for form state and UI changes.

Key characteristics:

- **Zero external dependencies** – the engine uses only Python standard library modules.
- **In‑memory only** – no database, no file storage; state vanishes when the process stops.
- **Reactive** – client‑side math, bi‑directional form sync, and automatic UI refresh via Server‑Sent Events.
- **Modular** – scripts can import helper modules from their own directory.
- **Portable** – runs anywhere Python does, including Termux on Android.

---

## 2. Installation

Clone the repository and install in development mode:

```bash
pip install -e .
```

This makes the pybro command available globally in your environment.

---

3. Quick Start

1. Write a blueprint script (e.g. my_tool.py):

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

4. UI Token Catalogue

Every visual token accepts optional keyword arguments css (dictionary of inline styles) and class_ (CSS class string). Some tokens also recognise target_id.

Structural Tokens (Pages & Tabs)

Python call Token type Description
ui.page_start("Name") PAGE_START Begins a new page. All following tokens belong to this page until PAGE_END.
ui.page_end() PAGE_END Ends the current page.
ui.tab_group_start() TAB_GROUP_START Opens a tab group inside the current page.
ui.tab_start("Tab Name") TAB_START Starts a named tab within the tab group.
ui.tab_end() TAB_END Ends the current tab.
ui.tab_group_end() TAB_GROUP_END Ends the tab group.

Visual Tokens

Call Token Type Description Key Fields
ui.title(text) UI_TITLE Header block. text
ui.row_start() LAYOUT_ROW_START Begins a horizontal flex row. –
ui.row_end() LAYOUT_ROW_END Ends the current row, returns to vertical stacking. –
ui.input_text(id, label) UI_INPUT Text entry field. id, label
ui.checkbox(id, label) UI_CHECKBOX Boolean toggle. id, label
ui.dropdown(id, label, options) UI_DROPDOWN Drop‑down selection. id, label, options
ui.text_area(id, label) UI_TEXT_AREA Read‑only output textarea. id, label
ui.math_compute(target_id, formula) UI_MATH_COMPUTE Client‑side expression with {placeholder} substitution. target_id, formula
ui.button_callback(text, function, target_id?) UI_CALLBACK_BUTTON Triggers a Python function. target_id can be positional or keyword. text, callback_name, target_id
ui.os_command(cmd, desc, target_id) OS_GATEKEEPER Shell command with gatekeeper confirmation. Output is shown after the command completes (blocking execution). cmd, desc, target_id
ui.table(headers, rows) UI_TABLE Static table. headers, rows
ui.root_css(vars_dict) UI_ROOT_CSS Overrides global CSS custom properties. css_vars

---

5. Styling & Theme

The frontend uses CSS variables for consistent theming. Default values:

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

Override them globally with ui.root_css():

```python
ui.root_css({"--bg": "#ffffff", "--accent": "#ff6600"})
```

Individual components can receive css and class_ arguments. For UI_TITLE, these are applied directly to the <h1> element; for all other tokens, they are applied to the wrapper <div>.

---

6. Callbacks & Form Data

Callback functions (referenced in button_callback) receive a single dictionary with the current values of all input widgets, keyed by their id. Checkbox values are bool, everything else is str.

Example:

```python
def my_callback(form):
    host = form['host']          # string
    verbose = form['verbose']    # bool
    return f"Host: {host}, Verbose: {verbose}"
```

Dynamic UI Updates (Token Patches)

A callback may return a list of patch dictionaries instead of a plain string. Each patch modifies a token in the running COMPILED_TOKENS list, and the UI is instantly refreshed for all connected clients.

Available patch actions:

Action Effect Extra Fields
set_text Changes UI_TITLE.text or UI_CALLBACK_BUTTON.text value (str)
set_label Changes a label (UI_INPUT, UI_CHECKBOX, etc.) value (str)
set_css Replaces inline CSS value (dict)
set_class Replaces CSS class value (str)
insert_table_row Appends a row to a UI_TABLE row (list)
set_table_rows Replaces all rows rows (list of lists)
set_options Replaces dropdown options options (list)

Note: token_index refers to the zero‑based position of the token in COMPILED_TOKENS. The first ui.* call is index 0, and structural tokens (PAGE_START, ROW_START, etc.) are included in the indexing. Inspect /tokens in the browser to see the exact order.

Example callback that adds a row to a table and updates a title:

```python
def handle_click(form):
    return [
        {"action": "insert_table_row", "token_index": 2, "row": [form['name'], "active"]},
        {"action": "set_text", "token_index": 0, "value": "Updated Dashboard"}
    ]
```

The server applies patches, broadcasts tokens_updated via SSE, and the frontend re‑renders.

---

7. Deployment Modes

Mode 0 – Localhost (Default)

```bash
pybro my_tool.py
```

Binds to 127.0.0.1. No authentication. The browser opens automatically.

Mode 1 – Shared Team Hub

```bash
pybro my_tool.py --shared --key mysecret
```

Binds to 0.0.0.0. Access requires the key via ?key=... or X-Pybro-Key header. If --key is omitted, a random hex token is generated and printed. With --connectable, the master also builds a cryptographically signed project tree that remote clients can download.

Mode 2 – Distributed Sandbox Client (Experimental)

```bash
pybro --connect 192.168.1.45:8080 --key mysecret
```

Fetches the signed token tree from the remote master, extracts project files to a temporary directory, imports the script, and serves the UI locally on 127.0.0.1. Callbacks and OS commands run on the client side. Temporary files are deleted on exit, unless --keep-script is used. If the remote project declares external dependencies (pybro.toml), pass --allow-deps to install them in an ephemeral venv.

Tip: If running master and client on the same machine, give the client a different port with --port 8081.

---

8. Advanced Command‑Line Options

Flag Effect
--port 9090 Change the listening port (default 8080).
--verbose Print Apache‑style HTTP request logs.
--key <secret> Set the security key explicitly (shared mode / --connect).
--keep-script In Mode 2, retain the downloaded project directory after shutdown.
--ssl Serve over HTTPS. Requires --cert-file/--key-file or auto‑generation (Python ≥ 3.9).
--cert-file <path> Path to TLS certificate (PEM).
--key-file <path> Path to TLS private key (PEM).
--allow-deps In Mode 2, auto‑install dependencies from pybro.toml into a temporary venv.
--entrypoint <file> In Mode 2, specify the main script filename (default: main.py or first .py).
--os-timeout <int> Timeout for OS commands in seconds (default 5).
--watch Watch the script file for changes; re‑compile tokens and push UI updates live.

---

9. Architecture & Internal Flow

```
User Script (.py)
     │
     ▼
 AST Parser (PybroUIParser)
     │  (uses TARGET_MODULE for function‑call eval)
     ▼
 COMPILED_TOKENS (global list)
     │
     ├─► EphemeralServer (HTTP)
     │      ├─ GET  /tokens          → JSON tokens
     │      ├─ GET  /stream          → SSE updates (form state, token changes)
     │      ├─ POST /broadcast_state → share form data
     │      ├─ POST /execute_os      → execute OS command (blocking, returns result)
     │      ├─ POST /trigger_callback→ invoke Python function, apply patches
     │      └─ GET  /token-tree      → signed project bundle (--connectable)
     │
     └─► Frontend (index.html)
            renders tokens, evaluates math, syncs form, handles page/tab navigation
```

Key components:

· PybroUIParser – walks the script AST; collects assignments and UI calls, populates COMPILED_TOKENS. If given a module, it can evaluate simple function calls in assignments (e.g. HEADERS = get_headers()) so that the token receives the actual result, not a placeholder string.
· TARGET_MODULE – the imported user script. Used for callbacks and (optionally) for function evaluation during parsing.
· EphemeralServer – handles HTTP requests, SSE broadcasting, command execution, and token patching.
· broadcast_event() – pushes events to all connected SSE clients using a thread‑safe queue.

---

10. Server API Reference

Static Files

Endpoint Method Description
/ or /index.html GET Returns the frontend HTML.

Data Endpoints (require authentication in shared mode)

Endpoint Method Authentication Description
/tokens GET Required Returns the current COMPILED_TOKENS as JSON.
/stream GET Not checked (inherits page auth) SSE stream for real‑time events (form state, token updates).
/token-tree GET Required (master with --connectable) Returns the signed project bundle.
/broadcast_state POST Required Merges form_state into shared state and broadcasts.
/execute_os POST Required Validates and executes a registered OS command. Returns the command’s output in the HTTP response.
/trigger_callback POST Required Calls a Python function with form state, applies patches if returned.

SSE Events

Event Data Description
state_update JSON object (form state) Current shared form state. Sent on connect.
callback_output {"output": "...", "target_id": "..."} Plain string result from a callback.
tokens_updated JSON array (new tokens) Tokens were modified (callback patches or --watch reload). Frontend re‑renders.
heartbeat (SSE comment) Keeps connection alive.

---

11. Authentication & Session Key

In shared mode (or when --connectable is used), a session key is generated or supplied. The key must be included in:

· The URL query string ?key=<key>
· Or the X-Pybro-Key HTTP header.

The /stream endpoint does not check the key after the initial page load, because the page itself already includes the key.

Signed Token Tree

When --connectable is active, the master constructs a JSON payload containing:

· ui_tokens
· files (a dictionary of relative paths to file contents for all bundled .py files)
· requires (external dependencies)

This payload is signed with HMAC‑SHA256 using the session key. The client verifies the signature to ensure code integrity and authenticity.

---

12. OS Command Execution & Security

Commands registered with ui.os_command() must exactly match an OS_GATEKEEPER token present in the compiled tokens. This prevents arbitrary command injection from the frontend.

The command is executed synchronously using subprocess.run with shell=True (to support pipes and redirects). The process runs to completion, and its output is captured and returned to the frontend, which displays it in the designated terminal area. Timeout is configurable via --os-timeout (default 5 seconds).

Security note: Because the command is executed with shell=True, only trusted script authors should define OS commands. A future version will add a configurable allow‑list of permitted executables.

---

13. Configuration File – pybro.toml

For multi‑file projects or when distributing a project (Mode 2), a pybro.toml file placed in the project root controls bundling and dependencies.

```toml
[distribute]
# Files or directories to include in the distributed bundle.
# Default: all .py files (excluding .git, __pycache__, venv, etc.)
include = ["main.py", "scanner/", "utils.py"]

# Pip dependencies required by the project.
requires = ["requests>=2.25", "rich"]
```

The master uses this file to build the signed token tree. The client installs requires only if --allow-deps is passed.

---

14. AST Parser Details

The parser (PybroUIParser) extends ast.NodeVisitor. It processes:

· Top‑level assignments – constants are evaluated with ast.literal_eval; function calls are evaluated via _safe_eval if a module is provided. Results are stored in var_table.
· UI calls – ui.title(...), ui.input_text(...), etc. Arguments are either literal values, variable names resolved from var_table, or function calls that _safe_eval attempts to execute.
· Keyword arguments – css, class_, and target_id are explicitly recognized and transferred to the token.

Limitations:

· Only simple function calls (e.g. my_func(args)) are evaluated; attribute chains like module.func() are not.
· The function must exist in the module’s namespace and be safe to call at parse time (no persistent side‑effects).

---

15. Blocking OS Execution Internals

When a valid OS command is triggered via the gatekeeper:

1. The server validates the command against existing OS_GATEKEEPER tokens.
2. subprocess.run is called with the command string, shell=True, capture_output=True, text=True, and the configured timeout.
3. If the command completes successfully, its stdout (or stderr if stdout is empty) is HTML‑escaped and returned in the HTTP response.
4. If the command times out or raises an exception, an appropriate error message is returned.
5. The frontend immediately displays the result in the target terminal <div>.

No SSE streaming is used for OS output in the current version.

---

16. File Watcher (--watch)

When --watch is active (master modes only), a daemon thread polls the script file’s modification time every 2 seconds. On a change:

· The AST is re‑parsed and COMPILED_TOKENS is replaced.
· The target module is re‑imported (so callbacks pick up code changes).
· If --connectable is on, the token tree is rebuilt.
· A tokens_updated SSE event is broadcast, causing all browsers to re‑render.

Errors are logged to the console but do not stop the watcher.

---

17. Multi‑Page & Tab Support

Pybro now supports multiple pages and tabs within a page. Pages are created with ui.page_start("Page Name") / ui.page_end(). Each page appears as a navigation button at the top of the dashboard, and only the active page’s content is shown.

Inside a page, you can add a tab group with ui.tab_group_start() / ui.tab_group_end(). Individual tabs are defined with ui.tab_start("Tab Name") / ui.tab_end(). The frontend builds a local tab bar and shows only the active tab’s content. All form state is preserved when switching pages or tabs because the underlying DOM nodes are hidden/shown, not destroyed.

---

18. Multi‑User & State

Currently, all connected clients share a single form state (shared_form_state). There is no user isolation or session management. This works well for a single user with multiple devices (or a shared dashboard), but true multi‑user support is a planned enhancement.

---

19. Limitations & Planned Features

Current limitations:

· Complex expressions, nested function definitions, and imports are not evaluated in assignments (only simple calls and literals).
· OS commands are executed synchronously (blocking); long‑running commands may cause the browser to wait. Real‑time streaming is planned for a future release.
· SSE streams are not authenticated after the initial connection.
· Callbacks are restricted to module‑level functions (no lambdas/closures).
· No persistent state across restarts.
· Table cells that contain HTML‑like strings are rendered as plain text only (no XSS risk).

Roadmap highlights:

· Clear parser error messages with line numbers.
· New widgets: password fields, sliders, date pickers, file upload stubs.
· ui.markdown(text) for static documentation blocks.
· Dark/light theme toggle.
· Configurable command allow‑list for os_command.
· Persistent state with --state-file.
· Custom CSS/JS injection with security gating.
· Full sandboxing for Mode 2 clients.
· Return of streaming OS output (optionally).

---

20. Project Structure

```
pybro_ui/
├── pyproject.toml
├── README.md
├── examples/
│   ├── mytool.py
│   └── netsweep/
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

21. License

MIT – do whatever you want, just don’t blame us if you point an OS command at something dangerous.

For the very latest updates and community contributions, see the repository issues and pull requests.
