# TECHNICAL.md — Pybro Internals

Pybro is a zero‑dependency dashboard framework that compiles a Python DSL (calls to a `ui` object) into an interactive HTML UI served over HTTP.  
This document explains every file in the project, its role, and how the pieces fit together.

---

## Project file layout

```

pybro_ui/
├── LICENSE
├── README.md
├── pyproject.toml                # Python packaging metadata
├── docs/
│   ├── TECHNICAL.md              # This file
│   ├── TOKENS.md                 # Token reference (UI components & patches)
│   ├── CSS_CUSTOM.md             # Styling & customisation guide
│   └── pybro.toml                # Annotated configuration template
├── examples/
│   ├── all_tokens_v4.py
│   ├── all_patches_demo.py
│   ├── css_style_example/
│   │   ├── custom_style_demo.py
│   │   └── custom_theme.css
│   ├── mytool.py
│   ├── netsweep/
│   │   ├── main.py
│   │   ├── scanner.py
│   │   └── utils.py
│   │   └── pybro.toml
│   ├── pybro_demo/
│   │   ├── main.py
│   │   ├── scanner.py
│   │   ├── textarea_test.py
│   │   └── pybro.toml
│   │   └── theme.css
│   └── section_demo.py
└── src/
└── pybro/
├── init.py           # No‑op stub so user scripts can import ui
├── server.py             # Core engine: AST parsing, tree, HTTP server, SSE
├── index.html            # Single HTML shell, loads the frontend module
└── static/
├── utils.js          # Small helpers (escape, auth headers, CSS injection)
├── state.js          # Form state capture/sync, reactive math
├── renderer.js       # Builds the DOM from the token tree, page/tab switching
├── sse.js            # SSE client: reconnects and dispatches events
├── gatekeeper.js     # OS command modal, execution request to server
├── poller.js         # Optional fallback polling for token updates
└── app.js            # Main runtime: wires modules together, manages UI lifecycle

```

User projects typically contain a `pybro.toml` (optional) and one or more Python scripts that use the `ui` DSL.

---

## `src/pybro/__init__.py` — The UI stub

```python
class _UIStub:
    """No‑op stub that accepts any attribute call."""
    def __getattr__(self, name):
        def stub(*args, **kwargs):
            pass
        return stub

ui = _UIStub()
```

Purpose:
User scripts import from pybro import ui and then call ui.page_start(...), ui.input_text(...), etc. Without this stub, importing the script would fail because the ui module doesn’t really exist at runtime. The stub makes every call a harmless no‑op, so the user’s script can be imported into the server process without errors. The real UI parsing is done by server.py’s AST visitor — it never uses this stub.

Important:
The stub must be in a package named pybro so that from pybro import ui resolves correctly. The server’s sys.path must include the project directory to find this package.

---

server.py — The engine

Overview

server.py is the entire backend. It does everything:

· Parses the user script with ast and builds a tree of UI nodes (UINode).
· Starts an HTTP server with endpoints for tokens, SSE, OS execution, and callbacks.
· Maintains a global tree lock for thread‑safe mutation.
· Supports two modes: Master (serves UI) and Distributed Client (downloads code & tokens from a master).

Architecture highlights

Tree data model (UINode)

Every UI element becomes a node. The root is UINode('ROOT'). Nodes have:

· type: e.g., "PAGE_START", "UI_INPUT", "UI_TEXT_AREA", "SECTION_START"...
· attrs: a dict of properties (id, label, visible, etc.)
· children: a list of child nodes (for containers like sections, rows, pages, tabs).

This replaces the old flat COMPILED_TOKENS list, making patching by target_id robust and eliminating index‑based fragility.

Flattening

flatten_tree(root) recursively walks the tree and produces the flat token list that the frontend expects, automatically inserting end tokens (PAGE_END, SECTION_END, etc.) for containers.

Thread safety

A tree_lock (threading.Lock()) guards all reads and writes to UI_ROOT. Before any endpoint reads the tree, it acquires the lock and flattens a snapshot. Before any mutation, it locks, changes nodes, flattens, and broadcasts the new tokens via SSE.

AST Parser (PybroUIParser)

· Inherits from ast.NodeVisitor.
· Creates a UINode('ROOT') and a stack of container nodes.
· On every ui.xxx() call, it extracts arguments using ast.literal_eval (constants) or stores symbolic names for later resolution (e.g., table row variables like ROWS).
· Does not execute any user code during parsing. Only constants are evaluated.
· Builds the UI tree directly.

Deferred symbol linker (link_tree)

After the module is loaded (so variables like ROWS exist), link_tree walks the tree and replaces headers_ref / rows_ref with the actual values from the module.

HTTP Server (EphemeralServer)

Endpoints:

