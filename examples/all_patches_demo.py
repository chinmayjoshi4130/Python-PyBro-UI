from pybro import ui

# ---------- existing business logic ----------
def run_audit(form_data):
    target = form_data.get("target_ip", "0.0.0.0")
    profile = form_data.get("scan_profile", "Standard Scan")
    verbose = form_data.get("verbose", False)
    return (
        f"[SUCCESS] Audit dispatched.\n"
        f"[*] Target: {target}\n"
        f"[*] Profile: {profile}\n"
        f"[*] Verbose: {'ON' if verbose else 'OFF'}"
    )

# ---------- new callback that exercises every patch action ----------
def test_patches(form_data):
    """
    This function returns a list of token patches.
    The token indices below match the order of ui.* calls in this script.
    (Check /tokens if you ever need to verify.)
    """
    patches = [
        # 1. Change the text of the first title (index 1)
        {"action": "set_text", "token_index": 1, "value": "⚡ Patches Applied!"},

        # 2. Change the label of the "Target IP Address" input (index 3)
        {"action": "set_label", "token_index": 3, "value": "Target IP (updated)"},

        # 3. Replace the inline CSS of the same input (add a red border)
        {"action": "set_css", "token_index": 3, "value": {"border": "2px solid var(--red)"}},

        # 4. Add a CSS class to the checkbox (index 4)
        {"action": "set_class", "token_index": 4, "value": "urgent-toggle"},

        # 5. Replace the dropdown options (index 7)
        {"action": "set_options", "token_index": 7, "options": ["Quick", "Full", "Custom (patched)"]},

        # 6. Add a row to the node status table (index 20)
        {"action": "insert_table_row", "token_index": 20, "row": ["2", "10.0.0.1", "Patched"]},

        # 7. Replace all rows of the table with completely new data
        {"action": "set_table_rows", "token_index": 20, "rows": [
            ["X1", "Patched-Node", "OK"],
            ["X2", "Patched-Node2", "OK"]
        ]},
    ]
    return patches

# ---------- UI definition ----------
ui.root_css({
    "--bg": "#0a0e17",
    "--surface": "#111827",
    "--border": "#1f2a44",
    "--text": "#e2e8f0",
    "--accent": "#f97316",
    "--green": "#22c55e",
    "--red": "#ef4444"
})

# index 0: root_css (UI_ROOT_CSS)
# index 1:
ui.title("⚡ Custom Themed Dashboard", css={"color": "var(--accent)", "fontSize": "2.2rem"}, class_="main-title")

# index 2: row_start
ui.row_start(css={"gap": "2rem", "marginBottom": "1rem"})
# index 3:
ui.input_text("target_ip", "Target IP Address", css={"border": "2px solid var(--accent)"})
# index 4:
ui.checkbox("verbose", "Enable Verbose Logging", class_="toggle-checkbox")
# index 5: row_end
ui.row_end()

# index 6: row_start
ui.row_start(css={"gap": "2rem"})
# index 7:
ui.dropdown("scan_profile", "Audit Profile", ["Standard Scan", "Deep Analysis", "Custom"],
            css={"backgroundColor": "#1a2236", "color": "var(--text)"})
# index 8: row_end
ui.row_end()

# index 9:
ui.title("🔢 Instant Client‑Side Math")
# index 10: row_start
ui.row_start()
# index 11:
ui.input_text("base", "Base Value")
# index 12:
ui.input_text("exp", "Exponent")
# index 13: row_end
ui.row_end()
# index 14:
ui.math_compute("math_result", "{base} ** {exp}")
# index 15: row_start
ui.row_start()
# index 16:
ui.text_area("math_result", "Computed Power Result",
             css={"minHeight": "80px", "border": "1px solid var(--accent)"})
# index 17: row_end
ui.row_end()

# index 18:
ui.os_command("echo 'System scan initiated'", "Run System Echo", "os_output",
              css={"backgroundColor": "#0f172a", "minHeight": "80px"})

# index 19:
ui.title("📊 Node Status")
HEADERS = ["ID", "Node", "Status"]
ROWS = [["1","192.168.1.1","Online"]]
# index 20:
ui.table(HEADERS, ROWS, css={"border": "1px solid var(--accent)", "marginTop": "0.5rem"})

# index 21:
ui.text_area("audit_result", "Audit Output",
             css={"minHeight": "100px", "border": "1px solid var(--green)"})
# index 22:
ui.button_callback("🚀 Run Audit Now", "run_audit",
                   target_id="audit_result",
                   css={"background": "linear-gradient(135deg, #f97316, #b45309)", "border": "none"})

# index 23: new button that triggers the patch callback
ui.button_callback("🧪 Test All Patches", "test_patches",
                   target_id="audit_result",
                   css={"background": "linear-gradient(135deg, #22c55e, #166534)", "border": "none"})