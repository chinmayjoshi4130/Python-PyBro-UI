# state.py
import threading

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
        for d in dead:
            sse_clients.remove(d)