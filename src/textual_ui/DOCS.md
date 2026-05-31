# Textual Reference

> Textual is a Python framework for building cross-platform user interfaces that run in the terminal *or* a web browser.

**Docs:** https://textual.textualize.io/
**Repo:** https://github.com/Textualize/textual
**PyPI:** https://pypi.org/project/textual/

---

## Core Pattern

```python
from textual.app import App, ComposeResult
from textual.widgets import Static

class MyApp(App):
    def compose(self) -> ComposeResult:
        yield Static("Hello, World!")

if __name__ == "__main__":
    MyApp().run()
```

Subclass `App`, implement `compose()`, call `run()`. Everything else is built on this.

---

## Key Concepts

| Concept | Description |
|---|---|
| `App` | Top-level application class. Manages screens, keybindings, CSS, lifecycle. |
| `Screen` | A full-screen container. Apps have a stack of screens; only the top is active. |
| `Widget` | A rectangular UI component. Many built-in; easy to create custom ones. |
| `ComposeResult` | Return type of `compose()` — yield widgets from a generator. |
| `CSS` | Textual has its own CSS dialect (`.tcss` files) for layout and styling. |
| `Actions` | Methods prefixed with `action_` callable from keybindings and `@click` links. |
| `Messages` | Widgets communicate via message classes (e.g. `Button.Pressed`). |
| `Reactive` | Attributes that automatically trigger re-renders when changed. |
| `Pilot` | Test helper that simulates user interaction in headless mode. |

---

## App Lifecycle

1. `__init__` — construct app
2. `compose()` — yield initial widgets
3. `on_mount()` — called after compose, safe to query widgets
4. `on_ready()` — called after mount, safe to run timers
5. `run()` — enter application mode (blocking)
6. `exit()` — exit application mode

---

## Built-in Widgets (selection)

| Widget | Purpose |
|---|---|
| `Static` | Renders static or dynamically updated text with markup |
| `Label` | Simple text label |
| `Button` | Clickable button with variants (`primary`, `error`, `success`, `warning`) |
| `Input` | Text input field |
| `TextArea` | Multi-line text editor |
| `Digits` | Digital clock-style display |
| `DataTable` | Sortable, scrollable data table |
| `Tree` | Hierarchical tree control |
| `ListView` | Scrollable list of items |
| `OptionList` | List of selectable options |
| `RichLog` | Scrolling log viewer (Rich renderables) |
| `Markdown` | Renders Markdown content |
| `ProgressBar` | Indeterminate or determinate progress |
| `Header` / `Footer` | Top/bottom bars with keybinding hints |
| `Placeholder` | Placeholder for layout prototyping |
| `LoadingIndicator` | Spinner for async operations |

Full gallery: https://textual.textualize.io/widget_gallery/

---

## Layout Containers

| Container | CSS | Behaviour |
|---|---|---|
| `Vertical` | `layout: vertical;` | Stacks children top-to-bottom |
| `Horizontal` | `layout: horizontal;` | Arranges children left-to-right |
| `Grid` | `layout: grid;` | Grid with `grid-size`, `grid-columns`, `grid-rows` |
| `ScrollableContainer` | `overflow-y: auto;` | Vertically scrollable |
| `Center` (middle) | `align: center middle;` | Centers content on screen |

---

## Key CSS Properties

| Property | Example | Notes |
|---|---|---|
| `layout` | `grid`, `horizontal`, `vertical` | Container layout mode |
| `align` | `center middle` | Align children within container |
| `width` / `height` | `50%`, `20`, `auto`, `1fr` | Dimensions (cells, %, fr, auto) |
| `min-width` / `max-width` | `30`, `100%` | Clamp dimensions |
| `margin` | `1 2` | Outside spacing (top/bottom left/right) |
| `padding` | `1 2` | Inside spacing |
| `border` | `solid red`, `round white`, `tall $primary` | Border style, color, type |
| `background` | `$surface`, `blue`, `rgba(0,0,0,0.5)` | Background color (supports alpha) |
| `color` | `$text`, `$text-muted` | Foreground text color |
| `text-style` | `bold`, `italic`, `underline`, `reverse` | Text decoration |
| `content-align` | `center middle`, `left top` | Alignment of content within widget |
| `display` | `none`, `block` | Show/hide widgets |
| `visibility` | `hidden`, `visible` | Hide but keep layout space |
| `opacity` | `0.5` | Transparency (0-1) |
| `offset` | `3 1` | Shift position (x y) |
| `overflow` | `auto`, `hidden`, `scroll` | Scroll behaviour |
| `grid-size` | `3 2` | Grid columns rows |
| `grid-gutter` | `1 2` | Grid cell spacing |
| `column-span` | `2` | Grid cell spanning |
| `dock` | `top`, `bottom`, `left`, `right` | Dock to edge (for headers/footers) |
| `tint` | `red 20%` | Overlay tint on entire widget |

