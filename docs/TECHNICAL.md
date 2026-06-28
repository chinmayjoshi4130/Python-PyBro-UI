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
│   │   ├── utils.py
│   │   └── pybro.toml
│   ├── pybro_demo/
│   │   ├── main.py
│   │   ├── scanner.py
│   │   ├── textarea_test.py
│   │   ├── pybro.toml
│   │   └── theme.css
│   └── section_demo.py
└── src/
└── pybro/
├── init.py           # No‑op stub so user scripts can import ui
├── state.py              # Shared globals, locks, and broadcast helper
├── tree.py               # UINode, flatten/find/build/link, bundling
├── parser.py             # PybroUIParser – AST → UI tree
├── handler.py            # EphemeralServer – HTTP, SSE, routes
├── watcher.py            # watch_script – file‑watcher thread
├── server.py             # main() – argument parsing & server startup
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
User scripts import from pybro import ui and then call ui.page_start(...), ui.input_text(...), etc. Without this stub, importing the script would fail because the ui module doesn’t really exist at runtime. The stub makes every call a harmless no‑op, so the user’s script can be imported into the server process without errors. The real UI parsing is done by parser.py’s AST visitor — it never uses this stub.

Important:
The stub must be in a package named pybro so that from pybro import ui resolves correctly. The server’s sys.path must include the project directory to find this package.

---

Backend modules (src/pybro/)

The backend is split into several files for maintainability. All modules share global state through state.py.

state.py – Shared globals and broadcast

Contains every piece of mutable state used across the engine:

· UI_ROOT – the root UINode of the UI tree
· TARGET_MODULE – the imported user module (for callbacks)
· SESSION_KEY – security key for shared mode
· PROJECT_TOKEN_TREE – signed bundle for distributed mode
· PROJECT_DIR, TEMP_DIR – filesystem paths
· tree_lock, state_lock, sse_lock – thread‑safety locks
· shared_form_state – form values synced across clients
· sse_clients – list of active SSE client queues
· broadcast_event() – sends an event to all SSE clients

Other modules access these variables via state.UI_ROOT, state.tree_lock, etc., never by importing them directly. This ensures that mutations are visible everywhere.

---

tree.py – Tree data model and operations

Defines the UINode class, which represents every UI element:

· type – token type string ("PAGE_START", "UI_INPUT", …)
· attrs – dict of properties (id, label, visible, …)
· children – list of child UINodes

Key functions:

· flatten_tree(root) – recursively walks the tree and produces the flat token list the frontend expects, automatically inserting end tokens for containers.
· find_node_by_id(root, target_id) – walks the tree to find the first node with a matching id attribute. Used by the patch engine and OS command output persistence.
· build_tree_from_flat(tokens) – reconstructs a UI_ROOT tree from a flat token list (used in Mode 2). Uses start/end token pairs to build the hierarchy.
· link_tree(node, module) – deferred symbol linker. After the user module is loaded, this replaces headers_ref / rows_ref with the actual values from the module.
· get_bundle_info() – collects files and dependencies from pybro.toml for distribution.
· build_token_tree() – creates the HMAC‑signed token tree for secure distribution in --connectable mode.

---

parser.py – AST parser (PybroUIParser)

Inherits from ast.NodeVisitor. This module never executes user code; it only extracts structure and constants.

· On encountering ui.xxx() calls, it evaluates arguments via ast.literal_eval when possible, or stores symbolic names (e.g., HEADERS, ROWS) for later linking.
· Builds the UI_ROOT tree directly using a stack of container nodes.
· Structural tokens (PAGE_START, SECTION_START, etc.) push/pop the stack; visual tokens become leaf nodes with UINode(type, **attrs).

---

handler.py – HTTP request handler (EphemeralServer)

Contains the entire HTTP and SSE logic.

GET endpoints:

Path Description
/tokens Returns the flattened token list (JSON), read under tree_lock.
/stream SSE event stream. Sends heartbeat, tokens_updated, state_update, callback_output.
/token-tree Signed project bundle for distributed mode (requires --connectable).
/custom.css Serves the optional custom CSS file.
/ or /index.html Serves the HTML shell, injecting the custom CSS link and poll‑interval script.
/static/... Serves front‑end JS/CSS files.

POST endpoints:

Path Description
/broadcast_state Receives form state from one client and broadcasts it to all others.
/execute_os Validates the command against gatekeeper tokens, splits with shlex, optionally checks an allowlist, runs with subprocess.run (no shell=True), and persists output in the target UI_TEXT_AREA.
/trigger_callback Calls the registered Python function (capturing stdout/stderr), applies any returned patches (by target_id or token_index), persists plain‑text output in the tree, and broadcasts updates.

Security hardening:

· OS commands use shlex.split() and shell=False – no shell injection.
· An optional allowed_commands list in pybro.toml restricts executable programs.
· Callback execution is wrapped with redirect_stdout / redirect_stderr to prevent accidental server‑side prints.

---

watcher.py – File watcher (watch_script)

When --watch is active, this function runs in a daemon thread:

· Monitors the script file’s modification time.
· On change: re‑parses the AST, reloads the module, links deferred symbols, atomically replaces state.UI_ROOT and state.TARGET_MODULE under tree_lock, then broadcasts a tokens_updated event.
· If --connectable is enabled, rebuilds the signed token tree.

---

server.py – Entry point (main())

Handles argument parsing, configuration (CLI + pybro.toml), and server startup.

Modes:

· Mode 0 (Localhost): pybro my_tool.py – binds to 127.0.0.1.
· Mode 1 (Shared): pybro my_tool.py --shared --key secret – binds to 0.0.0.0, requires authentication.
· Mode 2 (Distributed Client): pybro --connect <master_ip>:<port> --key secret – downloads the signed token tree, reconstructs the UI tree, extracts the codebase to a temp directory, and acts as a local mirror.

CSS auto‑detection in Mode 2:
After extracting the bundle, the client automatically searches for any .css file in the temp directory and serves it as the custom stylesheet. This ensures that the master’s visual theme is replicated without extra flags.

SSL setup (optional) – can use a provided certificate or generate a self‑signed one (Python ≥ 3.9).

The server instance (ThreadedTCPServer) is configured with all runtime options (os_timeout, poll_interval, allowed_commands, etc.) and starts EphemeralServer as the handler.

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
11. In distributed mode, the client automatically picks up any bundled .css file and serves it, mirroring the master’s look.

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
