import subprocess
import time

def run_ping(target):
    """Perform a real ping (platform dependent) and return a one‑liner result."""
    try:
        # Windows uses -n, Unix uses -c
        param = "-n" if subprocess.os.name == "nt" else "-c"
        result = subprocess.run(
            ["ping", param, "1", target],
            capture_output=True, text=True, timeout=5
        )
        if result.returncode == 0:
            return f"{target} – reachable"
        else:
            return f"{target} – unreachable"
    except Exception as e:
        return f"{target} – error ({e})"

def generate_report(form):
    import datetime
    now = datetime.datetime.now().strftime("%H:%M:%S")
    return {
        "message": f"Report updated at {now}",
        "patches": [
            # Now uses target_id instead of token_index – much safer
            {"action": "insert_table_row", "target_id": "activity_log", "row": [now, form.get("action", "?"), "OK"]}
        ]
    }
