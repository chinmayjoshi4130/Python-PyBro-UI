from pybro import ui
from scanner import run_ping, generate_report   # multi‑file import

# ----- Callbacks -----
def ping_host(form):
    target = form.get("host", "127.0.0.1")
    return run_ping(target)

def update_report(form):
    return generate_report(form)

def toggle_advanced(form):
    return [{"action": "toggle_section", "section_id": "advanced_section", "visible": True}]

def hide_advanced(form):
    return [{"action": "toggle_section", "section_id": "advanced_section", "visible": False}]

def print_all_inputs(form):
    """Return a formatted view of all current input values."""
    lines = []
    for key, value in sorted(form.items()):
        lines.append(f"{key}: {value}")
    return "\n".join(lines) if lines else "(no inputs yet)"

# ----- UI definition -----
ui.root_css({"--bg": "#0a0e17"})

# ======================== PAGE 1 – Dashboard ========================
ui.page_start("Dashboard")

ui.title("Network Tools Dashboard", css={"fontSize": "2rem"})

ui.markdown(
    "## Quick Guide\n\n"
    "* **Dashboard** – view reports & logs\n"
    "* **Scanner** – ping hosts or run OS commands\n"
    "* **Widgets** – try out new UI components\n"
    "* **Settings** – configure advanced options\n\n"
    "Tip: the `--watch` flag reloads the UI on script changes."
)

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
ui.table(HEADERS, ROWS, class_="data-grid", target_id="activity_log")

ui.page_end()

# ======================== PAGE 4 – Widgets ========================
ui.page_start("Widgets")

ui.title("New Widgets Showcase", css={"fontSize": "1.8rem"})

ui.row_start()
ui.password("api_secret", "API Secret")
ui.toggle("notifications", "Enable Notifications", checked=True)
ui.row_end()

ui.row_start()
ui.date("start_date", "Start Date")
ui.slider("timeout", "Timeout (sec)", 5, 60, 5)
ui.row_end()

ui.input("email", "Email Address", type="email")
ui.progress("scan_progress", "Scan Progress", value=25, max=100)

ui.button_callback("Print All Inputs", "print_all_inputs", target_id="all_inputs_display")
ui.text_area("all_inputs_display", "Current Form State")

ui.page_end()

# ======================== PAGE 5 – Settings ========================
ui.page_start("Settings")

ui.title("Settings")

ui.row_start()
ui.button_callback("Show Advanced", "toggle_advanced",
                   css={"background": "var(--accent)", "border": "none"})
ui.button_callback("Hide Advanced", "hide_advanced")
ui.row_end()

ui.slider("poll_seconds", "Poll Interval (sec)", 1, 30, 1,
          css={"border": "1px solid var(--border)"})

# Advanced section – initially hidden
ui.section_start("advanced_section", visible=False)
ui.input_text("api_key", "API Key")
ui.checkbox("dark_mode", "Dark Mode")
ui.dropdown("log_level", "Log Level", ["info", "debug", "warn"])
ui.section_end()

ui.page_end()