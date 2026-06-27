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

COMPILED_TOKENS = []
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
            import tomllib
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

    # Build payload (without signature)
    payload = {
        "ui_tokens": COMPILED_TOKENS,
        "files": files_dict,
        "requires": bundle_info['requires']
    }
    # Canonical JSON for signing
    payload_json = json.dumps(payload, sort_keys=True, separators=(',', ':')).encode('utf-8')
    # HMAC-SHA256 with the session key
    sig = hmac.new(SESSION_KEY.encode('utf-8'), payload_json, hashlib.sha256).hexdigest()
    payload['signature'] = sig
    PROJECT_TOKEN_TREE = payload


# ---------- AST Parser ----------
class PybroUIParser(ast.NodeVisitor):
    """Walk the user script and extract UI tokens into COMPILED_TOKENS."""
    def __init__(self):
        self.var_table = {}

    def visit_Module(self, node):
        for stmt in node.body:
            if isinstance(stmt, ast.Assign) and len(stmt.targets) == 1:
                target = stmt.targets[0]
                if isinstance(target, ast.Name):
                    try:
                        self.var_table[target.id] = ast.literal_eval(stmt.value)
                    except ValueError:
                        pass
        self.generic_visit(node)

    def visit_Call(self, node):
        if isinstance(node.func, ast.Attribute) and isinstance(node.func.value, ast.Name):
            if node.func.value.id == 'ui':
                func_name = node.func.attr
                args = []
                for arg in node.args:
                    try:
                        args.append(ast.literal_eval(arg))
                    except ValueError:
                        if isinstance(arg, ast.Name):
                            if arg.id in self.var_table:
                                args.append(self.var_table[arg.id])
                            else:
                                args.append(arg.id)
                        else:
                            args.append(None)
    
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
    
                token = None
                if func_name == 'title' and args:
                    token = {"type": "UI_TITLE", "text": args[0]}
                elif func_name == 'row_start':
                    token = {"type": "LAYOUT_ROW_START"}
                elif func_name == 'row_end':
                    token = {"type": "LAYOUT_ROW_END"}
                elif func_name == 'input_text' and len(args) >= 2:
                    token = {"type": "UI_INPUT", "id": args[0], "label": args[1]}
                elif func_name == 'checkbox' and len(args) >= 2:
                    token = {"type": "UI_CHECKBOX", "id": args[0], "label": args[1]}
                elif func_name == 'dropdown' and len(args) >= 3:
                    token = {"type": "UI_DROPDOWN", "id": args[0], "label": args[1], "options": args[2]}
                elif func_name == 'text_area' and len(args) >= 2:
                    token = {"type": "UI_TEXT_AREA", "id": args[0], "label": args[1]}
                elif func_name == 'button_callback' and len(args) >= 2:
                    # Prefer keyword target_id, then positional third argument
                    target = kwargs.get('target_id', None)
                    if target is None and len(args) >= 3:
                        target = args[2]
                    token = {"type": "UI_CALLBACK_BUTTON", "text": args[0], "callback_name": args[1], "target_id": target}
                elif func_name == 'math_compute' and len(args) >= 2:
                    token = {"type": "UI_MATH_COMPUTE", "target_id": args[0], "formula": args[1]}
                elif func_name == 'os_command' and len(args) >= 3:
                    token = {"type": "OS_GATEKEEPER", "cmd": args[0], "desc": args[1], "target_id": args[2]}
                elif func_name == 'table' and len(args) >= 2:
                    token = {"type": "UI_TABLE", "headers": args[0], "rows": args[1]}
                elif func_name == 'root_css' and len(args) >= 1:
                    token = {"type": "UI_ROOT_CSS", "css_vars": args[0]}
                else:
                    token = None
    
                if token is not None:
                    if 'css' in kwargs:
                        token['css'] = kwargs['css']
                    if 'class' in kwargs:
                        token['class'] = kwargs['class']
                    COMPILED_TOKENS.append(token)
        self.generic_visit(node)


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
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            self.wfile.write(json.dumps(COMPILED_TOKENS).encode())

        elif clean_path == '/stream':
            self.send_response(200)
            self.send_header('Content-Type', 'text/event-stream')
            self.send_header('Cache-Control', 'no-cache')
            self.send_header('Connection', 'keep-alive')
            self.end_headers()
            import queue
            client_queue = queue.Queue()
            with sse_lock:
                sse_clients.append(client_queue)
            # Send current state on connect
            with state_lock:
                current_state = json.dumps(dict(shared_form_state))
            client_queue.put(("state_update", current_state))

            # Heartbeat timer (keeps connection alive)
            def heartbeat():
                while True:
                    try:
                        client_queue.put(("heartbeat", ""), timeout=15)
                    except queue.Full:
                        break
            heartbeat_thread = threading.Thread(target=heartbeat, daemon=True)
            heartbeat_thread.start()

            try:
                while True:
                    event_type, data = client_queue.get()
                    if event_type == "close":
                        break
                    # heartbeat is sent as a comment to keep connection alive
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

        elif clean_path in ('', '/', '/index.html'):
            self.send_response(200)
            self.send_header('Content-Type', 'text/html')
            self.end_headers()
            base_dir = os.path.dirname(os.path.abspath(__file__))
            html_path = os.path.join(base_dir, 'index.html')
            with open(html_path, 'rb') as f:
                self.wfile.write(f.read())
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
            is_valid = any(t.get('cmd') == requested_cmd for t in COMPILED_TOKENS if t['type'] == 'OS_GATEKEEPER')

            if is_valid:
                try:
                    # shell=True is kept for pipes/redirects; exact match above prevents injection.
                    result = subprocess.run(requested_cmd, shell=True, capture_output=True, text=True, timeout=5)
                    response_text = result.stdout if result.stdout else result.stderr
                except Exception as e:
                    response_text = f"Error: {str(e)}"
                    traceback.print_exc()
            else:
                response_text = "Security Violation: Dynamic evaluation pipeline rejected."

            resp = {"output": response_text.strip(), "target_id": target_id}
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps(resp).encode())
            broadcast_event("command_output", resp)

        elif self.path == '/trigger_callback':
            func_name = post_data.get('callback_name')
            form_state = post_data.get('form_state', {})
            target_id = post_data.get('target_id')
            is_registered = any(t.get('callback_name') == func_name for t in COMPILED_TOKENS if t['type'] == 'UI_CALLBACK_BUTTON')

            if is_registered and TARGET_MODULE and hasattr(TARGET_MODULE, func_name):
                try:
                    target_function = getattr(TARGET_MODULE, func_name)
                    response_text = str(target_function(form_state))
                except Exception as e:
                    response_text = f"Callback Error: {str(e)}"
                    traceback.print_exc()
            else:
                response_text = "Error: Function mapping constraint failure."

            resp = {"output": response_text.strip(), "target_id": target_id}
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps(resp).encode())
            broadcast_event("callback_output", resp)


