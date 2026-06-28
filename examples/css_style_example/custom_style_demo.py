from pybro import ui

def greet(form):
    name = form.get("name", "World")
    return f"Hello, {name}!"

def update_theme(form):
    return [
        {"action": "set_css", "token_index": 2, "value": {"color": "#ff0", "fontSize": "3rem"}},
        {"action": "set_class", "token_index": 5, "value": "urgent-output"},
    ]

ui.root_css({"--accent": "#f97316"})

ui.page_start("Styled Dashboard")

ui.title("Custom CSS Demo", class_="main-title")

ui.row_start()
ui.input_text("name", "Your Name", class_="fancy-input")
ui.checkbox("subscribe", "Subscribe", class_="fancy-check")
ui.row_end()

ui.dropdown("level", "Experience", ["Beginner", "Pro", "Expert"], class_="fancy-dropdown")

ui.text_area("greeting", "Greeting", class_="greeting-box")

ui.button_callback("Greet Me", "greet", target_id="greeting", class_="primary-btn")

ui.os_command("echo 'Processing...' && sleep 1 && echo 'Done'",
              "Run System Echo", "cmd-output", class_="terminal-block")

ui.table(["ID", "Name", "Status"],
         [["1","Alice","Active"], ["2","Bob","Inactive"]],
         class_="data-grid")

ui.button_callback("Change Theme", "update_theme", class_="theme-btn")

ui.page_end()