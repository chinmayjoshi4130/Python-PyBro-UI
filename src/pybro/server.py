# server.py – entry point
import sys
import os
import ast
import secrets
import argparse
import importlib            
import importlib.util
import webbrowser
import tempfile
import atexit
import subprocess
import threading
import ssl
import hashlib
import shutil
import traceback
import urllib.request
import socketserver
import json
import hmac

from . import state
from .state import logger
from .parser import PybroUIParser
from .tree import (UINode, link_tree, flatten_tree, build_tree_from_flat,
                   build_token_tree, get_bundle_info)
from .handler import EphemeralServer
from .watcher import watch_script

try:
    import tomllib
except ImportError:
    import tomli as tomllib


def main():
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
    parser.add_argument("--log-level", default=None,
                        help="Log level (debug, info, warn, error). Multiple levels can be comma‑separated.")
    parser.add_argument("--log-file", default=None, help="Path to log file (append mode)")
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
        state.PROJECT_DIR = os.path.dirname(script_path_arg)
    else:
        state.PROJECT_DIR = os.getcwd()

    config = {}
    toml_path = os.path.join(state.PROJECT_DIR, 'pybro.toml')
    if os.path.isfile(toml_path):
        try:
            with open(toml_path, 'rb') as f:
                raw = tomllib.load(f)
            config = raw.get('pybro', {})
            for path_key in ('custom-css', 'cert-file', 'key-file', 'entrypoint'):
                if path_key in config and not os.path.isabs(config[path_key]):
                    config[path_key] = os.path.join(state.PROJECT_DIR, config[path_key])
        except Exception:
            logger.warn("Could not parse pybro.toml, ignoring.")

    def get_value(key, cli_value, default, coerce=lambda x: x):
        if cli_value is not None:
            return cli_value
        if key in config:
            return coerce(config[key])
        return default

    # --- Logging configuration (CLI overrides pybro.toml) ---
    log_level_str = args.log_level
    if log_level_str is None:
        log_level_str = config.get('log-level', None)
    if log_level_str is not None:
        state.set_log_level(log_level_str)
        logger.debug(f"Log level set to: {log_level_str}")

    log_file = args.log_file
    if log_file is None:
        log_file = config.get('log-file', None)
    if log_file:
        from .logger import Logger
        new_logger = Logger(level=state.logger.level, logfile=log_file)
        state.logger = new_logger
        # Update the local `logger` variable so subsequent calls go to the file
        globals()['logger'] = new_logger
        # Update already‑imported modules so they use the file logger
        sys.modules['pybro.handler'].logger = new_logger
        sys.modules['pybro.watcher'].logger = new_logger
        sys.modules['pybro.tree'].logger = new_logger
        sys.modules['pybro.parser'].logger = new_logger
        logger.info(f"Log file set to: {log_file}")

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

    allowed_commands = config.get('allowed_commands', None)

    if custom_css and not os.path.isfile(custom_css):
        logger.error(f"Custom CSS file not found: {custom_css}")
        sys.exit(1)

    if args.script and args.script != '.':
        script_path = script_path_arg
    elif entrypoint:
        script_path = os.path.join(state.PROJECT_DIR, entrypoint)
        if not os.path.isfile(script_path):
            logger.error(f"Entry point '{entrypoint}' not found.")
            sys.exit(1)
    elif connect_target is None:
        py_files = [f for f in os.listdir(state.PROJECT_DIR) if f.endswith('.py')]
        main_candidate = next((f for f in py_files if f == 'main.py'), py_files[0] if py_files else None)
        if not main_candidate:
            logger.error("No Python files found in project directory.")
            sys.exit(1)
        script_path = os.path.join(state.PROJECT_DIR, main_candidate)
    else:
        script_path = None

    # --- MODE 2 ---
    if connect_target:
        if not connect_target.startswith("http"):
            connect_target = f"http://{connect_target}"
        logger.info(f"Mode 2: Launching distributed sandbox link to pipeline: {connect_target}")

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

        try:
            req = urllib.request.Request(f"{connect_target.split('?')[0].rstrip('/')}/tokens", headers=headers)
            with urllib.request.urlopen(req, timeout=5) as response:
                flat_tokens = json.loads(response.read().decode())
            logger.info(f"Synced {len(flat_tokens)} remote blueprints.")
        except Exception as e:
            logger.error(f"Failed to fetch tokens: {e}")
            logger.debug(traceback.format_exc())
            sys.exit(1)

        try:
            req = urllib.request.Request(f"{connect_target.split('?')[0].rstrip('/')}/token-tree", headers=headers)
            with urllib.request.urlopen(req, timeout=10) as response:
                if response.status == 403:
                    logger.error("Master does not allow distributed connections (--connectable is disabled on the server).")
                    sys.exit(1)
                token_tree = json.loads(response.read().decode())
                signature = token_tree.pop('signature', None)
                if signature:
                    if not key:
                        logger.error("The master requires a shared key. Please provide the --key argument.")
                        sys.exit(1)
                    payload_json = json.dumps(token_tree, sort_keys=True, separators=(',', ':')).encode('utf-8')
                    expected_sig = hmac.new(key.encode('utf-8'), payload_json, hashlib.sha256).hexdigest()
                    if not hmac.compare_digest(expected_sig, signature):
                        raise ValueError("Invalid signature – possible tampering or wrong key")
                    logger.info("Token tree signature verified.")
                else:
                    logger.info("No signature present – proceeding without verification.")
                ui_tokens = token_tree['ui_tokens']
                files = token_tree['files']
                requires = token_tree.get('requires', [])
        except urllib.error.HTTPError as e:
            if e.code == 403:
                logger.error("Master does not allow distributed connections (--connectable is disabled on the server).")
                sys.exit(1)
            else:
                logger.error(f"Failed to fetch token tree: {e}")
                logger.debug(traceback.format_exc())
                sys.exit(1)
        except Exception as e:
            logger.error(f"Failed to fetch or verify token tree: {e}")
            logger.debug(traceback.format_exc())
            sys.exit(1)

        state.UI_ROOT = build_tree_from_flat(ui_tokens)

        state.TEMP_DIR = tempfile.mkdtemp(prefix='pybro_')
        for rel_path, content in files.items():
            dest_path = os.path.join(state.TEMP_DIR, rel_path)
            os.makedirs(os.path.dirname(dest_path), exist_ok=True)
            with open(dest_path, 'w', encoding='utf-8') as f:
                f.write(content)
        logger.info(f"Codebase extracted to {state.TEMP_DIR}")

        # Auto‑detect a CSS file bundled by the master
        if not custom_css:
            css_files = [f for f in os.listdir(state.TEMP_DIR) if f.endswith('.css')]
            if css_files:
                custom_css = os.path.join(state.TEMP_DIR, css_files[0])
                logger.info(f"Auto-detected custom CSS: {css_files[0]}")

        if state.TEMP_DIR not in sys.path:
            sys.path.insert(0, state.TEMP_DIR)

        if requires and allow_deps:
            logger.info("Installing external dependencies...")
            venv_dir = os.path.join(state.TEMP_DIR, '.venv')
            try:
                subprocess.run([sys.executable, '-m', 'venv', venv_dir], check=True, capture_output=True)
            except subprocess.CalledProcessError as e:
                logger.error(f"Failed to create virtual environment: {e.stderr.decode()}")
                sys.exit(1)
            pip_path = os.path.join(venv_dir, 'Scripts' if os.name == 'nt' else 'bin', 'pip')
            py_path = os.path.join(venv_dir, 'Scripts' if os.name == 'nt' else 'bin', 'python')
            env = os.environ.copy()
            env['PIP_CACHE_DIR'] = os.path.join(state.TEMP_DIR, 'pip_cache')
            for dep in requires:
                logger.info(f"  Installing {dep}")
                try:
                    subprocess.run([pip_path, 'install', dep], check=True, capture_output=True, text=True, env=env)
                except subprocess.CalledProcessError as e:
                    logger.error(f"Failed to install {dep}: {e.stderr}")
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
            logger.info("Dependencies installed.")

        if entrypoint:
            main_script = entrypoint
        else:
            candidates = [f for f in os.listdir(state.TEMP_DIR) if f.endswith('.py')]
            main_script = next((f for f in candidates if f == 'main.py'), candidates[0] if candidates else None)
            if not main_script:
                logger.error("No Python files found in the downloaded bundle.")
                sys.exit(1)

        module_name = os.path.splitext(main_script)[0]
        spec = importlib.util.spec_from_file_location(module_name, os.path.join(state.TEMP_DIR, main_script))
        state.TARGET_MODULE = importlib.util.module_from_spec(spec)
        try:
            spec.loader.exec_module(state.TARGET_MODULE)
            logger.info(f"Loaded module '{module_name}' from codebase.")
        except Exception as e:
            logger.warn(f"Could not execute module: {e}")
            logger.debug(traceback.format_exc())

        bind_ip = "127.0.0.1"

    else:
        # --- DEFAULT MODE & MODE 1 (Master) ---
        if not script_path:
            parser.print_help()
            sys.exit(1)

        if state.PROJECT_DIR not in sys.path:
            sys.path.insert(0, state.PROJECT_DIR)

        with open(script_path, "r") as f:
            ast_tree = ast.parse(f.read())
        parser_obj = PybroUIParser()
        parser_obj.visit(ast_tree)
        state.UI_ROOT = parser_obj.root
        logger.info(f"Parsed script: {script_path}")

        module_name = os.path.splitext(os.path.basename(script_path))[0]
        spec = importlib.util.spec_from_file_location(module_name, script_path)
        state.TARGET_MODULE = importlib.util.module_from_spec(spec)
        try:
            spec.loader.exec_module(state.TARGET_MODULE)
            logger.info(f"Module '{module_name}' loaded.")
        except Exception as e:
            logger.warn(f"Target callback module linking unavailable: {e}")
            logger.debug(traceback.format_exc())

        link_tree(state.UI_ROOT, state.TARGET_MODULE)

        if shared:
            bind_ip = "0.0.0.0"
            state.SESSION_KEY = key if key else secrets.token_hex(4)
        else:
            bind_ip = "127.0.0.1"

        if connectable:
            if not shared:
                logger.error("--connectable requires --shared (shared mode). Exiting.")
                sys.exit(1)
            if state.SESSION_KEY:
                build_token_tree()
                logger.info("Project token tree signed and ready for distribution.")
            else:
                logger.error("--connectable requires a shared key. Use --shared --key <secret>.")
                sys.exit(1)

    if state.TEMP_DIR and not keep_script:
        def cleanup_temp_dir():
            if os.path.exists(state.TEMP_DIR):
                shutil.rmtree(state.TEMP_DIR)
                logger.info(f"Temporary codebase {state.TEMP_DIR} deleted.")
        atexit.register(cleanup_temp_dir)

    # SSL setup
    ssl_context = None
    cert_file_temp = None
    key_file_temp = None
    if ssl_enabled:
        if cert_file and key_file:
            if not os.path.exists(cert_file):
                logger.error(f"Certificate file not found: {cert_file}")
                sys.exit(1)
            if not os.path.exists(key_file):
                logger.error(f"Key file not found: {key_file}")
                sys.exit(1)
            ssl_context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
            try:
                ssl_context.load_cert_chain(cert_file, key_file)
                logger.info("Using provided TLS certificate.")
            except Exception as e:
                logger.error(f"Failed to load certificate/key: {e}")
                sys.exit(1)
        else:
            if sys.version_info < (3, 9):
                logger.error("--ssl requires Python 3.9 or later for automatic certificate generation.")
                logger.error("Provide your own certificate with --cert-file and --key-file.")
                sys.exit(1)
            if not hasattr(ssl.SSLContext, 'generate_self_signed_certificate'):
                logger.error("Your Python installation does not support automatic self‑signed certificates.")
                sys.exit(1)
            try:
                ssl_context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
                cert_pem, key_pem = ssl_context.generate_self_signed_certificate(("localhost",), valid_days=365)
                cert_file_temp = tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.pem')
                cert_file_temp.write(cert_pem)
                cert_file_temp.close()
                key_file_temp = tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.pem')
                key_file_temp.write(key_pem)
                key_file_temp.close()
                ssl_context.load_cert_chain(cert_file_temp.name, key_file_temp.name)
                fingerprint = hashlib.sha256(ssl.PEM_cert_to_DER_cert(cert_pem)).hexdigest()
                logger.info(f"Self‑signed certificate SHA256 fingerprint: {fingerprint}")
            except Exception as e:
                logger.error(f"Failed to generate SSL certificate: {e}")
                sys.exit(1)

    class ThreadedTCPServer(socketserver.ThreadingMixIn, socketserver.TCPServer):
        allow_reuse_address = True
        daemon_threads = True

    try:
        with ThreadedTCPServer((bind_ip, port), EphemeralServer) as httpd:
            httpd.verbose = verbose
            httpd.os_timeout = os_timeout
            httpd.poll_interval = poll_interval
            httpd.allowed_commands = allowed_commands
            if custom_css:
                httpd.custom_css_path = os.path.abspath(custom_css)

            if ssl_context:
                httpd.socket = ssl_context.wrap_socket(httpd.socket, server_side=True)

            protocol = "https" if ssl_context else "http"
            logger.info("=" * 55)
            logger.info("PYBRO ENGINE SYSTEM UPGRADE ACTIVE")
            logger.info(f"Bound Interface Location: {protocol}://{bind_ip}:{port}")

            if state.SESSION_KEY:
                logger.info("SECURITY ENFORCED: Shared Key Mode active.")
                if connectable:
                    logger.info("Distributed connections ENABLED (--connectable)")
                else:
                    logger.info("Distributed connections DISABLED (no --connectable)")
                logger.info("TARGET DEVICE PASS-LINK:")
                logger.info(f"    {protocol}://<your_server_ip>:{port}/?key={state.SESSION_KEY}")
            else:
                logger.info("Security Layer: Local Sandbox Mode (No Key Required)")
            logger.info("=" * 55)

            if not connect_target and not state.SESSION_KEY:
                webbrowser.open(f"{protocol}://localhost:{port}")

            if watch and not connect_target:
                logger.info(f"Starting file watcher on {script_path}")
                threading.Thread(target=watch_script, args=(script_path, connectable), daemon=True).start()

            httpd.serve_forever()
    except KeyboardInterrupt:
        logger.info("Clean volatile memory purge done.")
    except OSError as e:
        logger.error(f"Could not start server: {e}")
        sys.exit(1)
    finally:
        if cert_file_temp:
            os.unlink(cert_file_temp.name)
        if key_file_temp:
            os.unlink(key_file_temp.name)


if __name__ == "__main__":
    main()