from pybro import ui

# ----- Page & UI definition -----
ui.page_start("TextArea Targeting Test")

ui.text_area("log", "Console Output")                       # id = "log"

ui.button_callback(
    "Write via Patch",                                      # button text
    "write_to_log",                                         # callback name
    target_id="log"                                         # the text‑area to update
)

ui.os_command(
    "echo 'Output from OS command'",                        # shell command
    "Echo a test string",                                   # description
    target_id="log"                                         # target text‑area
)

ui.page_end()

# ----- Python callbacks -----
def write_to_log(form_state):
    """Return a patch that updates the text‑area by its id."""
    return [
        {
            "action": "set_text",
            "target_id": "log",                             # <-- id, not token_index
            "value": "Hello from callback! (id‑based patch)"
        }
    ]