· GET /tokens — returns the flattened token list (JSON).
· GET /stream — SSE event stream.
· GET /token-tree — signed bundle of tokens + files for distributed mode.
· GET /custom.css — optional user CSS.
· GET / or /index.html — serves the HTML shell with optional custom CSS injection and poll‑interval script.
· GET /static/... — serves static JS/CSS files from the static/ folder.
· POST /broadcast_state — receives form state from a client and broadcasts to others.
· POST /execute_os — validates an OS command against the gatekeeper tokens, runs it with shlex.split (no shell=True), optionally checks an allowlist, and updates the target UI_TEXT_AREA.
· POST /trigger_callback — calls the registered Python function, applies any patches returned, persists plain‑text output into the tree, and broadcasts updates.

Security hardening

· OS commands use shlex.split() and shell=False → no shell injection.
· An optional allowed_commands list in pybro.toml restricts which programs can be executed.
· Callback execution is wrapped with redirect_stdout/redirect_stderr to prevent accidental leaks.

File watcher (watch_script)

If --watch is used, a background thread reloads the script, re‑parses the AST, links symbols, and atomically replaces UI_ROOT under the lock. It passes the connectable flag correctly (fixing the earlier NameError).

Mode 2 (Distributed Client)

When --connect is used, the server fetches the signed token tree from a master, reconstructs a UI_ROOT tree from the flat tokens using build_tree_from_flat(), extracts the codebase to a temp directory, optionally installs deps, and then acts as a local server mirroring the master’s UI.

---

index.html — The shell

This is a minimal HTML file. It contains:

· All CSS styles for the dashboard (custom properties, component styling, modals, etc.).
· A <div id="page-nav"> placeholder for page buttons.
· A <div id="app-canvas"> where the UI is rendered.
· A gatekeeper modal (hidden by default).
· A small SSE status dot.
· One line that loads the frontend as a module:
  ```html
  <script type="module" src="/static/app.js"></script>
  ```
· At the end of <body>, the server injects a <script> tag with window.pybroPollInterval so the poller module knows the interval.

No other JavaScript is embedded — all logic resides in static/.

---

Frontend modules (static/)

All files are ES modules (.js), loaded directly by the browser without any build step.

utils.js

Exports small helper functions:

· escapeHtml(text) — prevents XSS when inserting user‑supplied text.
· getAuthHeaders() — reads the session token from sessionStorage and returns an object for fetch.
· applyRootCSS(cssVars) — sets CSS custom properties on :root.
· applyComponentCSS(wrapper, token) — applies inline css and class from a token to a DOM element.

Used by other modules.

state.js

Manages form state and reactive math.

· getFormState() — collects values of all visible input and select elements.
· captureFormState() / restoreFormState() — saves/restores form state across UI rebuilds.
· debouncedSyncFormState() — sends the current state to the server (/broadcast_state) after a short delay.
· evaluateReactiveMath() — re‑evaluates all registered math formulas, replacing placeholders like {some_id} with current form values.
· setMathFormulas(formulas) / getMathFormulas() — getter/setter for the global formula list.

renderer.js

The largest module; builds the DOM from tokens and handles navigation.

· buildPageStructure(tokens) — parses the flat token list into a nested array of pages, tabs, and tokens.
· renderPages(pages) — creates page navigation buttons and page containers, calls renderTokens for each page/tab content. Resets callbackButtons and globalMathFormulas once per full rebuild.
· renderTokens(container, tokens) — walks through a token list and creates appropriate DOM elements (inputs, buttons, textareas, tables, etc.), respecting sections and rows via a container stack.
· showPage(pageName), showTab(pageName, tabName) — manage visibility classes and update location.hash.
· attachGlobalListeners() — now a no‑op because all input/button events are handled by delegation (see ensureGlobalDelegation).
· ensureGlobalDelegation() — attaches one delegated listener to the document for:
  · input/change on all input, select elements → triggers reactive math and state sync.
  · click on button[data-os-cmd] → opens gatekeeper modal.
  · click on button[data-callback] → fires a custom pybro:callback event that app.js listens for.

This delegation eliminates listener bloat and makes section toggles instant.

sse.js

Encapsulates the EventSource connection.

· startSSE({ onTokensUpdated, onStateUpdate, onCallbackOutput }) — connects to /stream, listens for open, tokens_updated, state_update, callback_output events, and calls the provided callbacks.
· On error, it closes the connection and retries after 3 seconds.

gatekeeper.js

Handles the OS command execution modal.

· openGatekeeper(cmd, desc, targetId) — shows the modal with command details.
· resolveGatekeeper(allowed) — hides modal; if allowed, sends a POST to /execute_os and updates the target terminal/text area.
· updateTarget(output, target_id) — safely updates a DOM element by id (textarea value or div innerText). Falls back to the first textarea / .terminal if no ID given.

poller.js

A fallback polling mechanism for when SSE isn’t enough.

