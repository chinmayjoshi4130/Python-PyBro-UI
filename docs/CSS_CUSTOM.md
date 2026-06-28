---

Pybro gives you multiple layers of CSS control, ranging from quick one‑line overrides to a full custom stylesheet. You can also change the UI dynamically at runtime via token patches. Here’s exactly what you can do, and what the limits are.

---

🎨 CSS customisation – from simple to advanced

1. Global theme variables

The fastest way to change the look of the entire dashboard.
Use ui.root_css({...}) in your Python script to override the built‑in CSS custom properties.

```python
ui.root_css({
    "--bg": "#ffffff",
    "--accent": "#ff6600",
    "--radius": "4px",
})
```

This affects every component that uses these variables – colours, shadows, border radius, etc.

Default variables you can change:

Variable What it controls
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

Every visual token accepts a css argument – a dictionary of CSS property/value pairs applied directly to that component’s wrapper <div> (or the <h1> for titles).

```python
ui.input_text("host", "Target Host",
              css={"border": "2px solid var(--accent)", "borderRadius": "6px"})
ui.button_callback("Submit", "my_func",
                   css={"background": "linear-gradient(45deg, #e94560, #0f3460)"})
```

This gives you per‑component control without any external CSS file.

---

3. CSS classes (with a custom stylesheet)

Every token also accepts a class_ argument – a CSS class name that you can define in an external stylesheet.

```python
ui.checkbox("verbose", "Verbose", class_="my-custom-toggle")
```

Then, in your custom CSS file (loaded with --custom-css), you define:

```css
.my-custom-toggle input {
    accent-color: var(--accent);
}
```

This approach keeps your Python script clean and your styles reusable. You can also target inner elements (like the terminal inside an OS command block, or table cells) using wrapper classes and descendant selectors – see the Token Reference for the exact DOM structure of each token.

---

4. Full custom stylesheet (--custom-css)

For complete visual control, pass a path to a .css file with the --custom-css flag:

```bash
pybro my_tool.py --custom-css ./my_theme.css
```

The server injects a <link rel="stylesheet" href="/custom.css"> after the built‑in CSS, so your rules override the defaults automatically.

You can change any CSS rule – layout, fonts, animations, even the navigation bar.
Example my_theme.css:

```css
/* Make the page nav vertical */
#page-nav {
    flex-direction: column;
    width: 200px;
    border-right: 2px solid var(--border);
}
/* Rounded tabs */
.tab-btn {
    border-radius: 8px 8px 0 0;
}
/* Custom button hover */
button:hover {
    filter: brightness(1.2);
}
```

Limitations:

· You cannot change the HTML structure (e.g., add new elements) through CSS alone.
· The built‑in CSS still exists; you are overriding it, not replacing it.
· If you want a drastically different layout, you might need to also edit index.html (not recommended for normal use).

---

🔧 Dynamic CSS changes (runtime)

Through the callback token‑patch system, you can alter a widget’s css or class on the fly:

```python
def update_theme(form):
    return [
        {"action": "set_css", "token_index": 5, "value": {"border": "2px solid red"}},
        {"action": "set_class", "token_index": 6, "value": "urgent"},
    ]
```

The UI re‑renders instantly, applying the new styles without a page reload.

---

🧱 UI structure control – what you can build

You have full control over the layout and content via tokens:

· Pages – separate, navigable screens with ui.page_start("Name") / ui.page_end().
· Tabs – local tab bars inside a page, using ui.tab_group_start() / ui.tab_end() and ui.tab_start("Name") / ui.tab_end().
· Sections – hideable blocks of tokens defined with ui.section_start("id", visible=True/False) and ui.section_end(). These preserve their internal form state when hidden because only display is toggled. You can show/hide them dynamically with the set_section_visible patch action.
· Rows – horizontal flex rows with ui.row_start / ui.row_end.
· Widgets – the complete catalogue of inputs, outputs, tables, math blocks, and buttons.
· Dynamic content – tables can be updated, dropdown options changed, titles rewritten, sections shown/hidden, all from Python callbacks.

You cannot currently add custom HTML elements or JavaScript (that’s planned, but with security gates). The available widget set covers most automation needs.

---

Summary of control levels

What you want to change How to do it
Colours, radii, shadows globally ui.root_css({...})
One widget’s style inline css={"property":"value"}
Reusable style patterns (including inner elements) class_="my-class" + --custom-css
Entire theme / layout overhaul --custom-css your_file.css
Change styles at runtime Token patches (set_css, set_class)
Change UI content at runtime Token patches (set_text, insert_table_row, set_options, set_section_visible, etc.)
Add custom HTML/JS Not yet available (planned)
Show/hide predefined blocks without destroying state ui.section_start / ui.section_end + patches

In practice, most dashboards need only root_css and a few inline css tweaks. If you need a branded look or specific layout, a custom stylesheet gives you nearly limitless visual freedom, and sections let you build interactive, conditional interfaces.