from pybro import ui

def show_details(form):
    return [{"action": "toggle_section", "section_id": "details_panel", "visible": True}]

def hide_details(form):
    return [{"action": "toggle_section", "section_id": "details_panel", "visible": False}]

ui.root_css({"--accent": "#f97316"})

ui.page_start("Section Demo")
ui.title("Dynamic Section Example")

ui.row_start()
ui.button_callback("Show Details", "show_details")
ui.button_callback("Hide Details", "hide_details")
ui.row_end()

ui.section_start("details_panel", visible=False)
ui.title("Details Panel", css={"fontSize": "1.5rem"})
ui.input_text("username", "Username")
ui.checkbox("remember", "Remember me")
ui.table(["Field", "Value"], [["Username", "—"], ["Remember", "—"]])
ui.section_end()

ui.page_end()