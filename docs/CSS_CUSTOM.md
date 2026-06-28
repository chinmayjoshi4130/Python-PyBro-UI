---

Pybro Styling & Customisation

Pybro gives you multiple layers of CSS control – from quick one‑liners to full custom stylesheets – plus the ability to change the UI at runtime with token patches. Here’s what you can do, and the limits.

---

🎨 CSS customisation – from simple to advanced

1. Global theme variables

Override the built‑in CSS custom properties with ui.root_css({...}).

```python
ui.root_css({
    "--bg": "#ffffff",
    "--accent": "#ff6600",
    "--radius": "4px",
})
```

Variable Controls
--bg Page background
--surface Component card background
--border Border colour
--text Main text colour
--accent Headings, active tab/page indicators
--green Output text (terminals, textareas)
--red Errors, destructive buttons
--radius Border radius of cards and inputs
--shadow Box shadow on cards

You can override all of them, or just a few – the rest keep their defaults.

---

2. Inline styles on individual widgets

Every visual token accepts a css argument – a dictionary of CSS property/value pairs applied directly to that component’s outermost element.

```python
ui.input_text("host", "Target Host",
              css={"border": "2px solid var(--accent)", "borderRadius": "6px"})
ui.button_callback("Submit", "my_func",
                   css={"background": "linear-gradient(45deg, #e94560, #0f3460)"})
```

For sections, the wrapper <div class="section"> gets the styles:

```python
ui.section_start("advanced", visible=True, css={"border": "1px dashed var(--border)"})
```

---

3. CSS classes (with a custom stylesheet)

Every token also accepts a class_ argument – a CSS class name that you can define in an external stylesheet.

```python
ui.checkbox("verbose", "Verbose", class_="my-custom-toggle")
ui.section_start("logs", class_="log-panel")
```

In your custom CSS file (loaded with --custom-css):

```css
.my-custom-toggle input {
    accent-color: var(--accent);
}
.log-panel {
    background: #1a1a2e;
    padding: 1rem;
}
```

You can target inner elements (like the terminal inside an OS command block, or table cells) using wrapper classes and descendant selectors. See the Token Reference for the exact DOM structure of each token.

---

4. Full custom stylesheet (--custom-css)

For complete visual control, pass a path to a .css file:

```bash
pybro my_tool.py --custom-css ./my_theme.css
```

The server injects a <link rel="stylesheet" href="/custom.css"> after the built‑in CSS, so your rules override the defaults automatically.

You can change any CSS rule – layout, fonts, animations, even the navigation bar.

```css
/* Vertical page nav */
#page-nav {
    flex-direction: column;
    width: 200px;
    border-right: 2px solid var(--border);
}
/* Rounded tabs */
.tab-btn {
    border-radius: 8px 8px 0 0;
}
/* Custom section highlight */
.section {
    transition: all 0.3s ease;
}
/* Style all component wrappers globally */
.component {
    backdrop-filter: blur(4px);
}
```

Limitations:

· You cannot change the HTML structure (e.g., add new elements) through CSS alone.
· The built‑in CSS still exists; you are overriding it, not replacing it.
· For radical layout changes, you may need to edit index.html (not recommended for normal use).

---

🔧 Dynamic CSS changes (runtime)

Through the callback token‑patch system, you can alter a widget’s css or class on the fly. The server applies the changes and the UI updates without a page reload.

```python
def update_theme(form):
    return [
        {"action": "set_css", "target_id": "main_title", "value": {"color": "red"}},
        {"action": "set_class", "target_id": "output_area", "value": "urgent"},
    ]
```

Important: Prefer target_id over the deprecated token_index whenever possible.

---

🧱 UI structure control – what you can build

You have full control over the layout and content via tokens.

Pages

```python
ui.page_start("Dashboard")
# ... widgets ...
ui.page_end()
```

· Each page becomes a separate, navigable screen.
· Page nav buttons get the class .page-nav-btn.
· The active page gets .page-content.active.

Tabs

```python
ui.tab_group_start()
  ui.tab_start("Ping")
    # ... widgets ...
  ui.tab_end()
  ui.tab_start("Trace")
    # ...
  ui.tab_end()
ui.tab_group_end()
```

· Tabs create a local tab bar inside a page.
· Tab buttons get .tab-btn; active tab button gets .tab-btn.active.
· Tab content containers get .tab-content.

Sections (hideable blocks)

Sections let you group widgets and show/hide them without destroying their internal form state.

```python
ui.section_start("filters", visible=True, css={"padding": "1rem"}, class_="filter-block")
  ui.checkbox("active_only", "Active only")
  ui.dropdown("sort_by", "Sort by", ["name", "date"])
ui.section_end()
```

Key points:

· The section wrapper is <div class="section" id="section-filters">.
· If visible=False, the wrapper gets style="display: none".
· You can apply css and class_ directly on the section start token – they go on the wrapper.
· To toggle visibility dynamically, use the toggle_section patch action with the section’s id:

```python
return [{"action": "toggle_section", "section_id": "filters", "visible": False}]
```

· No token index needed – the server looks up the SECTION_START node by its section_id.
· Because the DOM is merely hidden, all input values inside the section are preserved.

Rows

```python
ui.row_start()
  ui.input_text("host", "Host")
  ui.button_callback("Ping", "do_ping", target_id="output")
ui.row_end()
```

· Rows are flex containers (<div class="ui-row">) that lay out widgets horizontally.
· They accept css and class_.

Widgets

The complete catalogue includes inputs, checkboxes, dropdowns, text areas, callbacks, math compute blocks, OS gatekeepers, and tables – see the Token Reference for every option.

Dynamic content

Tables can be updated, dropdown options changed, titles rewritten, sections shown/hidden, all from Python callbacks using patches (see the token reference for all action types).

---

Summary of control levels

What you want to change How to do it
Colours, radii, shadows globally ui.root_css({...})
One widget’s style inline css={"property":"value"} on the token
Reusable style patterns (including inner elements) class_="my-class" + --custom-css file
Entire theme / layout overhaul --custom-css your_file.css
Change styles at runtime Token patches: set_css, set_class (use target_id)
Change UI content at runtime Token patches: set_text, insert_table_row, set_options, etc.
Show/hide predefined blocks without losing state ui.section_start / ui.section_end + toggle_section patch (by section_id)
Add custom HTML/JS Not yet available (planned)

In practice, most dashboards need only root_css and a few inline css tweaks. For a branded look or specific layout, a custom stylesheet gives you nearly limitless visual freedom, and sections let you build interactive, conditional interfaces.