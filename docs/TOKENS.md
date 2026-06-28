---

Pybro Token Reference

This document describes every UI token produced by the Pybro parser – its Python call, the HTML it generates, the styling classes / inner elements you can target, and how dynamic updates (patches) work.

---

How styling works

· css argument – a dict of property: value pairs applied as inline styles on the token’s outermost element.
· class_ argument – a CSS class name added to that same outermost element.
· --custom-css file – a stylesheet loaded after the built‑in CSS. Use descendant selectors to reach inner elements like <label>, <input>, <textarea>, etc.

The outermost element for most visual tokens is a <div class="component">.
For titles it is the <h1> itself; for layout rows it is a <div class="ui-row">; for sections it is a <div class="section">.

---

Built‑in CSS variables (customisable via ui.root_css or --custom-css)

Variable Default Role
--bg #0b0f19 Page background
--surface #131a2b Card/component background
--border #2a3350 Borders
--text #e0e6f0 Body text
--accent #6e8efb Highlights, links
--green #00e676 Terminal text, success
--red #ff5252 Errors, warnings
--radius 12px Border radius
--shadow 0 8px … Component shadow

You can override them globally with ui.root_css({…}) at the top of your script, or via your custom CSS file.

---

Token catalogue

UI_TITLE

```python
ui.title("text", css={...}, class_="...")
```

DOM:
<h1>text</h1>

· css and class_ are applied directly to the <h1>.
· No inner elements.

---

UI_INPUT

```python
ui.input_text("id", "label", css={...}, class_="...")
```

DOM (inside wrapper):

```html
<label>label</label>
<input id="id" type="text">
```

Target inner elements: label, input[type="text"]

---

UI_CHECKBOX

```python
ui.checkbox("id", "label", css={...}, class_="...")
```

DOM (inside wrapper):

```html
<label style="display:flex; align-items:center; gap:8px;">
  <input id="id" type="checkbox"> label
</label>
```

Target inner elements: label (the container), input[type="checkbox"]

---

UI_DROPDOWN

```python
ui.dropdown("id", "label", ["option1", "option2"], css={...}, class_="...")
```

DOM (inside wrapper):

```html
<label>label</label>
<select id="id">
  <option value="option1">option1</option>
  ...
</select>
```

Target inner elements: label, select, option

---

UI_TEXT_AREA

```python
ui.text_area("id", "label", css={...}, class_="...")
```

DOM (inside wrapper):

```html
<label>label</label>
<textarea id="id" readonly>System Idle...</textarea>
```

Target inner elements: label, textarea[readonly]

The textarea is readonly – its content is updated by OS commands, callbacks, or SSE pushes, never by direct user typing.

---

UI_CALLBACK_BUTTON

```python
ui.button_callback("Button Text", "function_name", target_id="...", css={...}, class_="...")
```

· target_id can also be passed as the third positional argument:
    ui.button_callback("Run", "my_callback", "output_area")

DOM (inside wrapper):

```html
<button type="button" data-callback="function_name">Button Text</button>
```

Target: button[data-callback]

When clicked, the frontend calls the Python function function_name (registered in the module).
The function receives the current form state as a dict. It may return:

· A plain string – written into the element whose ID matches the button’s target_id (if any).
· A list of patch dicts – applied to the UI and broadcast to all clients.
· A dict with a "patches" key – same effect.

If target_id is set, that element will receive the immediate output and, for textareas, the value is also persisted in the token tree so it survives UI rebuilds.

---

UI_MATH_COMPUTE

```python
ui.math_compute("target_id", "{a} + {b}", css={...}, class_="...")
```

Does not produce visible DOM.
Instead, whenever any form value changes, the expression is evaluated (placeholders like {id} are replaced with the current value of the input with that id). The result is written into the element with id="target_id".

Example:

```python
ui.input_text("a", "Value A")
ui.input_text("b", "Value B")
ui.math_compute("sum", "{a} + {b}")
```

---

OS_GATEKEEPER

```python
ui.os_command("command string", "Description", "target_id", css={...}, class_="...")
```

DOM (inside wrapper):

```html
<button type="button" data-os-cmd="..." data-os-desc="..." data-os-target="target_id">
  Execute Script Hook
</button>
<label style="margin-top:10px;">System Buffer Output:</label>
<div id="target_id" class="terminal">Console idle.</div>
```

Important: The command is executed synchronously (the UI freezes until it finishes).
The user must approve execution in a modal first. After approval, the result replaces the content of the #target_id terminal.

Target inner elements:

· button[data-os-cmd] – the execute button
· label – the “System Buffer Output” label
· .terminal – the output display div

---

UI_TABLE

```python
ui.table(["Header1", "Header2"], [["cell1", "cell2"], ...], target_id="...", css={...}, class_="...")
```

