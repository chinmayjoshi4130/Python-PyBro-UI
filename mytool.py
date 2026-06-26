from pybro import ui

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

ui.root_css({
    "--bg": "#0a0e17",
    "--surface": "#111827",
    "--border": "#1f2a44",
    "--text": "#e2e8f0",
    "--accent": "#f97316",
    "--green": "#22c55e",
    "--red": "#ef4444"
})

ui.title("⚡ Custom Themed Dashboard", css={"color": "var(--accent)", "fontSize": "2.2rem"}, class_="main-title")

ui.row_start(css={"gap": "2rem", "marginBottom": "1rem"})
ui.input_text("target_ip", "Target IP Address", css={"border": "2px solid var(--accent)"})
ui.checkbox("verbose", "Enable Verbose Logging", class_="toggle-checkbox")
ui.row_end()

ui.row_start(css={"gap": "2rem"})
ui.dropdown("scan_profile", "Audit Profile", ["Standard Scan", "Deep Analysis", "Custom"],
            css={"backgroundColor": "#1a2236", "color": "var(--text)"})
ui.row_end()

ui.title("🔢 Instant Client‑Side Math")
ui.row_start()
ui.input_text("base", "Base Value")
ui.input_text("exp", "Exponent")
ui.row_end()
ui.math_compute("math_result", "{base} ** {exp}")
ui.row_start()
ui.text_area("math_result", "Computed Power Result",
             css={"minHeight": "80px", "border": "1px solid var(--accent)"})
ui.row_end()

# OS command – its own output is built‑in, just style it
ui.os_command("echo 'System scan initiated'", "Run System Echo", "os_output",
              css={"backgroundColor": "#0f172a", "minHeight": "80px"})

ui.title("📊 Node Status")
HEADERS = ["ID", "Node", "Status"]
ROWS = [["1","192.168.1.1","Online"]]
ui.table(HEADERS, ROWS,css={"border": "1px solid var(--accent)", "marginTop": "0.5rem"})

ui.text_area("audit_result", "Audit Output",
             css={"minHeight": "100px", "border": "1px solid var(--green)"})
ui.button_callback("🚀 Run Audit Now", "run_audit",
                   target_id="audit_result",
                   css={"background": "linear-gradient(135deg, #f97316, #b45309)", "border": "none"})
