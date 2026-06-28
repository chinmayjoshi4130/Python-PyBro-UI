import ast
import http.server
import json
import socketserver
import sys
import webbrowser
import importlib.util
import os
import secrets
import argparse
import urllib.request
import tempfile
import atexit
import subprocess
import threading
import ssl
import hashlib
import shutil
import hmac
import traceback
import html
import time
import uuid
import types
from queue import Queue

# --- tomllib / tomli fallback ---
try:
    import tomllib
except ImportError:
    import tomli as tomllib

# ---------- Tree data model ----------
class UINode:
    """A node in the UI tree. type is the token type, attrs are the token properties."""
    __slots__ = ('type', 'attrs', 'children')
    def __init__(self, type_, **attrs):
        self.type = type_
        self.attrs = attrs
        self.children = []

    def to_dict(self):
        """Convert back to the flat token dict format for the frontend."""
        d = {'type': self.type}
        d.update(self.attrs)
        return d

# ---------- Global state ----------
UI_ROOT = None          # the root node of the UI tree (type 'ROOT')
tree_lock = threading.Lock()

TARGET_MODULE = None
SESSION_KEY = None
TEMP_DIR = None
PROJECT_DIR = None

# The complete signed token tree (built only when --connectable is used)
PROJECT_TOKEN_TREE = None

# ---------- Shared form state (bi‑directional SSE) ----------
shared_form_state = {}
state_lock = threading.Lock()

# ---------- SSE real‑time broadcast ----------
sse_clients = []
sse_lock = threading.Lock()


def broadcast_event(event_type, data):
    """Push an event to all connected SSE clients. Non‑string data is JSON‑serialised."""
    if not isinstance(data, str):
        data = json.dumps(data, default=str)
    with sse_lock:
        dead = []
        for client_queue in sse_clients:
            try:
                client_queue.put((event_type, data))
            except Exception:
                dead.append(client_queue)
        for d in dead:
            sse_clients.remove(d)


# ---------- Auto‑bundle logic ----------
EXCLUDE_DIRS = {'.git', '__pycache__', 'venv', '.venv', 'env', 'node_modules', '.mypy_cache', '.pytest_cache'}


def collect_project_files(project_dir):
    files = []
    for root, dirs, filenames in os.walk(project_dir):
        dirs[:] = [d for d in dirs if d not in EXCLUDE_DIRS and not d.startswith('.')]
        for fname in filenames:
            if fname.endswith('.py'):
                full = os.path.join(root, fname)
                rel = os.path.relpath(full, project_dir)
                files.append(rel)
    return files


def get_bundle_info():
    """Return a dict with 'files' (list of relative paths), 'requires' (list of deps)."""
    if not PROJECT_DIR:
        return {'files': [], 'requires': []}
    requires = []
    include = None
    manifest_path = os.path.join(PROJECT_DIR, 'pybro.toml')
    if os.path.exists(manifest_path):
        try:
            with open(manifest_path, 'rb') as f:
                config = tomllib.load(f)
            distribute = config.get('distribute', {})
            include = distribute.get('include')
            requires = distribute.get('requires', [])
        except Exception:
            print(f"[!] Could not parse pybro.toml. Falling back to auto‑bundle.")
            traceback.print_exc()

    if include:
        files = []
        for pattern in include:
            full = os.path.join(PROJECT_DIR, pattern)
            if os.path.isfile(full):
                files.append(pattern)
            elif os.path.isdir(full):
                for root, _, fnames in os.walk(full):
                    for fn in fnames:
                        if fn.endswith('.py'):
                            rel = os.path.relpath(os.path.join(root, fn), PROJECT_DIR)
                            files.append(rel)
        return {'files': files, 'requires': requires}
    return {'files': collect_project_files(PROJECT_DIR), 'requires': requires}


def flatten_tree(node):
    """Recursively flatten the tree back into the token list expected by the frontend."""
    tokens = []
    stack = [node]
    while stack:
        current = stack.pop()
        if current.type == 'ROOT':
            # root is invisible, just visit children
            stack.extend(reversed(current.children))
            continue
        tokens.append(current.to_dict())
        if current.children:
            # structural nodes may have children that should appear after them
            if current.type in ('SECTION_START', 'LAYOUT_ROW_START', 'PAGE_START', 'TAB_START', 'TAB_GROUP_START'):
                # we need to push children first, then the end token after, but order is tricky.
                # Instead, we'll handle by traversing children then pushing end tokens.
                pass
    # The current flattening via simple recursion doesn't handle structural closure tokens.
    # Let's re-implement properly.
    tokens.clear()
    def walk(n):
        if n.type == 'ROOT':
            for child in n.children:
                walk(child)
            return
        tokens.append(n.to_dict())
        for child in n.children:
            walk(child)
        # If the node is a container that requires an end token, append one.
        end_map = {
            'SECTION_START': 'SECTION_END',
            'LAYOUT_ROW_START': 'LAYOUT_ROW_END',
            'PAGE_START': 'PAGE_END',
            'TAB_START': 'TAB_END',
            'TAB_GROUP_START': 'TAB_GROUP_END',
        }
        if n.type in end_map:
            tokens.append({'type': end_map[n.type]})
    walk(node)
    return tokens


def find_node_by_id(root, target_id):
    """Find the first node with attrs['id'] == target_id."""
    stack = [root]
    while stack:
        node = stack.pop()
        if node.attrs.get('id') == target_id:
            return node
        stack.extend(node.children)
    return None


