from pybro import ui
from scanner import run_scan
from utils import subnet_size

# -------------------- Callbacks --------------------
def cb_run_audit(form_data):
    target = form_data.get("target_ip", "0.0.0.0")
    profile = form_data.get("scan_profile", "Standard Scan")
    verbose = form_data.get("verbose", False)
    return run_scan(target, profile, verbose)


def cb_subnet_calc(form_data):
    try:
        mask = int(form_data.get("cidr_suffix", 24))
        size = subnet_size(mask)
        return f"Subnet /{mask} → {size} usable hosts"
    except Exception as e:
        return f"[ERROR] {e}"


# -------------------- UI Definition --------------------
ui.root_css({
    "--bg": "#0b0f19",
    "--surface": "#131a2b",
    "--border": "#2a3350",
    "--text": "#e0e6f0",
    "--accent": "#6366f1",
    "--green": "#10b981",
    "--red": "#ef4444"
})

ui.title("🌐 NetSweep Recon Dashboard", css={"color": "var(--accent)", "fontSize": "2rem"})

# ----- Target input row -----
ui.row_start(css={"gap": "1.5rem"})
ui.input_text("target_ip", "Target IP / Host", css={"border": "2px solid var(--accent)"})
ui.checkbox("verbose", "Verbose Output", class_="monospace-toggle")
ui.row_end()

# ----- Profile selection -----
ui.row_start()
ui.dropdown("scan_profile", "Scan Profile",
            ["Standard Scan", "Deep Analysis", "Custom"],
            css={"backgroundColor": "#1a2236"})
ui.row_end()

# ----- Reactive math: CIDR subnet calculator -----
ui.title("🔢 Quick Subnet Calculator")
ui.row_start()
ui.input_text("cidr_suffix", "CIDR Suffix (e.g., 24)")
ui.math_compute("subnet_display", "{cidr_suffix}")  # just show the value
ui.row_end()
ui.row_start()
ui.text_area("subnet_display", "Subnet Info",
             css={"minHeight": "50px", "borderColor": "var(--accent)"})
ui.row_end()
ui.button_callback("📊 Calculate Subnet", "cb_subnet_calc",
                   target_id="subnet_display",
                   css={"background": "linear-gradient(135deg, #6366f1, #4f46e5)", "border": "none"})

# ----- OS command gate (safe, harmless) -----
ui.os_command("ping -c 3 127.0.0.1", "Ping Localhost (Test Gate)", "os_output",
              css={"backgroundColor": "#0f172a"})

# ----- Scan table (static) -----
ui.title("📋 Recent Scan History")
HEADERS = ["ID", "Host", "Profile", "Status"]
ROWS = [
    ["1", "192.168.1.1", "Standard Scan", "Completed"],
    ["2", "10.0.0.5", "Deep Analysis", "Pending"]
]
ui.table(HEADERS, ROWS, css={"borderColor": "var(--accent)", "marginTop": "0.5rem"})

# ----- Main scan output -----
ui.text_area("audit_result", "Live Audit Output",
             css={"minHeight": "120px", "border": "1px solid var(--green)"})
ui.button_callback("🚀 Run Full Audit", "cb_run_audit",
                   target_id="audit_result",
                   css={"background": "linear-gradient(135deg, #f97316, #b45309)", "border": "none"})

