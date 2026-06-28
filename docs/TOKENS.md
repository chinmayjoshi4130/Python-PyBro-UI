---

# Pybro Token Reference

This document describes every UI token produced by the Pybro parser – its Python call, the HTML it generates, and the CSS classes / inner elements you can target with a custom stylesheet.

Use this reference together with the class_ argument on tokens and the --custom-css flag on the server to completely restyle your dashboard.

---

How styling works

· css argument – a dict of property: value pairs applied as inline styles on the token’s outermost element.
· class_ argument – a CSS class name added to the outermost element.
· --custom-css file – a stylesheet loaded after the built‑in CSS. Use descendant selectors to style inner elements.

The outermost element for most tokens is a <div class="component">. For titles it is the <h1> itself; for layout rows it is a <div class="ui-row">; for sections it is a <div class="section">.

---

Token catalogue

UI_TITLE

```
ui.title("text")
```

DOM:
<h1>text</h1>

· css and class_ are applied directly to the <h1>.
· No inner elements.

---

UI_INPUT

```
ui.input_text("id", "label")
```

DOM (inside wrapper):

```html
<label>label</label>
<input id="id" type="text">
```

Target inner elements:

· label
· input[type="text"]

---

UI_CHECKBOX

```
ui.checkbox("id", "label")
```

DOM (inside wrapper):

```html
<label style="display:flex; align-items:center; gap:8px;">
  <input id="id" type="checkbox"> label
</label>
```

Target inner elements:

· label (the container)
· input[type="checkbox"]

---

UI_DROPDOWN

```
ui.dropdown("id", "label", ["option1", "option2"])
```

DOM (inside wrapper):

```html
<label>label</label>
<select id="id">
  <option value="option1">option1</option>
  ...
</select>
```

Target inner elements:

· label
· select
· option

---

UI_TEXT_AREA

```
ui.text_area("id", "label")
```

DOM (inside wrapper):

```html
<label>label</label>
<textarea id="id" readonly>System Idle...</textarea>
```

Target inner elements:

· label
· textarea[readonly]

---

UI_CALLBACK_BUTTON

```
ui.button_callback("Button Text", "function_name", target_id="...")
```

DOM (inside wrapper):

```html
<button type="button" data-callback="function_name">Button Text</button>
```

· Target button[data-callback] to style the button.

---

UI_MATH_COMPUTE

```
ui.math_compute("target_id", "{a} + {b}")
```

Does not produce visible DOM. The formula is evaluated client‑side and the result is written into the element with id="target_id". No wrapper, no inner elements.

---

OS_GATEKEEPER

```
ui.os_command("command string", "Description", "target_id")
```

DOM (inside wrapper):

```html
<button type="button" data-os-cmd="..." data-os-desc="..." data-os-target="target_id">
  Execute Script Hook
</button>
<label style="margin-top:10px;">System Buffer Output:</label>
<div id="target_id" class="terminal">Console idle.</div>
```

· The command runs synchronously (blocking); the output appears in the terminal after completion.
· Target inner elements:
  · button[data-os-cmd] – the execute button
  · label – the “System Buffer Output” label
  · .terminal – the output display div

---

UI_TABLE

```
ui.table(["Header1", "Header2"], [["cell1", "cell2"], ...])
```

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

If headers and rows are empty, a <p>No data available.</p> is shown instead.

Target inner elements:

· table
· thead
· tbody
· th
· td
· tr

---

UI_ROOT_CSS

```
ui.root_css({"--bg": "#fff", "--accent": "red"})
```

Does not produce DOM. Overrides CSS custom properties on :root. The variables are applied directly to <html>.

---

Layout tokens

LAYOUT_ROW_START / LAYOUT_ROW_END

```
ui.row_start()
ui.row_end()
```

DOM:
A <div class="ui-row"> wraps the content between start and end.
css and class_ are applied to this row <div>. Its children are normal component wrappers.

---

Structural tokens (pages / tabs)

These produce no inline styles but create the navigation structure.

Token Python DOM role
PAGE_START ui.page_start("Page Name") Creates a page container <div class="page-content" id="page-..."> and a navigation button <button class="page-nav-btn">. No css/class_ argument.
PAGE_END ui.page_end() Closes the current page.
TAB_GROUP_START ui.tab_group_start() Opens a tab group container.
TAB_START ui.tab_start("Tab Name") Creates a tab button <button class="tab-btn"> and a tab content <div class="tab-content" id="tab-...">.
TAB_END ui.tab_end() Closes the current tab.
TAB_GROUP_END ui.tab_group_end() Closes the tab group.

These tokens have no css or class_ arguments. Their visual style can only be changed via a custom stylesheet, e.g.:

```css
.page-nav-btn { ... }
.tab-btn { ... }
```

---

Section tokens (hideable blocks)

Sections let you pre‑define blocks of UI that can be shown/hidden at runtime without destroying their internal form state. They are simply hidden via display: none.

Token Python call Description
SECTION_START ui.section_start("section_id", visible=True) Starts a new section with a unique id and an optional visible keyword argument (default True). The token also accepts css and class_ for the wrapper.
SECTION_END ui.section_end() Ends the current section.

DOM:
A <div class="section" id="section-section_id"> wraps all tokens between start and end.
If visible is False, the section gets style="display: none".

Dynamic toggling:
Use the set_section_visible patch action to toggle visibility from a callback:

```python
return [{"action": "set_section_visible", "token_index": 5, "visible": True}]
```

---

Dynamic token patches

Callbacks can return a list of patch dictionaries to modify tokens on the fly. The server applies the changes to the compiled token list and re‑renders the UI.

Action Effect Extra Fields
set_text Changes UI_TITLE.text or UI_CALLBACK_BUTTON.text value (str)
set_label Changes a label value (str)
set_css Replaces inline CSS value (dict)
set_class Replaces CSS class value (str)
insert_table_row Appends a row to a UI_TABLE row (list)
set_table_rows Replaces all rows rows (list of lists)
set_options Replaces dropdown options options (list)
set_section_visible Shows/hides a section (SECTION_START) visible (bool)

---

Quick styling examples (using --custom-css)

Assume you add class_="my-section" to a few tokens.

Custom table:

```css
.my-section table {
    border: 2px solid var(--accent);
}
.my-section th {
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

Hide a section initially and style it:

```css
.my-hidden-section {
    border: 1px dashed var(--border);
    padding: 1rem;
    margin-top: 1rem;
}
```

---

Notes

· All tokens that produce a wrapper (everything except titles, rows, and structural tokens) share the base class component. You can style all widgets globally with .component { ... }.
· The css argument on a token does not cascade to inner elements; it is applied only to the outermost element (the wrapper). Use class_ + a custom stylesheet for inner styling.
· Token indexes (used in dynamic patches) are determined by the order of ui.* calls. Open /tokens in the browser to see the exact sequence.
· Section tokens are part of the token list; their SECTION_START and SECTION_END tokens count toward the index, but they themselves do not produce visible widgets (only the wrapper <div>).