def build_token_tree():
    """Build the complete signed token tree for the current project."""
    global PROJECT_TOKEN_TREE
    if not PROJECT_DIR or not SESSION_KEY:
        PROJECT_TOKEN_TREE = None
        return

    bundle_info = get_bundle_info()
    files_dict = {}
    for rel_path in bundle_info['files']:
        full_path = os.path.join(PROJECT_DIR, rel_path)
        with open(full_path, 'r', encoding='utf-8') as f:
            files_dict[rel_path] = f.read()

    with tree_lock:
        tokens_flat = flatten_tree(UI_ROOT)
    payload = {
        "ui_tokens": tokens_flat,
        "files": files_dict,
        "requires": bundle_info['requires']
    }
    payload_json = json.dumps(payload, sort_keys=True, separators=(',', ':')).encode('utf-8')
    sig = hmac.new(SESSION_KEY.encode('utf-8'), payload_json, hashlib.sha256).hexdigest()
    payload['signature'] = sig
    PROJECT_TOKEN_TREE = payload


# ---------- Deferred symbol linker ----------
def link_tree(node, module):
    """Walk the tree and replace unresolved symbol references with actual values."""
    if node.type == 'ROOT':
        for child in node.children:
            link_tree(child, module)
        return

    # Resolve table rows/headers from references
    if node.type == 'UI_TABLE':
        headers_ref = node.attrs.pop('headers_ref', None)
        rows_ref = node.attrs.pop('rows_ref', None)
        if headers_ref and module and hasattr(module, headers_ref):
            node.attrs['headers'] = getattr(module, headers_ref)
        if rows_ref and module and hasattr(module, rows_ref):
            node.attrs['rows'] = getattr(module, rows_ref)

    # Resolve math formulas? For now, formulas are strings, no change.
    # Resolve other possible refs...
    for child in node.children:
        link_tree(child, module)


# ---------- AST Parser (builds a tree, no execution) ----------
class PybroUIParser(ast.NodeVisitor):
    def __init__(self):
        self.root = UINode('ROOT')
        self.stack = [self.root]   # current container stack

    def _safe_literal(self, node):
        """Safely evaluate constant nodes only. Returns the value or an unresolved symbol name."""
        if isinstance(node, ast.Constant):
            return node.value
        if isinstance(node, ast.Name):
            # Return the identifier string for deferred resolution
            return node.id
        if isinstance(node, ast.Call):
            # For now, we do not resolve calls during parsing.
            return None
        try:
            return ast.literal_eval(node)
        except (ValueError, TypeError):
            return None

    def visit_Call(self, node):
        if isinstance(node.func, ast.Attribute) and isinstance(node.func.value, ast.Name):
            if node.func.value.id == 'ui':
                func_name = node.func.attr
                args = []
                for arg in node.args:
                    val = self._safe_literal(arg)
                    args.append(val)

                kwargs = {}
                for kw in node.keywords:
                    if kw.arg == 'css':
                        try:
                            kwargs['css'] = ast.literal_eval(kw.value)
                        except Exception:
                            kwargs['css'] = {}
                    elif kw.arg == 'class_':
                        try:
                            kwargs['class'] = ast.literal_eval(kw.value)
                        except Exception:
                            kwargs['class'] = ''
                    elif kw.arg == 'target_id':
                        try:
                            kwargs['target_id'] = ast.literal_eval(kw.value)
                        except Exception:
                            kwargs['target_id'] = None
                    elif kw.arg == 'visible':
                        try:
                            kwargs['visible'] = ast.literal_eval(kw.value)
                        except Exception:
                            kwargs['visible'] = True
                    else:
                        # unknown kwargs stored as literal if possible
                        try:
                            kwargs[kw.arg] = ast.literal_eval(kw.value)
                        except Exception:
                            kwargs[kw.arg] = None

                token_type = None
                attrs = {}

                # --- structural tokens ---
                if func_name == 'section_start' and args:
                    token_type = "SECTION_START"
                    attrs = {"id": args[0], "visible": kwargs.get("visible", True)}
                elif func_name == 'section_end':
                    token_type = "SECTION_END"
                elif func_name == 'page_start' and args:
                    token_type = "PAGE_START"
                    attrs = {"name": args[0]}
                elif func_name == 'page_end':
                    token_type = "PAGE_END"
                elif func_name == 'tab_group_start':
                    token_type = "TAB_GROUP_START"
                elif func_name == 'tab_start' and args:
                    token_type = "TAB_START"
                    attrs = {"name": args[0]}
                elif func_name == 'tab_end':
                    token_type = "TAB_END"
                elif func_name == 'tab_group_end':
                    token_type = "TAB_GROUP_END"

                # --- visual tokens ---
                elif func_name == 'title' and args:
                    token_type = "UI_TITLE"
                    attrs = {"text": args[0]}
                elif func_name == 'row_start':
                    token_type = "LAYOUT_ROW_START"
                elif func_name == 'row_end':
                    token_type = "LAYOUT_ROW_END"
                elif func_name == 'input_text' and len(args) >= 2:
                    token_type = "UI_INPUT"
                    attrs = {"id": args[0], "label": args[1]}
                elif func_name == 'checkbox' and len(args) >= 2:
                    token_type = "UI_CHECKBOX"
                    attrs = {"id": args[0], "label": args[1]}
                elif func_name == 'dropdown' and len(args) >= 3:
                    token_type = "UI_DROPDOWN"
                    attrs = {"id": args[0], "label": args[1], "options": args[2]}
                elif func_name == 'text_area' and len(args) >= 2:
                    token_type = "UI_TEXT_AREA"
                    attrs = {"id": args[0], "label": args[1], "value": ""}
                elif func_name == 'button_callback' and len(args) >= 2:
                    target = kwargs.get('target_id', None)
                    if target is None and len(args) >= 3:
                        target = args[2]   # positional target_id
                    token_type = "UI_CALLBACK_BUTTON"
                    attrs = {"text": args[0], "callback_name": args[1], "target_id": target}
                elif func_name == 'math_compute' and len(args) >= 2:
                    token_type = "UI_MATH_COMPUTE"
                    attrs = {"target_id": args[0], "formula": args[1]}
                elif func_name == 'os_command' and len(args) >= 3:
                    token_type = "OS_GATEKEEPER"
                    attrs = {"cmd": args[0], "desc": args[1], "target_id": args[2]}
                elif func_name == 'table' and len(args) >= 2:
                    token_type = "UI_TABLE"
                    # If args are not literals, store the identifier name for later resolution
                    if isinstance(args[0], str) and not args[0].isdigit():
                        attrs["headers_ref"] = args[0]
                    else:
                        attrs["headers"] = args[0]
                    if len(args) >= 2:
                        if isinstance(args[1], str) and not args[1].isdigit():
                            attrs["rows_ref"] = args[1]
                        else:
                            attrs["rows"] = args[1]
                    # target_id for table can be passed as kwarg or third positional
                    table_id = kwargs.get('target_id', None)
                    if table_id is None and len(args) >= 3:
                        table_id = args[2]
                    if table_id:
                        attrs["id"] = table_id
                elif func_name == 'root_css' and len(args) >= 1:
                    token_type = "UI_ROOT_CSS"
                    attrs = {"css_vars": args[0]}
                else:
                    token_type = None

                if token_type is not None:
                    # Create the node
                    if 'css' in kwargs:
                        attrs['css'] = kwargs['css']
                    if 'class' in kwargs:
                        attrs['class'] = kwargs['class']
                    new_node = UINode(token_type, **attrs)

                    # Structural nodes manage the stack
                    if token_type in ('SECTION_START', 'LAYOUT_ROW_START', 'PAGE_START', 'TAB_START', 'TAB_GROUP_START'):
                        self.stack[-1].children.append(new_node)
                        self.stack.append(new_node)
                    elif token_type in ('SECTION_END', 'LAYOUT_ROW_END', 'PAGE_END', 'TAB_END', 'TAB_GROUP_END'):
                        # pop the stack, but ensure the end token is matched to its start
                        if len(self.stack) > 1:
                            # We don't need to create an explicit end node; flatten_tree handles it.
                            self.stack.pop()
                    else:
                        # Leaf node
                        self.stack[-1].children.append(new_node)

        self.generic_visit(node)