· startPolling(onNewTokens, getCurrentTokens) — periodically fetches /tokens, compares the JSON snapshot to the current one, and calls onNewTokens if they differ.
· The interval is read from window.pybroPollInterval (set by the server).

app.js

The orchestrator. It imports all other modules and ties them together:

· Stores session key from URL params into sessionStorage.
· initRuntime() — fetches tokens, builds pages, renders them, sets up global delegation (once), restores form state, and handles access‑denied states.
· firePythonCallback(name) — looks up the button’s target_id from callbackButtons (set by renderer.js), sends a POST to /trigger_callback, and updates the target element if no UI patch was broadcast.
· Listens for the custom pybro:callback event to dispatch callbacks.
· Sets up gatekeeper approve/deny buttons.
· On window.onload:
  1. Calls ensureGlobalDelegation() to activate delegated listeners.
  2. Calls initRuntime() for the initial render.
  3. Starts SSE with callbacks that rebuild UI on token change, apply remote state, and handle callback output.
  4. Starts polling as a safety net.

---

How data flows end‑to‑end

1. User writes my_script.py with ui.xxx(...) calls.
2. Server starts, imports the script (using the stub pybro package), then parses it with PybroUIParser → builds a UINode tree.
3. Server loads the module (so callbacks are available), runs link_tree to resolve variable references.
4. Server starts HTTP server.
5. Browser loads index.html, which imports app.js and its dependencies.
6. app.js fetches /tokens → receives flattened token list.
7. renderer.js rebuilds the DOM from tokens, activating page/tab navigation and rendering all components.
8. User interacts → inputs fire delegated listeners, reactive math runs, form state syncs to server via /broadcast_state.
9. User clicks a callback button → app.js sends POST to /trigger_callback, server runs the Python function, applies patches, updates the tree, broadcasts via SSE → frontend rebuilds.
10. OS commands follow a similar flow through the gatekeeper modal.

---

Security considerations

· Shell injection: Fixed by using shlex.split() and shell=False.
· Command allowlist: Optional via [pybro] allowed_commands in pybro.toml.
· Session key: Passed via X-Pybro-Key header or ?key= URL parameter. Stored in sessionStorage on the client.
· Distributed mode: The token tree is HMAC‑signed, preventing tampering. Clients must provide the same key to verify.
· Callback output: Captured with redirect_stdout/stderr to avoid accidental server‑side prints.
· Thread safety: tree_lock prevents race conditions when the file‑watcher, SSE broadcaster, and request handlers mutate the UI tree simultaneously.

---

Configuring via pybro.toml

All settings can be overridden in a pybro.toml file placed in the project root.
The file uses standard TOML syntax. Every option is optional; omitted values fall back to the defaults listed below.

[pybro] section – Engine settings

Key Type Default Description
entrypoint string auto‑detect (main.py or first .py) Main Python script to run.
port integer 8080 HTTP server port.
shared boolean false Bind to all interfaces (0.0.0.0) instead of 127.0.0.1.
key string random hex Security key for shared mode.
connectable boolean false Allow remote clients to download the signed project tree (requires shared).
watch boolean false Watch the main script for changes and auto‑reload tokens.
ssl boolean false Enable HTTPS.
cert-file string – Path to TLS certificate (PEM). Required if ssl = true and no auto‑gen.
key-file string – Path to TLS private key (PEM). Required if ssl = true and no auto‑gen.
os-timeout integer 5 Timeout in seconds for OS commands.
custom-css string – Path to a CSS file loaded after built‑in styles.
poll-interval integer 2000 Polling fallback interval in milliseconds.
connect string – Remote master address for Mode 2 (e.g., 192.168.1.45:8080).
allow-deps boolean false In Mode 2, install dependencies from [distribute] into a temp venv.
keep-script boolean false In Mode 2, keep the downloaded codebase after exit.
verbose boolean false Enable Apache‑style HTTP request logs.
allowed_commands list of strings – (allow all) Restrict OS commands to this list (first word of command).

[distribute] section – Distribution / bundling

Used for Mode 2 and for building a shareable bundle.

Key Type Default Description
include list of paths (all .py files, excluding common dirs) Files or directories to include in the bundle.
requires list of strings [] Pip dependencies to install (e.g., "requests>=2.25").

Example pybro.toml:

```toml
[pybro]
port = 8080
shared = false
watch = true
custom-css = "style/custom.css"
allowed_commands = ["ping", "echo", "ls"]
poll-interval = 2000
os-timeout = 10

[distribute]
include = ["pages/", "utils.py"]
requires = ["requests"]
```

CLI flags (e.g., --port 9000) override any matching pybro.toml values.

---

This document covers every file and its role in Pybro’s architecture. The system is designed to be fully zero‑dependency, single‑binary friendly, yet flexible enough for LAN dashboards and distributed team automation.
