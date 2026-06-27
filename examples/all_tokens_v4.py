from pybro import ui

# ── Business logic ────────────────────────────────────────────
def run_scan(form):
    host = form.get("host", "127.0.0.1")
    return f"[SCAN] Target: {host} – OK"

def patch_all(form):
    """
    Demonstrates dynamic token patches.
    Token indices will depend on the order of ui.* calls below.
    Open /tokens in the browser to see the actual indices.
    """
    return [
        # Change the title on page 1 (index may vary – adjust as needed)
        {"action": "set_text", "token_index": 2, "value": "⚡ Patches Applied!"},
        # Add a row to the table on page 2
        {"action": "insert_table_row", "token_index": 19, "row": ["4", "10.0.0.4", "patched"]},
        # Update options on the dropdown inside a tab
        {"action": "set_options", "token_index": 11, "options": ["alpha", "beta", "gamma"]},
    ]

# ── UI definition ─────────────────────────────────────────────
ui.root_css({
    "--bg": "#0a0e17",
    "--accent": "#f97316",
    "--surface": "#111827",
    "--border": "#1f2a44",
})

# ██████████████ PAGE 1 ██████████████
ui.page_start("Dashboard")

ui.title("Welcome to Pybro v4", css={"fontSize": "2rem"})

ui.row_start()
ui.input_text("host", "Target Host")
ui.checkbox("verbose", "Verbose Logging")
ui.row_end()

ui.text_area("output", "Scan Output",
             css={"minHeight": "80px", "border": "1px solid var(--green)"})
ui.button_callback("Start Scan", "run_scan", target_id="output")

ui.page_end()

# ██████████████ PAGE 2 – with tabs ██████████████
ui.page_start("Nodes")

ui.title("Node Inventory")

ui.tab_group_start()

# --- Tab 1 ---
ui.tab_start("Table")
HEADERS = ["ID", "IP", "Status"]
ROWS = [
    ["1", "192.168.1.1", "online"],
    ["2", "192.168.1.2", "offline"],
    ["3", "192.168.1.3", "online"],
]
ui.table(HEADERS, ROWS, css={"marginTop": "0.5rem"})
ui.tab_end()

# --- Tab 2 ---
ui.tab_start("Actions")
ui.button_callback("Apply Patches", "patch_all", target_id="patch_output")
ui.text_area("patch_output", "Patch Result",
             css={"minHeight": "60px", "border": "1px solid var(--accent)"})
ui.tab_end()

ui.tab_group_end()
ui.page_end()

# ██████████████ PAGE 3 – math & OS ██████████████
ui.page_start("Compute & OS")

ui.title("Client‑Side Math")
ui.row_start()
ui.input_text("a", "Value A")
ui.input_text("b", "Value B")
ui.row_end()
ui.math_compute("math_result", "{a} * {b} + 10")
ui.text_area("math_result", "Result",
             css={"border": "1px solid var(--accent)"})

ui.title("OS Command")
ui.dropdown("profile", "Scan Profile", ["quick", "full", "custom"])
ui.os_command("echo 'Line 1' && sleep 1 && echo 'Line 2' && sleep 1 && echo 'Done'",
              "Longer Command", "os_output")
# The gatekeeper output appears here automatically
ui.page_end()