# ---------- Ephemeral HTTP Server ----------
class EphemeralServer(http.server.SimpleHTTPRequestHandler):
    def log_message(self, format, *args):
        if getattr(self.server, 'verbose', False):
            super().log_message(format, *args)

    def is_authorized(self):
        if not SESSION_KEY:
            return True
        auth_header = self.headers.get('X-Pybro-Key')
        if auth_header == SESSION_KEY:
            return True
        if '?' in self.path:
            query = self.path.split('?', 1)[1]
            params = dict(qc.split('=', 1) for qc in query.split('&') if '=' in qc)
            if params.get('key') == SESSION_KEY:
                return True
        return False

    def do_GET(self):
        clean_path = self.path.split('?')[0]

        if clean_path == '/tokens':
            if not self.is_authorized():
                self.send_response(401); self.end_headers()
                self.wfile.write(b"Unauthorized: Missing or invalid security session key.")
                return
            # Flatten tree under lock, return copy
            with tree_lock:
                tokens_flat = flatten_tree(UI_ROOT) if UI_ROOT else []
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Cache-Control', 'no-store, no-cache, must-revalidate, max-age=0')
            self.send_header('Pragma', 'no-cache')
            self.send_header('Expires', '0')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            self.wfile.write(json.dumps(tokens_flat).encode())

        elif clean_path == '/stream':
            self.send_response(200)
            self.send_header('Content-Type', 'text/event-stream')
            self.send_header('Cache-Control', 'no-cache')
            self.send_header('Connection', 'keep-alive')
            self.end_headers()
            client_queue = Queue()
            with sse_lock:
                sse_clients.append(client_queue)
            with state_lock:
                current_state = json.dumps(dict(shared_form_state))
            client_queue.put(("state_update", current_state))

            def heartbeat():
                while True:
                    try:
                        client_queue.put(("heartbeat", ""), timeout=15)
                    except:
                        break
            heartbeat_thread = threading.Thread(target=heartbeat, daemon=True)
            heartbeat_thread.start()

            try:
                while True:
                    event_type, data = client_queue.get()
                    if event_type == "close":
                        break
                    if event_type == "heartbeat":
                        self.wfile.write(b": heartbeat\n\n")
                    else:
                        msg = f"event: {event_type}\ndata: {data}\n\n"
                        self.wfile.write(msg.encode())
                    self.wfile.flush()
            except (BrokenPipeError, ConnectionResetError):
                pass
            finally:
                with sse_lock:
                    if client_queue in sse_clients:
                        sse_clients.remove(client_queue)

        elif clean_path == '/token-tree':
            if not self.is_authorized():
                self.send_response(401); self.end_headers()
                self.wfile.write(b"Unauthorized")
                return
            if PROJECT_TOKEN_TREE is None:
                self.send_response(403)
                self.send_header('Content-Type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps({
                    "error": "Distributed connections are not enabled on this master. Use --connectable with --shared."
                }).encode())
                return
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps(PROJECT_TOKEN_TREE).encode())

        elif clean_path == '/custom.css':
            custom_css_path = getattr(self.server, 'custom_css_path', None)
            if custom_css_path and os.path.isfile(custom_css_path):
                self.send_response(200)
                self.send_header('Content-Type', 'text/css')
                self.end_headers()
                with open(custom_css_path, 'rb') as f:
                    self.wfile.write(f.read())
            else:
                self.send_error(404)

        elif clean_path in ('', '/', '/index.html'):
            self.send_response(200)
            self.send_header('Content-Type', 'text/html')
            self.end_headers()
            base_dir = os.path.dirname(os.path.abspath(__file__))
            html_path = os.path.join(base_dir, 'index.html')
            with open(html_path, 'rb') as f:
                html_bytes = f.read()

            # Custom CSS injection
            custom_css_path = getattr(self.server, 'custom_css_path', None)
            if custom_css_path and os.path.isfile(custom_css_path):
                html_str = html_bytes.decode('utf-8')
                link_tag = '<link rel="stylesheet" href="/custom.css">'
                html_str = html_str.replace('</head>', f'{link_tag}\n</head>')
                html_bytes = html_str.encode('utf-8')

            # Poll interval injection
            poll_interval = getattr(self.server, 'poll_interval', 2000)
            html_str = html_bytes.decode('utf-8')
            poll_script = f'<script>window.pybroPollInterval = {poll_interval};</script>'
            html_str = html_str.replace('</body>', f'{poll_script}\n</body>')
            html_bytes = html_str.encode('utf-8')

            self.wfile.write(html_bytes)
        # Serve static files (JS, CSS, etc.)
        elif clean_path.startswith('/static/'):
            base_dir = os.path.dirname(os.path.abspath(__file__))
            file_path = os.path.join(base_dir, clean_path.lstrip('/'))
            if os.path.isfile(file_path):
                self.send_response(200)
                if file_path.endswith('.js'):
                    self.send_header('Content-Type', 'application/javascript')
                elif file_path.endswith('.css'):
                    self.send_header('Content-Type', 'text/css')
                self.end_headers()
                with open(file_path, 'rb') as f:
                    self.wfile.write(f.read())
            else:
                self.send_error(404)
        else:
            self.send_error(404)

    def do_POST(self):
        if not self.is_authorized():
            self.send_response(401); self.end_headers()
            self.wfile.write(json.dumps({"output": "Unauthorized process rejection."}).encode())
            return

        content_length = int(self.headers['Content-Length'])
        try:
            post_data = json.loads(self.rfile.read(content_length).decode())
        except Exception:
            self.send_response(400)
            self.end_headers()
            self.wfile.write(b"Bad JSON")
            return

        if self.path == '/broadcast_state':
            with state_lock:
                shared_form_state.update(post_data.get('form_state', {}))
            broadcast_event("state_update", shared_form_state)
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps({"status": "ok"}).encode())

        elif self.path == '/execute_os':
            requested_cmd = post_data.get('cmd')
            target_id = post_data.get('target_id')

            # Validate command (we still check against tokens in the tree)
            with tree_lock:
                tokens_flat = flatten_tree(UI_ROOT)
            is_valid = any(t.get('cmd') == requested_cmd for t in tokens_flat if t['type'] == 'OS_GATEKEEPER')
            if not is_valid:
                resp = {"output": "Security Violation: Dynamic evaluation pipeline rejected.", "target_id": target_id}
                self.send_response(403)
                self.send_header('Content-Type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps(resp).encode())
                return

            timeout = getattr(self.server, 'os_timeout', 5)
            try:
                result = subprocess.run(requested_cmd, shell=True, capture_output=True, text=True, timeout=timeout)
                raw_output = result.stdout if result.stdout else result.stderr
                response_text = html.escape(raw_output).strip()
                if not response_text:
                    response_text = "(no output)"
            except subprocess.TimeoutExpired:
                response_text = html.escape(f"[!] Command timed out after {timeout} seconds.")
            except Exception as e:
                response_text = html.escape(f"Error: {str(e)}")

            # Persist output in the tree if target_id matches a text_area
            if target_id:
                with tree_lock:
                    node = find_node_by_id(UI_ROOT, target_id)
                    if node and node.type == 'UI_TEXT_AREA':
                        node.attrs['value'] = response_text
                    # broadcast updated tokens
                    flat = flatten_tree(UI_ROOT)
                broadcast_event("tokens_updated", json.dumps(flat))
            resp = {"output": response_text, "target_id": target_id}
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps(resp).encode())

        elif self.path == '/trigger_callback':
            func_name = post_data.get('callback_name')
            form_state = post_data.get('form_state', {})
            target_id = post_data.get('target_id')
            with tree_lock:
                tokens_flat = flatten_tree(UI_ROOT)
            is_registered = any(t.get('callback_name') == func_name for t in tokens_flat if t['type'] == 'UI_CALLBACK_BUTTON')

            if is_registered and TARGET_MODULE and hasattr(TARGET_MODULE, func_name):
                try:
                    target_function = getattr(TARGET_MODULE, func_name)
                    result = target_function(form_state)   # execute without lock

                    token_patches = None
                    if isinstance(result, list):
                        token_patches = result
                    elif isinstance(result, dict) and 'patches' in result:
                        token_patches = result['patches']

                    if token_patches:
                        # Apply patches under lock
                        with tree_lock:
                            for patch in token_patches:
                                action = patch.get('action')

                                # id‑based section toggle
                                if action == 'toggle_section':
                                    section_id = patch.get('section_id', '')
                                    visible = bool(patch.get('visible', True))
                                    node = find_node_by_id(UI_ROOT, section_id)
                                    if node and node.type == 'SECTION_START':
                                        node.attrs['visible'] = visible
                                    continue

                                # target_id or token_index? We'll support target_id
                                target_id_patch = patch.get('target_id')
                                if target_id_patch:
                                    node = find_node_by_id(UI_ROOT, target_id_patch)
                                else:
                                    # fallback to token_index (deprecated but kept for compatibility)
                                    idx = int(patch.get('token_index', -1))
                                    if idx >= 0:
                                        flat = flatten_tree(UI_ROOT)
                                        if idx < len(flat):
                                            node = find_node_by_id(UI_ROOT, flat[idx].get('id'))
                                        else:
                                            node = None
                                    else:
                                        node = None

                                if not node:
                                    continue

                                if action == 'set_text':
                                    if node.type == 'UI_TEXT_AREA':
                                        node.attrs['value'] = str(patch.get('value', ''))
                                    else:
                                        node.attrs['text'] = str(patch.get('value', ''))
                                elif action == 'set_label':
                                    node.attrs['label'] = str(patch.get('value', ''))
                                elif action == 'set_css':
                                    if isinstance(patch.get('value'), dict):
                                        node.attrs['css'] = patch['value']
                                elif action == 'set_class':
                                    node.attrs['class'] = str(patch.get('value', ''))
                                elif action == 'insert_table_row':
                                    if node.type == 'UI_TABLE':
                                        row = patch.get('row', [])
                                        node.attrs.setdefault('rows', []).append(row)
                                elif action == 'set_table_rows':
                                    if node.type == 'UI_TABLE':
                                        node.attrs['rows'] = patch.get('rows', [])
                                elif action == 'set_options':
                                    if node.type == 'UI_DROPDOWN':
                                        node.attrs['options'] = patch.get('options', [])

                            flat = flatten_tree(UI_ROOT)
                        broadcast_event("tokens_updated", json.dumps(flat))
                        response_text = "UI updated"
                    else:
                        response_text = str(result)

                except Exception as e:
                    response_text = f"Callback Error: {str(e)}"
                    traceback.print_exc()
            else:
                response_text = "Error: Function mapping constraint failure."

            # Persist plain‑text output in the tree if target_id is a text_area
            if target_id and not token_patches and response_text != "UI updated":
                with tree_lock:
                    node = find_node_by_id(UI_ROOT, target_id)
                    if node and node.type == 'UI_TEXT_AREA':
                        node.attrs['value'] = response_text
                    flat = flatten_tree(UI_ROOT)
                broadcast_event("tokens_updated", json.dumps(flat))

            resp = {
                "output": response_text.strip(),
                "target_id": target_id,
                "ui_patched": True if token_patches else False
            }
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps(resp).encode())
            if response_text != "UI updated":
                broadcast_event("callback_output", resp)


