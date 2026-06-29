# handler.py
import http.server
import json
import os
import subprocess
import threading
import traceback
import html
import shlex
import io
from queue import Queue
from contextlib import redirect_stdout, redirect_stderr

from . import state
from .state import logger
from .tree import flatten_tree, find_node_by_id


class EphemeralServer(http.server.SimpleHTTPRequestHandler):
    def log_message(self, format, *args):
        """Override to route HTTP request logs through the Pybro logger."""
        if getattr(self.server, 'verbose', False):
            logger.info(format % args)

    # -----------------------------------------------------------------
    # Authentication
    # -----------------------------------------------------------------
    def is_authorized(self):
        if not state.SESSION_KEY:
            return True
        auth_header = self.headers.get('X-Pybro-Key')
        if auth_header == state.SESSION_KEY:
            return True
        if '?' in self.path:
            query = self.path.split('?', 1)[1]
            params = dict(qc.split('=', 1) for qc in query.split('&') if '=' in qc)
            if params.get('key') == state.SESSION_KEY:
                return True
        # Single, context‑rich log for all unauthorized attempts
        logger.warn(f"Unauthorized access to {self.path} from {self.client_address[0]}")
        return False

    # -----------------------------------------------------------------
    # GET handlers
    # -----------------------------------------------------------------
    def do_GET(self):
        clean_path = self.path.split('?')[0]

        # ---- /tokens ----
        if clean_path == '/tokens':
            if not self.is_authorized():
                self.send_response(401); self.end_headers()
                self.wfile.write(b"Unauthorized: Missing or invalid security session key.")
                return
            with state.tree_lock:
                tokens_flat = flatten_tree(state.UI_ROOT) if state.UI_ROOT else []
            logger.debug(f"Serving {len(tokens_flat)} tokens to {self.client_address[0]}")
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Cache-Control', 'no-store, no-cache, must-revalidate, max-age=0')
            self.send_header('Pragma', 'no-cache')
            self.send_header('Expires', '0')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            self.wfile.write(json.dumps(tokens_flat).encode())

        # ---- /stream (SSE) ----
        elif clean_path == '/stream':
            self.send_response(200)
            self.send_header('Content-Type', 'text/event-stream')
            self.send_header('Cache-Control', 'no-cache')
            self.send_header('Connection', 'keep-alive')
            self.end_headers()
            client_queue = Queue()
            with state.sse_lock:
                state.sse_clients.append(client_queue)
            logger.info(f"SSE client connected from {self.client_address[0]}, total clients: {len(state.sse_clients)}")
            with state.state_lock:
                current_state = json.dumps(dict(state.shared_form_state))
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
                logger.debug(f"SSE client {self.client_address[0]} disconnected (broken pipe)")
            finally:
                with state.sse_lock:
                    if client_queue in state.sse_clients:
                        state.sse_clients.remove(client_queue)
                logger.debug(f"SSE client {self.client_address[0]} removed, remaining: {len(state.sse_clients)}")

        # ---- /token-tree ----
        elif clean_path == '/token-tree':
            if not self.is_authorized():
                self.send_response(401); self.end_headers()
                self.wfile.write(b"Unauthorized")
                return
            if state.PROJECT_TOKEN_TREE is None:
                self.send_response(403)
                self.send_header('Content-Type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps({
                    "error": "Distributed connections are not enabled on this master. Use --connectable with --shared."
                }).encode())
                logger.warn(f"Token tree requested but not available from {self.client_address[0]}")
                return
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps(state.PROJECT_TOKEN_TREE).encode())
            logger.debug(f"Served token tree to {self.client_address[0]}")

        # ---- /custom.css ----
        elif clean_path == '/custom.css':
            custom_css_path = getattr(self.server, 'custom_css_path', None)
            if custom_css_path and os.path.isfile(custom_css_path):
                self.send_response(200)
                self.send_header('Content-Type', 'text/css')
                self.end_headers()
                with open(custom_css_path, 'rb') as f:
                    self.wfile.write(f.read())
                logger.debug(f"Served custom CSS: {custom_css_path}")
            else:
                logger.debug("Custom CSS not found")
                self.send_error(404)

        # ---- / (index.html) ----
        elif clean_path in ('', '/', '/index.html'):
            self.send_response(200)
            self.send_header('Content-Type', 'text/html')
            self.end_headers()
            base_dir = os.path.dirname(os.path.abspath(__file__))
            html_path = os.path.join(base_dir, 'index.html')
            with open(html_path, 'rb') as f:
                html_bytes = f.read()

            custom_css_path = getattr(self.server, 'custom_css_path', None)
            if custom_css_path and os.path.isfile(custom_css_path):
                html_str = html_bytes.decode('utf-8')
                link_tag = '<link rel="stylesheet" href="/custom.css">'
                html_str = html_str.replace('</head>', f'{link_tag}\n</head>')
                html_bytes = html_str.encode('utf-8')

            poll_interval = getattr(self.server, 'poll_interval', 2000)
            html_str = html_bytes.decode('utf-8')
            poll_script = f'<script>window.pybroPollInterval = {poll_interval};</script>'
            html_str = html_str.replace('</body>', f'{poll_script}\n</body>')
            html_bytes = html_str.encode('utf-8')
            self.wfile.write(html_bytes)
            logger.debug(f"Served index.html to {self.client_address[0]}")

        # ---- /static/... ----
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
                logger.debug(f"Served static file: {file_path}")
            else:
                logger.debug(f"Static file not found: {file_path}")
                self.send_error(404)
        else:
            logger.debug(f"Unknown path: {clean_path} from {self.client_address[0]}")
            self.send_error(404)

    # -----------------------------------------------------------------
    # POST handlers
    # -----------------------------------------------------------------
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
            logger.debug(f"Bad JSON in POST body from {self.client_address[0]}")
            return

        # ---- /broadcast_state ----
        if self.path == '/broadcast_state':
            with state.state_lock:
                state.shared_form_state.update(post_data.get('form_state', {}))
            state.broadcast_event("state_update", state.shared_form_state)
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps({"status": "ok"}).encode())
            logger.debug(f"Form state broadcasted from {self.client_address[0]}")

        # ---- /execute_os ----
        elif self.path == '/execute_os':
            requested_cmd = post_data.get('cmd')
            target_id = post_data.get('target_id')
            logger.info(f"OS execution requested by {self.client_address[0]}: '{requested_cmd}' -> target_id={target_id}")

            with state.tree_lock:
                tokens_flat = flatten_tree(state.UI_ROOT)
            is_valid = any(t.get('cmd') == requested_cmd for t in tokens_flat if t['type'] == 'OS_GATEKEEPER')
            if not is_valid:
                resp = {"output": "Security Violation: Dynamic evaluation pipeline rejected.", "target_id": target_id}
                self.send_response(403)
                self.send_header('Content-Type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps(resp).encode())
                logger.warn(f"Command rejected: '{requested_cmd}' not in gatekeeper tokens (from {self.client_address[0]})")
                return

            timeout = getattr(self.server, 'os_timeout', 5)
            try:
                cmd_list = shlex.split(requested_cmd)
                allowed_commands = getattr(self.server, 'allowed_commands', None)
                if allowed_commands is not None and cmd_list and cmd_list[0] not in allowed_commands:
                    resp = {"output": f"Command '{cmd_list[0]}' is not allowed.", "target_id": target_id}
                    self.send_response(403)
                    self.send_header('Content-Type', 'application/json')
                    self.end_headers()
                    self.wfile.write(json.dumps(resp).encode())
                    logger.warn(f"Command rejected by allowlist: '{cmd_list[0]}' (from {self.client_address[0]})")
                    return
                result = subprocess.run(cmd_list, capture_output=True, text=True, timeout=timeout)
                raw_output = result.stdout if result.stdout else result.stderr
                response_text = html.escape(raw_output).strip()
                if not response_text:
                    response_text = "(no output)"
                logger.debug(f"Command finished, output length: {len(response_text)}")
            except subprocess.TimeoutExpired:
                response_text = html.escape(f"[!] Command timed out after {timeout} seconds.")
                logger.warn(f"Command timed out: '{requested_cmd}' (from {self.client_address[0]})")
            except Exception as e:
                response_text = html.escape(f"Error: {str(e)}")
                logger.error(f"Command execution error: {e} (from {self.client_address[0]})")
                logger.debug(traceback.format_exc())

            if target_id:
                with state.tree_lock:
                    node = find_node_by_id(state.UI_ROOT, target_id)
                    if node and node.type == 'UI_TEXT_AREA':
                        node.attrs['value'] = response_text
                    flat = flatten_tree(state.UI_ROOT)
                state.broadcast_event("tokens_updated", json.dumps(flat))
                logger.debug(f"OS output persisted to target_id={target_id}")

            resp = {"output": response_text, "target_id": target_id}
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps(resp).encode())

        # ---- /trigger_callback ----
        elif self.path == '/trigger_callback':
            func_name = post_data.get('callback_name')
            form_state = post_data.get('form_state', {})
            target_id = post_data.get('target_id')
            logger.info(f"Callback '{func_name}' triggered by {self.client_address[0]}, target_id={target_id}")

            with state.tree_lock:
                tokens_flat = flatten_tree(state.UI_ROOT)
            is_registered = any(t.get('callback_name') == func_name for t in tokens_flat if t['type'] == 'UI_CALLBACK_BUTTON')

            if not is_registered:
                resp = {
                    "output": f"Error: Callback '{func_name}' is not registered by any UI button.",
                    "target_id": target_id,
                    "ui_patched": False
                }
                self.send_response(200)
                self.send_header('Content-Type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps(resp).encode())
                logger.warn(f"Callback not registered: {func_name} (from {self.client_address[0]})")
                return

            if not state.TARGET_MODULE or not hasattr(state.TARGET_MODULE, func_name):
                resp = {
                    "output": f"Error: Python function '{func_name}' not found in the loaded module.",
                    "target_id": target_id,
                    "ui_patched": False
                }
                self.send_response(200)
                self.send_header('Content-Type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps(resp).encode())
                logger.warn(f"Callback function not found: {func_name} (from {self.client_address[0]})")
                return

            try:
                target_function = getattr(state.TARGET_MODULE, func_name)
                with io.StringIO() as buf, redirect_stdout(buf), redirect_stderr(buf):
                    result = target_function(form_state)
                logger.debug(f"Callback '{func_name}' returned type: {type(result).__name__}")

                token_patches = None
                if isinstance(result, list):
                    token_patches = result
                elif isinstance(result, dict) and 'patches' in result:
                    token_patches = result['patches']

                if token_patches:
                    with state.tree_lock:
                        for patch in token_patches:
                            action = patch.get('action')
                            if action == 'toggle_section':
                                section_id = patch.get('section_id', '')
                                visible = bool(patch.get('visible', True))
                                node = find_node_by_id(state.UI_ROOT, section_id)
                                if node and node.type == 'SECTION_START':
                                    node.attrs['visible'] = visible
                                    logger.debug(f"Toggled section '{section_id}' to visible={visible}")
                                else:
                                    logger.warn(f"Section not found for toggle: '{section_id}'")
                                continue
                            target_id_patch = patch.get('target_id')
                            if target_id_patch:
                                node = find_node_by_id(state.UI_ROOT, target_id_patch)
                            else:
                                node = None
                            if not node:
                                logger.warn(f"Patch target not found: {patch}")
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
                            elif action == 'set_progress':
                                if node.type == 'UI_PROGRESS':
                                    node.attrs['value'] = int(patch.get('value', 0))
                            logger.debug(f"Applied patch: {action} on node id={node.attrs.get('id', '?')}")
                        flat = flatten_tree(state.UI_ROOT)
                    state.broadcast_event("tokens_updated", json.dumps(flat))
                    response_text = "UI updated"
                else:
                    response_text = str(result)

            except Exception as e:
                response_text = f"Callback Error: {str(e)}"
                logger.error(f"Callback '{func_name}' failed: {e} (from {self.client_address[0]})")
                logger.debug(traceback.format_exc())

            # Persist plain‑text output in token tree
            if target_id and not token_patches and response_text != "UI updated":
                with state.tree_lock:
                    node = find_node_by_id(state.UI_ROOT, target_id)
                    if node and node.type == 'UI_TEXT_AREA':
                        node.attrs['value'] = response_text
                    flat = flatten_tree(state.UI_ROOT)
                state.broadcast_event("tokens_updated", json.dumps(flat))
                logger.debug(f"Plain callback output persisted to target_id={target_id}")

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
                state.broadcast_event("callback_output", resp)