# mytool.py
from pybro import ui

# --- Backend callback (runs when the button is clicked) ---
def run_audit(form_data):
    target = form_data.get("target_ip", "0.0.0.0")
    profile = form_data.get("scan_profile", "Standard Scan")
    verbose = form_data.get("verbose", False)
    return (
        f"[SUCCESS] Audit dispatched.\n"
        f"[*] Target: {target}\n"
        f"[*] Profile: {profile}\n"
        f"[*] Verbose Mode: {'ON' if verbose else 'OFF'}"
    )

# --- UI Blueprint (all tokens) ---
ui.title("Full Token Showcase Dashboard")

# Row with text input and checkbox
ui.row_start()
ui.input_text("target_ip", "Target IP Address")
ui.checkbox("verbose", "Enable Verbose Logging")
ui.row_end()

# Row with dropdown
ui.row_start()
ui.dropdown("scan_profile", "Audit Profile", ["Standard Scan", "Deep Analysis", "Custom"])
ui.row_end()

# Math compute section
ui.title("Instant Client‑Side Math")
ui.row_start()
ui.input_text("base", "Base Value")
ui.input_text("exp", "Exponent")
ui.row_end()
ui.math_compute("math_result", "{base} ** {exp}")
ui.row_start()
ui.text_area("math_result", "Computed Power Result")
ui.row_end()

# OS command (safe example)
ui.os_command("echo 'System scan initiated'", "Run System Echo", "os_output")
ui.text_area("os_output", "OS Command Output")

# Static data table
headers = ["ID", "Node", "Status"]
rows = [
    ["1", "192.168.1.1", "Online"],
    ["2", "192.168.1.2", "Offline"],
    ["3", "192.168.1.3", "Online"]
]
ui.table(headers, rows)

# Callback button
ui.button_callback("Run Audit Now", "run_audit")