def watch_script(script_path, connectable=False):
    global UI_ROOT, TARGET_MODULE, PROJECT_TOKEN_TREE
    last_mtime = os.path.getmtime(script_path)
    while True:
        time.sleep(2)
        try:
            current_mtime = os.path.getmtime(script_path)
            if current_mtime != last_mtime:
                print("[*] Script change detected. Re‑compiling...")
                with open(script_path, "r") as f:
                    ast_tree = ast.parse(f.read())
                parser_obj = PybroUIParser()
                parser_obj.visit(ast_tree)
                new_root = parser_obj.root
                module_name = os.path.splitext(os.path.basename(script_path))[0]
                spec = importlib.util.spec_from_file_location(module_name, script_path)
                new_module = importlib.util.module_from_spec(spec)
                try:
                    spec.loader.exec_module(new_module)
                except Exception as e:
                    print(f"[!] Warning: could not reload module: {e}")
                # Link deferred symbols
                link_tree(new_root, new_module)
                # Atomically replace tree
                with tree_lock:
                    UI_ROOT = new_root
                    TARGET_MODULE = new_module
                    flat = flatten_tree(UI_ROOT)
                if PROJECT_DIR and SESSION_KEY and connectable:
                    build_token_tree()
                broadcast_event("tokens_updated", json.dumps(flat))
                print("[+] Re‑compile successful. UI refreshed.")
                last_mtime = current_mtime
        except FileNotFoundError:
            print("[!] Watched script disappeared.")
            break
        except Exception as e:
            print(f"[!] Error during re‑compile: {e}")
            traceback.print_exc()