def main():
    global COMPILED_TOKENS, TARGET_MODULE, SESSION_KEY, TEMP_DIR, PROJECT_DIR, PROJECT_TOKEN_TREE

    parser = argparse.ArgumentParser(description="Pybro Engine Runtime Framework")
    parser.add_argument("script", nargs="?", help="Target python automation script to compile")
    parser.add_argument("--shared", action="store_true", help="Mode 1: Shared Team Mode (exposes to LAN with security key)")
    parser.add_argument("--key", help="Specify a custom security key string")
    parser.add_argument("--connect", help="Mode 2: Remote Client Mirror (pulls blueprints from remote target IP:port)")
    parser.add_argument("--connectable", action="store_true", help="When in shared mode, allow Mode 2 clients to download the signed project tree")
    parser.add_argument("--keep-script", action="store_true", help="In Mode 2, keep the downloaded temporary codebase after exit")
    parser.add_argument("--port", type=int, default=8080, help="Server port (default 8080)")
    parser.add_argument("--verbose", action="store_true", help="Enable HTTP request logging")
    parser.add_argument("--ssl", action="store_true", help="Serve over HTTPS (requires --cert-file/--key-file or auto‑generation)")
    parser.add_argument("--cert-file", help="Path to TLS certificate file (PEM) for --ssl")
    parser.add_argument("--key-file", help="Path to TLS private key file (PEM) for --ssl")
    parser.add_argument("--allow-deps", action="store_true", help="In Mode 2, install external dependencies listed in the project's pybro.toml into a temporary venv")
    args = parser.parse_args()

    port = args.port   # local variable, not global

    # --- MODE 2: Distributed Sandbox Client ---
    if args.connect:
        remote_target = args.connect if args.connect.startswith("http") else f"http://{args.connect}"
        print(f"[*] Mode 2: Launching distributed sandbox link to pipeline: {remote_target}")

        headers = {}
        if args.key:
            headers["X-Pybro-Key"] = args.key
        elif "key=" in remote_target:
            try:
                extracted_key = remote_target.split("key=")[1].split("&")[0]
                headers["X-Pybro-Key"] = extracted_key
            except Exception:
                pass

        # Fetch tokens
        try:
            req = urllib.request.Request(f"{remote_target.split('?')[0].rstrip('/')}/tokens", headers=headers)
            with urllib.request.urlopen(req, timeout=5) as response:
                COMPILED_TOKENS = json.loads(response.read().decode())
            print(f"[+] Synced {len(COMPILED_TOKENS)} remote blueprints.")
        except Exception as e:
            print(f"[-] Failed to fetch tokens: {e}")
            traceback.print_exc()
            sys.exit(1)

        # Fetch signed token tree
        try:
            req = urllib.request.Request(f"{remote_target.split('?')[0].rstrip('/')}/token-tree", headers=headers)
            with urllib.request.urlopen(req, timeout=10) as response:
                if response.status == 403:
                    print("[-] Master does not allow distributed connections (--connectable is disabled on the server).")
                    sys.exit(1)
                token_tree = json.loads(response.read().decode())
                signature = token_tree.pop('signature', None)
                if not signature:
                    raise ValueError("Token tree missing signature")
                # Verify signature
                payload_json = json.dumps(token_tree, sort_keys=True, separators=(',', ':')).encode('utf-8')
                expected_sig = hmac.new(args.key.encode('utf-8') if args.key else b'', payload_json, hashlib.sha256).hexdigest()
                if not hmac.compare_digest(expected_sig, signature):
                    raise ValueError("Invalid signature – possible tampering or wrong key")
                print("[+] Token tree signature verified.")
                ui_tokens = token_tree['ui_tokens']
                COMPILED_TOKENS = ui_tokens   # Replace with the remote tokens
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

        # Create temp directory and extract all files
        TEMP_DIR = tempfile.mkdtemp(prefix='pybro_')
        for rel_path, content in files.items():
            dest_path = os.path.join(TEMP_DIR, rel_path)
            os.makedirs(os.path.dirname(dest_path), exist_ok=True)
            with open(dest_path, 'w', encoding='utf-8') as f:
                f.write(content)
        print(f"[+] Codebase extracted to {TEMP_DIR}")

        # Add temp directory to sys.path
        if TEMP_DIR not in sys.path:
            sys.path.insert(0, TEMP_DIR)

        # Handle external dependencies
        if requires:
            if args.allow_deps:
                print("[*] Installing external dependencies...")
                venv_dir = os.path.join(TEMP_DIR, '.venv')
                try:
                    subprocess.run([sys.executable, '-m', 'venv', venv_dir], check=True, capture_output=True)
                except subprocess.CalledProcessError as e:
                    print(f"[!] Failed to create virtual environment: {e.stderr.decode()}")
                    sys.exit(1)

                if os.name == 'nt':
                    pip_path = os.path.join(venv_dir, 'Scripts', 'pip.exe')
                    py_path = os.path.join(venv_dir, 'Scripts', 'python.exe')
                else:
                    pip_path = os.path.join(venv_dir, 'bin', 'pip')
                    py_path = os.path.join(venv_dir, 'bin', 'python')

                cache_dir = os.path.join(TEMP_DIR, 'pip_cache')
                env = os.environ.copy()
                env['PIP_CACHE_DIR'] = cache_dir

                for dep in requires:
                    print(f"  - Installing {dep}")
                    try:
                        subprocess.run([pip_path, 'install', dep], check=True, capture_output=True, text=True, env=env)
                    except subprocess.CalledProcessError as e:
                        print(f"[!] Failed to install {dep}: {e.stderr}")
                        print("[!] The script may fail due to missing dependencies.")

                # Add venv site-packages to sys.path
                try:
                    result = subprocess.run([py_path, '-c', "import site; print(';'.join(site.getsitepackages()))"],
                                            capture_output=True, text=True, env=env)
                    if result.returncode == 0:
                        site_packages = result.stdout.strip().split(';')
                        for sp in site_packages:
                            if sp not in sys.path:
                                sys.path.append(sp)
                except Exception:
                    if os.name == 'nt':
                        lib_path = os.path.join(venv_dir, 'Lib', 'site-packages')
                    else:
                        lib_path = os.path.join(venv_dir, 'lib', f'python{sys.version_info.major}.{sys.version_info.minor}', 'site-packages')
                    if os.path.isdir(lib_path) and lib_path not in sys.path:
                        sys.path.append(lib_path)
                print("[+] Dependencies installed.")
            else:
                print(f"[!] This project requires external dependencies: {', '.join(requires)}")
                print("[!] Use --allow-deps to install them in a temporary venv.")
                print("[!] The script may fail if these are not already installed globally.")

        # Load the main module
        main_candidates = [f for f in os.listdir(TEMP_DIR) if f.endswith('.py')]
        main_script = next((f for f in main_candidates if f == 'main.py'), main_candidates[0] if main_candidates else None)
        if main_script:
            module_name = os.path.splitext(main_script)[0]
            spec = importlib.util.spec_from_file_location(module_name, os.path.join(TEMP_DIR, main_script))
            TARGET_MODULE = importlib.util.module_from_spec(spec)
            try:
                spec.loader.exec_module(TARGET_MODULE)
                print(f"[+] Loaded module '{module_name}' from codebase.")
            except Exception as e:
                print(f"[!] Warning: could not execute module: {e}")
                traceback.print_exc()
        else:
            print("[!] No Python files found in the downloaded bundle.")
            sys.exit(1)

        bind_ip = "127.0.0.1"

    # --- DEFAULT MODE & MODE 1 (Master) ---
    else:
        if not args.script:
            parser.print_help()
            sys.exit(1)

        script_path = os.path.abspath(args.script)
        PROJECT_DIR = os.path.dirname(script_path)

        # Make sure the project directory is in sys.path so imports work
        if PROJECT_DIR not in sys.path:
            sys.path.insert(0, PROJECT_DIR)

        with open(script_path, "r") as f:
            ast_tree = ast.parse(f.read())
        parser_obj = PybroUIParser()
        parser_obj.visit(ast_tree)

        try:
            module_name = os.path.splitext(os.path.basename(script_path))[0]
            spec = importlib.util.spec_from_file_location(module_name, script_path)
            TARGET_MODULE = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(TARGET_MODULE)
        except Exception as e:
            print(f"[!] Target callback module linking unavailable: {e}")
            traceback.print_exc()

        if args.shared:
            bind_ip = "0.0.0.0"
            SESSION_KEY = args.key if args.key else secrets.token_hex(4)
        else:
            bind_ip = "127.0.0.1"

        if args.connectable and SESSION_KEY:
            build_token_tree()
            print("[*] Project token tree signed and ready for distribution.")
        elif args.connectable and not SESSION_KEY:
            print("[!] --connectable requires a shared key. Use --shared --key <secret>.")

    # Temp codebase cleanup
    if TEMP_DIR and not args.keep_script:
        def cleanup_temp_dir():
            if os.path.exists(TEMP_DIR):
                shutil.rmtree(TEMP_DIR)
                print(f"[-] Temporary codebase {TEMP_DIR} deleted.")
        atexit.register(cleanup_temp_dir)

    # SSL context setup
    ssl_context = None
    cert_file = None
    key_file = None
    if args.ssl:
        if args.cert_file and args.key_file:
            if not os.path.exists(args.cert_file):
                print(f"[!] Certificate file not found: {args.cert_file}")
                sys.exit(1)
            if not os.path.exists(args.key_file):
                print(f"[!] Key file not found: {args.key_file}")
                sys.exit(1)
            ssl_context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
            try:
                ssl_context.load_cert_chain(args.cert_file, args.key_file)
                print("[*] Using provided TLS certificate.")
            except Exception as e:
                print(f"[!] Failed to load certificate/key: {e}")
                sys.exit(1)
        else:
            if sys.version_info < (3, 9):
                print("[!] --ssl requires Python 3.9 or later for automatic certificate generation.")
                print("[!] Provide your own certificate with --cert-file and --key-file.")
                sys.exit(1)
            if not hasattr(ssl.SSLContext, 'generate_self_signed_certificate'):
                print("[!] Your Python installation does not support automatic self‑signed certificates.")
                print("[!] Provide your own certificate with --cert-file and --key-file, or use a reverse proxy.")
                sys.exit(1)
            try:
                ssl_context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
                cert_pem, key_pem = ssl_context.generate_self_signed_certificate(
                    ("localhost",), valid_days=365
                )
                cert_file = tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.pem')
                cert_file.write(cert_pem)
                cert_file.close()
                key_file = tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.pem')
                key_file.write(key_pem)
                key_file.close()
                ssl_context.load_cert_chain(cert_file.name, key_file.name)

                cert_der = ssl.PEM_cert_to_DER_cert(cert_pem)
                fingerprint = hashlib.sha256(cert_der).hexdigest()
                print(f"[*] Self‑signed certificate SHA256 fingerprint: {fingerprint}")
            except Exception as e:
                print(f"[!] Failed to generate SSL certificate: {e}")
                sys.exit(1)

    # Threaded server
    class ThreadedTCPServer(socketserver.ThreadingMixIn, socketserver.TCPServer):
        allow_reuse_address = True
        daemon_threads = True

    try:
        with ThreadedTCPServer((bind_ip, port), EphemeralServer) as httpd:
            httpd.verbose = args.verbose

            if ssl_context:
                httpd.socket = ssl_context.wrap_socket(httpd.socket, server_side=True)

            protocol = "https" if ssl_context else "http"
            print(f"\n=======================================================")
            print(f"[*] PYBRO ENGINE SYSTEM UPGRADE ACTIVE")
            print(f"[*] Bound Interface Location: {protocol}://{bind_ip}:{port}")

            if SESSION_KEY:
                print(f"[⚠️] SECURITY ENFORCED: Shared Key Mode active.")
                if args.connectable:
                    print(f"[⚠️] Distributed connections ENABLED (--connectable)")
                else:
                    print(f"[⚠️] Distributed connections DISABLED (no --connectable)")
                print(f"[⚠️] TARGET DEVICE PASS-LINK:")
                print(f"    {protocol}://<your_server_ip>:{port}/?key={SESSION_KEY}")
                print(f"=======================================================\n")
            else:
                print(f"[*] Security Layer: Local Sandbox Mode (No Key Required)")
                print(f"=======================================================\n")
                if not args.connect:
                    webbrowser.open(f"{protocol}://localhost:{port}")

            httpd.serve_forever()
    except KeyboardInterrupt:
        print("\n[-] Clean volatile memory purge done.")
    except OSError as e:
        print(f"[!] Could not start server: {e}")
        sys.exit(1)
    finally:
        if cert_file:
            os.unlink(cert_file.name)
        if key_file:
            os.unlink(key_file.name)


if __name__ == "__main__":
    main()