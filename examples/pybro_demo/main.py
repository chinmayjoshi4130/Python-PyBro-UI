from pybro import ui
from scanner import run_ping, generate_report   # multi‑file import

# ----- Callbacks -----
def ping_host(form):
    target = form.get("host", "127.0.0.1")
    return run_ping(target)

def update_report(form):
    return generate_report(form)

def toggle_advanced(form):
    # Toggle the advanced section by id – no index needed!
    return [{"action": "toggle_section", "section_id": "advanced_section", "visible": True}]

def hide_advanced(form):
    return [{"action": "toggle_section", "section_id": "advanced_section", "visible": False}]

# ----- UI definition -----
ui.root_css({"--bg": "#0a0e17"})

# ======================== PAGE 1 – Dashboard ========================
ui.page_start("Dashboard")

ui.title("Network Tools Dashboard", css={"fontSize": "2rem"})

ui.input_text("action", "Current Action", css={"border": "2px solid var(--accent)"})

ui.button_callback("Generate Report", "update_report", target_id="report_output",
                   css={"background": "linear-gradient(135deg, var(--accent), #b45309)", "border": "none"})
ui.text_area("report_output", "Report", css={"border": "1px solid var(--green)"})

ui.page_end()

# ======================== PAGE 2 – Scanner ========================
ui.page_start("Scanner")

ui.tab_group_start()

# --- Tab 1: Quick Ping ---
ui.tab_start("Quick Ping")
ui.input_text("host", "Target IP / Host")
ui.text_area("ping_output", "Ping Result", css={"border": "1px solid var(--accent)"})
ui.button_callback("Ping", "ping_host", target_id="ping_output",
                   css={"background": "var(--accent)", "border": "none"})
ui.tab_end()

# --- Tab 2: OS Command ---
ui.tab_start("OS Command")
ui.os_command("ping -c 1 google.com", "Ping google", "cmd_output")
# (the terminal is built‑in)
ui.tab_end()

ui.tab_group_end()
ui.page_end()

# ======================== PAGE 3 – Logs ========================
ui.page_start("Logs")

ui.title("Activity Log")
HEADERS = ["Time", "Action", "Status"]
ROWS = [
    ["12:00", "start", "OK"],
    ["12:05", "scan", "OK"],
]
# Added target_id so we can patch it by name instead of fragile index
ui.table(HEADERS, ROWS, class_="data-grid", target_id="activity_log")

ui.page_end()

# ======================== PAGE 4 – Settings ========================
ui.page_start("Settings")

ui.title("Settings")

ui.row_start()
ui.button_callback("Show Advanced", "toggle_advanced",
                   css={"background": "var(--accent)", "border": "none"})
ui.button_callback("Hide Advanced", "hide_advanced")
ui.row_end()

# Advanced section – initially hidden
ui.section_start("advanced_section", visible=False)
ui.input_text("api_key", "API Key")
ui.checkbox("dark_mode", "Dark Mode")
ui.dropdown("log_level", "Log Level", ["info", "debug", "warn"])
ui.section_end()

ui.page_end()