def main():
    global UI_ROOT, TARGET_MODULE, SESSION_KEY, TEMP_DIR, PROJECT_DIR, PROJECT_TOKEN_TREE

    parser = argparse.ArgumentParser(description="Pybro Engine Runtime Framework")
    parser.add_argument("script", nargs="?", default=None, help="Target python automation script to compile")
    parser.add_argument("--shared", action="store_true", default=None, help="Shared Team Mode")
    parser.add_argument("--key", default=None, help="Custom security key string")
    parser.add_argument("--connect", default=None, help="Remote Client Mirror target (IP:port)")
    parser.add_argument("--connectable", action="store_true", default=None,
                        help="Allow remote clients to download signed token tree")
    parser.add_argument("--keep-script", action="store_true", default=None,
                        help="Keep downloaded temp codebase after exit")
    parser.add_argument("--port", type=int, default=None, help="Server port (default 8080)")
    parser.add_argument("--verbose", action="store_true", default=None, help="HTTP request logging")
    parser.add_argument("--ssl", action="store_true", default=None,
                        help="Serve over HTTPS (requires --cert-file/--key-file or auto‑generation)")
    parser.add_argument("--cert-file", default=None, help="TLS certificate file (PEM)")
    parser.add_argument("--key-file", default=None, help="TLS private key file (PEM)")
    parser.add_argument("--allow-deps", action="store_true", default=None,
                        help="Install dependencies from pybro.toml")
    parser.add_argument("--entrypoint", default=None, help="Main Python file in Mode 2")
    parser.add_argument("--os-timeout", type=int, default=None, help="Timeout for OS commands (default 5)")
    parser.add_argument("--watch", action="store_true", default=None,
                        help="Watch script for changes and auto‑reload tokens")
    parser.add_argument("--custom-css", default=None, help="Path to a CSS file to override default styles")
    args = parser.parse_args()

    # --- Determine project directory and read pybro.toml ---
    if args.script and args.script != '.':
        script_path_arg = os.path.abspath(args.script)
        PROJECT_DIR = os.path.dirname(script_path_arg)
    else:
        PROJECT_DIR = os.getcwd()

    config = {}
    toml_path = os.path.join(PROJECT_DIR, 'pybro.toml')
    if os.path.isfile(toml_path):
        try:
            with open(toml_path, 'rb') as f:
                raw = tomllib.load(f)
            config = raw.get('pybro', {})
            for path_key in ('custom-css', 'cert-file', 'key-file', 'entrypoint'):
                if path_key in config and not os.path.isabs(config[path_key]):
                    config[path_key] = os.path.join(PROJECT_DIR, config[path_key])
        except Exception:
            print("[!] Could not parse pybro.toml, ignoring.")

    def get_value(key, cli_value, default, coerce=lambda x: x):
        if cli_value is not None:
            return cli_value
        if key in config:
            return coerce(config[key])
        return default

    shared = get_value('shared', args.shared, False, bool)
    watch = get_value('watch', args.watch, False, bool)
    connectable = get_value('connectable', args.connectable, False, bool)
    ssl_enabled = get_value('ssl', args.ssl, False, bool)
    allow_deps = get_value('allow-deps', args.allow_deps, False, bool)
    keep_script = get_value('keep-script', args.keep_script, False, bool)
    verbose = get_value('verbose', args.verbose, False, bool)
    key = get_value('key', args.key, None)
    port = get_value('port', args.port, 8080, int)
    os_timeout = get_value('os-timeout', args.os_timeout, 5, int)
    custom_css = get_value('custom-css', args.custom_css, None)
    cert_file = get_value('cert-file', args.cert_file, None)
    key_file = get_value('key-file', args.key_file, None)
    entrypoint = get_value('entrypoint', args.entrypoint, None)
    connect_target = get_value('connect', args.connect, None)
    poll_interval = get_value('poll-interval', None, 2000, int)

    if custom_css and not os.path.isfile(custom_css):
        print(f"[!] Custom CSS file not found: {custom_css}")
        sys.exit(1)

    if args.script and args.script != '.':
        script_path = script_path_arg
    elif entrypoint:
        script_path = os.path.join(PROJECT_DIR, entrypoint)
        if not os.path.isfile(script_path):
            print(f"[!] Entry point '{entrypoint}' not found.")
            sys.exit(1)
    elif connect_target is None:
        py_files = [f for f in os.listdir(PROJECT_DIR) if f.endswith('.py')]
        main_candidate = next((f for f in py_files if f == 'main.py'), py_files[0] if py_files else None)
        if not main_candidate:
            print("[!] No Python files found in project directory.")
            sys.exit(1)
        script_path = os.path.join(PROJECT_DIR, main_candidate)
    else:
        script_path = None
        
    # --- MODE 2: Distributed Sandbox Client ---
    if connect_target:
        if not connect_target.startswith("http"):
            connect_target = f"http://{connect_target}"
        print(f"[*] Mode 2: Launching distributed sandbox link to pipeline: {connect_target}")
    
        headers = {}
        if key:
            headers["X-Pybro-Key"] = key
        elif "key=" in connect_target:
            try:
                extracted_key = connect_target.split("key=")[1].split("&")[0]
                headers["X-Pybro-Key"] = extracted_key
                key = extracted_key
            except Exception:
                pass
    
        # Fetch flat token list (only needed for compatibility check)
        try:
            req = urllib.request.Request(f"{connect_target.split('?')[0].rstrip('/')}/tokens", headers=headers)
            with urllib.request.urlopen(req, timeout=5) as response:
                flat_tokens = json.loads(response.read().decode())
            print(f"[+] Synced {len(flat_tokens)} remote blueprints.")
        except Exception as e:
            print(f"[-] Failed to fetch tokens: {e}")
            traceback.print_exc()
            sys.exit(1)
    
        # Fetch full token tree (code + UI tokens)
        try:
            req = urllib.request.Request(f"{connect_target.split('?')[0].rstrip('/')}/token-tree", headers=headers)
            with urllib.request.urlopen(req, timeout=10) as response:
                if response.status == 403:
                    print("[-] Master does not allow distributed connections (--connectable is disabled on the server).")
                    sys.exit(1)
                token_tree = json.loads(response.read().decode())
                signature = token_tree.pop('signature', None)
                if signature:
                    if not key:
                        print("[-] The master requires a shared key. Please provide the --key argument.")
                        sys.exit(1)
                    payload_json = json.dumps(token_tree, sort_keys=True, separators=(',', ':')).encode('utf-8')
                    expected_sig = hmac.new(key.encode('utf-8'), payload_json, hashlib.sha256).hexdigest()
                    if not hmac.compare_digest(expected_sig, signature):
                        raise ValueError("Invalid signature – possible tampering or wrong key")
                    print("[+] Token tree signature verified.")
                else:
                    print("[*] No signature present – proceeding without verification.")
                ui_tokens = token_tree['ui_tokens']
                files = token_tree['files']
                requires = token_tree.get('requires', [])
        except urllib.error.HTTPError as e:
            if e.code == 403:
                print("[-] Master does not allow distributed connections (--connectable is disabled on the server).")
                sys.exit(1)
            else:
                print(f"[-] Failed to fetch token tree: {e}")
                traceback.print_exc()
                sys.exit(1)
        except Exception as e:
            print(f"[-] Failed to fetch or verify token tree: {e}")
            traceback.print_exc()
            sys.exit(1)
    
        # Reconstruct a UI tree from the flat tokens
        def build_tree_from_flat(tokens):
            root = UINode('ROOT')
            stack = [root]
            end_map = {
                'SECTION_END': 'SECTION_START',
                'LAYOUT_ROW_END': 'LAYOUT_ROW_START',
                'PAGE_END': 'PAGE_START',
                'TAB_END': 'TAB_START',
                'TAB_GROUP_END': 'TAB_GROUP_START',
            }
            for tok in tokens:
                ttype = tok['type']
                attrs = {k: v for k, v in tok.items() if k != 'type'}
                if ttype in ('SECTION_START', 'LAYOUT_ROW_START', 'PAGE_START', 'TAB_START', 'TAB_GROUP_START'):
                    node = UINode(ttype, **attrs)
                    stack[-1].children.append(node)
                    stack.append(node)
                elif ttype in ('SECTION_END', 'LAYOUT_ROW_END', 'PAGE_END', 'TAB_END', 'TAB_GROUP_END'):
                    expected_type = end_map[ttype]
                    if stack[-1].type == expected_type:
                        stack.pop()
                    else:
                        # mismatch, but we can still pop if we find it
                        # For simplicity we assume well‑formed tokens
                        pass
                else:
                    node = UINode(ttype, **attrs)
                    stack[-1].children.append(node)
            return root
    
        with tree_lock:
            UI_ROOT = build_tree_from_flat(ui_tokens)
    
        # Extract the codebase to temp directory
        TEMP_DIR = tempfile.mkdtemp(prefix='pybro_')
        for rel_path, content in files.items():
            dest_path = os.path.join(TEMP_DIR, rel_path)
            os.makedirs(os.path.dirname(dest_path), exist_ok=True)
            with open(dest_path, 'w', encoding='utf-8') as f:
                f.write(content)
        print(f"[+] Codebase extracted to {TEMP_DIR}")
    
        if TEMP_DIR not in sys.path:
            sys.path.insert(0, TEMP_DIR)
    
        # Install dependencies if needed
        if requires and allow_deps:
            # (dependency installation unchanged – keep the previous code)
            print("[*] Installing external dependencies...")
            venv_dir = os.path.join(TEMP_DIR, '.venv')
            try:
                subprocess.run([sys.executable, '-m', 'venv', venv_dir], check=True, capture_output=True)
            except subprocess.CalledProcessError as e:
                print(f"[!] Failed to create virtual environment: {e.stderr.decode()}")
                sys.exit(1)
    
            pip_path = os.path.join(venv_dir, 'Scripts' if os.name == 'nt' else 'bin', 'pip')
            py_path = os.path.join(venv_dir, 'Scripts' if os.name == 'nt' else 'bin', 'python')
            env = os.environ.copy()
            env['PIP_CACHE_DIR'] = os.path.join(TEMP_DIR, 'pip_cache')
    
            for dep in requires:
                print(f"  - Installing {dep}")
                try:
                    subprocess.run([pip_path, 'install', dep], check=True, capture_output=True, text=True, env=env)
                except subprocess.CalledProcessError as e:
                    print(f"[!] Failed to install {dep}: {e.stderr}")
            # Add venv to path
            try:
                result = subprocess.run([py_path, '-c', "import site; print(';'.join(site.getsitepackages()))"],
                                        capture_output=True, text=True, env=env)
                if result.returncode == 0:
                    for sp in result.stdout.strip().split(';'):
                        if sp not in sys.path:
                            sys.path.append(sp)
            except Exception:
                lib_path = os.path.join(venv_dir, 'Lib' if os.name == 'nt' else 'lib',
                                        f'python{sys.version_info.major}.{sys.version_info.minor}', 'site-packages')
                if os.path.isdir(lib_path) and lib_path not in sys.path:
                    sys.path.append(lib_path)
            print("[+] Dependencies installed.")
    
        # Locate and import the main module
        if entrypoint:
            main_script = entrypoint
        else:
            candidates = [f for f in os.listdir(TEMP_DIR) if f.endswith('.py')]
            main_script = next((f for f in candidates if f == 'main.py'), candidates[0] if candidates else None)
            if not main_script:
                print("[!] No Python files found in the downloaded bundle.")
                sys.exit(1)
    
        module_name = os.path.splitext(main_script)[0]
        spec = importlib.util.spec_from_file_location(module_name, os.path.join(TEMP_DIR, main_script))
        TARGET_MODULE = importlib.util.module_from_spec(spec)
        try:
            spec.loader.exec_module(TARGET_MODULE)
            print(f"[+] Loaded module '{module_name}' from codebase.")
        except Exception as e:
            print(f"[!] Warning: could not execute module: {e}")
            traceback.print_exc()
    
        bind_ip = "127.0.0.1"
        
    else:
        # --- DEFAULT MODE & MODE 1 (Master) ---
        if not script_path:
            parser.print_help()
            sys.exit(1)

        if PROJECT_DIR not in sys.path:
            sys.path.insert(0, PROJECT_DIR)

        # Parse the script and build the tree
        with open(script_path, "r") as f:
            ast_tree = ast.parse(f.read())
        parser_obj = PybroUIParser()
        parser_obj.visit(ast_tree)
        UI_ROOT = parser_obj.root

        # Load the module (callbacks only, no execution during parsing)
        module_name = os.path.splitext(os.path.basename(script_path))[0]
        spec = importlib.util.spec_from_file_location(module_name, script_path)
        TARGET_MODULE = importlib.util.module_from_spec(spec)
        try:
            spec.loader.exec_module(TARGET_MODULE)
        except Exception as e:
            print(f"[!] Target callback module linking unavailable: {e}")
            traceback.print_exc()

        # Now resolve all deferred symbol references
        link_tree(UI_ROOT, TARGET_MODULE)

        # Setup network
        if shared:
            bind_ip = "0.0.0.0"
            SESSION_KEY = key if key else secrets.token_hex(4)
        else:
            bind_ip = "127.0.0.1"

        if connectable:
            if not shared:
                print("[!] --connectable requires --shared (shared mode). Exiting.")
                sys.exit(1)
            if SESSION_KEY:
                build_token_tree()
                print("[*] Project token tree signed and ready for distribution.")
            else:
                print("[!] --connectable requires a shared key. Use --shared --key <secret>.")
                sys.exit(1)

    # --- Cleanup of temporary dir ---
    if TEMP_DIR and not keep_script:
        def cleanup_temp_dir():
            if os.path.exists(TEMP_DIR):
                shutil.rmtree(TEMP_DIR)
                print(f"[-] Temporary codebase {TEMP_DIR} deleted.")
        atexit.register(cleanup_temp_dir)

    # --- SSL setup (unchanged) ---
    ssl_context = None
    cert_file_temp = None
    key_file_temp = None
    if ssl_enabled:
        # ... same as before ...
        pass

    class ThreadedTCPServer(socketserver.ThreadingMixIn, socketserver.TCPServer):
        allow_reuse_address = True
        daemon_threads = True

    try:
        with ThreadedTCPServer((bind_ip, port), EphemeralServer) as httpd:
            httpd.verbose = verbose
            httpd.os_timeout = os_timeout
            httpd.poll_interval = poll_interval
            if custom_css:
                httpd.custom_css_path = os.path.abspath(custom_css)

            if ssl_context:
                httpd.socket = ssl_context.wrap_socket(httpd.socket, server_side=True)

            protocol = "https" if ssl_context else "http"
            print(f"\n=======================================================")
            print(f"[*] PYBRO ENGINE SYSTEM UPGRADE ACTIVE")
            print(f"[*] Bound Interface Location: {protocol}://{bind_ip}:{port}")

            if SESSION_KEY:
                print(f"[⚠️] SECURITY ENFORCED: Shared Key Mode active.")
                if connectable:
                    print(f"[⚠️] Distributed connections ENABLED (--connectable)")
                else:
                    print(f"[⚠️] Distributed connections DISABLED (no --connectable)")
                print(f"[⚠️] TARGET DEVICE PASS-LINK:")
                print(f"    {protocol}://<your_server_ip>:{port}/?key={SESSION_KEY}")
                print(f"=======================================================\n")
            else:
                print(f"[*] Security Layer: Local Sandbox Mode (No Key Required)")
                print(f"=======================================================\n")
                if not connect_target:
                    webbrowser.open(f"{protocol}://localhost:{port}")

            if watch and not connect_target:
                print("[*] Starting file watcher on", script_path)
                threading.Thread(target=watch_script, args=(script_path, connectable), daemon=True).start()

            httpd.serve_forever()
    except KeyboardInterrupt:
        print("\n[-] Clean volatile memory purge done.")
    except OSError as e:
        print(f"[!] Could not start server: {e}")
        sys.exit(1)
    finally:
        if cert_file_temp:
            os.unlink(cert_file_temp.name)
        if key_file_temp:
            os.unlink(key_file_temp.name)


if __name__ == "__main__":
    main()