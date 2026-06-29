# state.py
import threading

from .logger import Logger, DEBUG, INFO, WARN, ERROR

# ---------- Tree ----------
UI_ROOT = None          # root UINode
tree_lock = threading.Lock()

# ---------- Module ----------
TARGET_MODULE = None

# ---------- Security ----------
SESSION_KEY = None

# ---------- Temp / project ----------
TEMP_DIR = None
PROJECT_DIR = None

# ---------- Signed token tree (for distributed mode) ----------
PROJECT_TOKEN_TREE = None

# ---------- Shared form state (bi‑directional SSE) ----------
shared_form_state = {}
state_lock = threading.Lock()

# ---------- SSE real‑time broadcast ----------
sse_clients = []
sse_lock = threading.Lock()

# ---------- Logger ----------
# Default: show info, warnings, and errors (no debug spam)
logger = Logger(level=INFO | WARN | ERROR)

def set_log_level(level):
    """Convenience to change the logger level globally.
    level can be an integer bitmask or a string like 'debug,info'."""
    if isinstance(level, str):
        logger.set_level_from_string(level)
    else:
        logger.set_level(level)

def broadcast_event(event_type, data):
    """Push an event to all connected SSE clients. Non‑string data is JSON‑serialised."""
    import json
    if not isinstance(data, str):
        data = json.dumps(data, default=str)
    with sse_lock:
        dead = []
        for client_queue in sse_clients:
            try:
                client_queue.put((event_type, data))
            except Exception:
                dead.append(client_queue)
                logger.debug(f"SSE client queue dead, will be removed")
        for d in dead:
            sse_clients.remove(d)
        if dead:
            logger.debug(f"Removed {len(dead)} dead SSE clients, {len(sse_clients)} remaining")
        logger.debug(f"Broadcast event '{event_type}' to {len(sse_clients)} clients")