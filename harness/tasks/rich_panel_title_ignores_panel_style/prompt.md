# Panel title and subtitle render without the panel's background style

`rich.panel.Panel(..., style="on blue", title="hi")` should render `hi` on a
blue background, just like the panel body. Currently the title row gets only
the border style applied; the panel's `style` (which carries the background)
is dropped on the title and subtitle. Visually: title text shows up on the
terminal default background instead of the panel background.

Fix `rich/panel.py` so the title and subtitle are rendered with the panel's
style merged with the border style (border style takes precedence for color,
but the panel's background should still apply).