---

## Variables (Theme-aware)

| Variable | Source | Use |
|---|---|---|
| `$primary` | Theme | Branding color |
| `$secondary` | Theme | Alternative brand |
| `$accent` | Theme | Draw attention |
| `$background` | Theme | Screen background |
| `$surface` | Theme | Widget background |
| `$panel` | Theme | Panel/separator |
| `$foreground` | Theme | Default text |
| `$text` | Computed | Legible text on any bg |
| `$text-muted` | Computed | Low-importance text |
| `$text-disabled` | Computed | Disabled text |
| `$border` | Computed | Focused widget border |
| `$border-blurred` | Computed | Unfocused widget border |
| `$boost` | Theme | Alpha overlay |
| `$warning` / `$error` / `$success` | Theme | Semantic colors |
| `$scrollbar` | Theme | Scrollbar color |

All colors have `-lighten-1/2/3` and `-darken-1/2/3` shades, plus `-muted` variants.

---

## Actions & Bindings

```python
class MyApp(App):
    BINDINGS = [
        ("q", "quit", "Quit"),
        ("ctrl+p", "show_palette", "Command Palette"),
    ]

    def action_quit(self) -> None: ...
    def action_show_palette(self) -> None: ...
```

Namespaces: `app.`, `screen.`, `focused.` prefix actions.

`@click` links in markup: `"[@click=app.bell]Click me[/]"`.

Dynamic action guards: `check_action(action, params) -> bool | None` to enable/disable/hide keys.

---

## Screens

```python
from textual.screen import Screen

class MyScreen(Screen):
    def compose(self) -> ComposeResult: ...

class MyApp(App):
    SCREENS = {"my": MyScreen}
    BINDINGS = [("m", "push_screen('my')", "My Screen")]
```

Stack API: `push_screen`, `pop_screen`, `switch_screen`, `install_screen`.

Modal screens: `ModalScreen` subclass blocks parent bindings + dims background.

---

## Reactive Attributes

```python
from textual.reactive import reactive

class MyWidget(Static):
    count = reactive(0)  # triggers re-render on change
    name = reactive("", always_update=True)  # re-render even if same value
```

Reactive with bindings refresh: `reactive(0, bindings=True)`.

---

## Testing

```python
async def test_my_app():
    app = MyApp()
    async with app.run_test(size=(80, 24)) as pilot:
        await pilot.press("q")
        await pilot.click("#my-button")
        await pilot.pause()
        assert app.screen.styles.background == Color.parse("red")
```

| Pilot Method | Purpose |
|---|---|
| `press(*keys)` | Simulate key presses |
| `click(selector, offset, times, control, shift, meta)` | Simulate mouse click |
| `pause(delay)` | Wait for pending messages |
| `wait_for_screen(screen)` | Wait for screen to become active |

Snapshot testing: `pytest-textual-snapshot` plugin generates SVG comparisons.

---

## Themes

```python
from textual.theme import Theme

my_theme = Theme(
    name="my",
    primary="#88C0D0",
    secondary="#81A1C1",
    dark=True,
)
```

Register: `app.register_theme(my_theme)`, set: `app.theme = "my"`.

Built-in themes: `textual-dark` (default), `textual-light`, `nord`, `gruvbox`, `dracula`, `monokai`, `catppuccin`, `tokyo-night`, `solarized-light`.

---

## Known Pitfalls

1. **Async compose**: `compose()` should not be async — use `on_mount()` for async setup after widgets are ready.
2. **Mount timing**: Widgets aren't queryable inside `compose()`. Use `on_mount()` or `on_ready()`.
3. **CSS path**: relative to the file where `App` is defined, not the working directory.
4. **Inline mode**: `app.run(inline=True)` runs below the prompt (no fullscreen). Not available on Windows.
5. **Browser serving**: `textual serve my_app.py` or `textual-web` for remote access.
6. **Development tools**: `textual-dev` package provides devtools console, `textual run --dev` for live CSS editing.
7. **Testing requires async**: `run_test()` is an async context manager — tests must be `async def`.
8. **`pip install textual-dev`** separate from `textual` — provides `textual keys`, `textual diagnose`, `textual run --dev`.

---

## Links

- [API Reference](https://textual.textualize.io/api/)
- [Widget Gallery](https://textual.textualize.io/widget_gallery/)
- [CSS Reference](https://textual.textualize.io/guide/CSS/)
- [Textual Web](https://github.com/Textualize/textual-web) — serve apps remotely
- [Textual Demo](https://github.com/textualize/textual-demo) — example app via `uvx textual-demo`
- [Discord](https://discord.gg/Enf6Z3qhVr)