· target_id (optional) lets you dynamically patch rows using the table’s ID.
· css and class_ apply to the component wrapper, not directly to the <table>.

DOM (inside wrapper):

```html
<table>
  <thead>
    <tr><th>Header1</th><th>Header2</th></tr>
  </thead>
  <tbody>
    <tr><td>cell1</td><td>cell2</td></tr>
    ...
  </tbody>
</table>
```

If headers and rows are both empty, a <p>No data available.</p> is shown.

Target inner elements: table, thead, tbody, th, td, tr

---

UI_ROOT_CSS

```python
ui.root_css({"--bg": "#fff", "--accent": "red"})
```

No DOM produced.
Overrides the CSS custom properties on :root immediately.
Use this at the top of your script before any UI components.

---

Layout tokens

LAYOUT_ROW_START / LAYOUT_ROW_END

```python
ui.row_start(css={...}, class_="...")
# ... components ...
ui.row_end()
```

Creates a flex row: <div class="ui-row">.
css and class_ are applied to this row.

---

Structural tokens (Pages & Tabs)

These create the navigation structure but no inline styles.
They do not accept css or class_. Style them via a custom stylesheet.

Token Python call DOM / role
PAGE_START ui.page_start("Page Name") Creates a <div class="page-content" id="page-..."> and a <button class="page-nav-btn">
PAGE_END ui.page_end() Closes the current page
TAB_GROUP_START ui.tab_group_start() Opens a tab group container
TAB_START ui.tab_start("Tab Name") Creates a <button class="tab-btn"> and a <div class="tab-content" id="tab-...">
TAB_END ui.tab_end() Closes the current tab
TAB_GROUP_END ui.tab_group_end() Closes the tab group

Example custom styles:

```css
.page-nav-btn.active { background: var(--accent); }
.tab-btn.active { border-bottom: 2px solid var(--accent); }
```

---

Section tokens (hideable blocks)

Sections group UI elements that can be shown / hidden without losing their form state.

```python
ui.section_start("section_id", visible=True, css={...}, class_="...")
# ... components ...
ui.section_end()
```

DOM: <div class="section" id="section-section_id"> wraps the content.
If visible=False, the div gets style="display: none".

Dynamic toggle via callback:
Return a patch list that targets the section by its section_id (no need for a token index):

```python
def my_callback(form):
    return [{"action": "toggle_section", "section_id": "advanced_section", "visible": True}]
```

---

Dynamic token patches (from callback functions)

Callbacks can return patches to modify the UI without a full page reload. Patches are applied server‑side and broadcast via SSE, so all connected clients see the change.

Targeting a token

Every patch may include either target_id (string) or token_index (integer).
target_id is the preferred, stable way. The token_index approach is deprecated and may be removed in future versions.

Available patch actions

Action Affected token(s) Extra fields
set_text UI_TEXT_AREA (→ value), UI_TITLE, UI_CALLBACK_BUTTON (→ text) value (str)
set_label any with a label value (str)
set_css any value (dict)
set_class any value (str)
insert_table_row UI_TABLE row (list)
set_table_rows UI_TABLE rows (list of lists)
set_options UI_DROPDOWN options (list)
toggle_section SECTION_START section_id (str), visible (bool)

Example: Append a row to a table identified by target_id="log_table":

```python
def update_log(form):
    return [
        {"action": "insert_table_row", "target_id": "log_table",
         "row": ["12:00", form.get("action"), "OK"]}
    ]
```

---

Quick styling examples (using --custom-css)

Custom table:

```css
.my-table table {
    border: 2px solid var(--accent);
}
.my-table th {
    background: var(--surface);
    text-transform: uppercase;
}
```

Custom OS command block:

```css
.my-os button[data-os-cmd] {
    background: var(--accent);
    font-size: 1.1rem;
}
.my-os .terminal {
    background: #000;
    color: #0f0;
    font-family: monospace;
}
```

Custom text input:

```css
.my-input input[type="text"] {
    border-left: 4px solid var(--accent);
    padding-left: 1rem;
}
```

---

Notes

· All visual tokens that produce a wrapper (except titles and rows) share the base class component. Style them globally with .component { ... }.
· The css argument does not cascade to inner elements. Use class_ + a custom stylesheet for inner styling.
· Token indexes are deprecated – use target_id wherever possible.
· The /tokens endpoint shows the current token list; this is the sequence the parser builds from your ui.* calls.
· Section start/end tokens are part of the token list but don’t produce visible widgets (only the wrapper div).
· All callback functions receive the current form state as a dict. They must be defined at the module level.
· OS commands run synchronously and require user confirmation in the gatekeeper modal. The server uses shlex.split() to parse the command string safely (no shell injection).