import re
from contextlib import asynccontextmanager
from typing import TYPE_CHECKING, Any, Sequence, override

from spaceport.op import browser, gui
from spaceport.subject import TSL, CardinalityError, Handle, Subject, TSLError
from spaceport.subject.factory import ManagedSubject, SubjectFactory, managed_subject

if TYPE_CHECKING:
    from playwright.async_api import BrowserContext, Locator, Page

_TSL_FUNCTION_PATTERN = re.compile(r"(\w+)(?:\[(.*)\])?")
_TSL_CONDITION_PATTERN = re.compile(r'(\w+)\s+(is|like)\s+(["\'])((?:(?!\3).)*)\3')


def _parse_tsl_part(part: str) -> tuple[str, dict[str, tuple[str, str]]]:
    """Parse a single part of a GUI TSL path into function and conditions"""
    function_match = _TSL_FUNCTION_PATTERN.match(part)
    if not function_match:
        raise ValueError(f"Invalid function format: {part}")

    function = function_match.group(1)
    conditions_str = function_match.group(2) or ""
    conditions: dict[str, tuple[str, str]] = {}

    # Parse conditions
    for condition in conditions_str.split(";"):
        condition = condition.strip()
        if not condition:
            continue

        match = _TSL_CONDITION_PATTERN.match(condition)
        if match:
            key, operator, _, value = match.groups()
            conditions[key] = (operator, value)

    return function, conditions


def _generate_part_selector(
    function: str, conditions: dict[str, tuple[str, str]]
) -> str:
    """Generate a Playwright selector for one part of the TSL path"""
    # Comprehensive mapping of TSL functions to HTML elements
    function_map = {
        # Interactive Elements
        "button": ["button", "input[type='button']", "input[type='submit']"],
        "link": ["a"],
        "input": ["input", "textarea"],
        "checkbox": ["input[type='checkbox']"],
        "radio": ["input[type='radio']"],
        "textbox": ["input[type='text']", "textarea"],
        "searchbox": ["input[type='search']"],
        "spinbutton": ["input[type='number']"],
        "slider": ["input[type='range']"],
        "select": ["select"],
        "option": ["option"],
        # Content Elements
        "article": ["article"],
        "banner": ["banner"],
        "complementary": ["complementary"],
        "contentinfo": ["contentinfo"],
        "dialog": ["dialog"],
        "document": ["document"],
        "feed": ["feed"],
        "figure": ["figure"],
        "grid": ["grid"],
        "gridcell": ["gridcell"],
        "group": ["group"],
        "main": ["main"],
        "menu": ["menu"],
        "menubar": ["menubar"],
        "navigation": ["navigation", "nav"],
        "region": ["region"],
        "row": ["row"],
        "rowgroup": ["rowgroup"],
        "rowheader": ["rowheader"],
        "scrollbar": ["scrollbar"],
        "search": ["search"],
        "section": ["section"],
        "heading": ["h1", "h2", "h3", "h4", "h5", "h6"],
        "img": ["img"],
        "list": ["ul", "ol", "li"],
        "table": ["table"],
        "form": ["form"],
        # Generic Elements
        "div": ["div"],
        "span": ["span"],
        "paragraph": ["p"],
        "text": ["span", "p", "div", "label"],
    }

    try:
        base_selectors = function_map[function]
    except KeyError:
        raise TSLError(f"Invalid function: {function}")

    condition_parts: list[str] = []
    for key, (operator, value) in conditions.items():
        if key == "role":
            if operator == "is":
                condition_parts.append(f'[role="{value}" i]')
            else:
                condition_parts.append(f'[role*="{value}" i]')
        elif key == "label":
            if operator == "is":
                condition_parts.append(f'[aria-label="{value}" i]')
                # Regular text content for non-input elements
                if function not in {
                    "input",
                    "textbox",
                    "searchbox",
                    "combobox",
                    "spinbutton",
                }:
                    # Add support for both direct text and text within label elements
                    condition_parts.append(f':text-is("{value}")')
                    condition_parts.append(f':has(label:text-is("{value}"))')
                    condition_parts.append(f':has(:text-is("{value}"))')
                else:
                    # For form controls, look for associated labels
                    condition_parts.append(
                        f':has(+ label:text-is("{value}"))'
                    )  # Label after input
                    condition_parts.append(
                        f':has(label:text-is("{value}") + *)'
                    )  # Label before input
            else:  # like
                condition_parts.append(f'[aria-label*="{value}" i]')
                if function not in {
                    "input",
                    "textbox",
                    "searchbox",
                    "combobox",
                    "spinbutton",
                }:
                    # Add support for both direct text and text within label elements
                    condition_parts.append(f':text("{value}")')
                    condition_parts.append(f':has(label:text("{value}"))')
                    condition_parts.append(f':has(:text("{value}"))')
                else:
                    # For form controls, look for associated labels
                    condition_parts.append(
                        f':has(+ label:text("{value}"))'
                    )  # Label after input
                    condition_parts.append(
                        f':has(label:has-text("{value}") + *)'
                    )  # Label before input
        else:
            # Handle other attributes
            if operator == "is":
                condition_parts.append(f'[{key}="{value}" i]')
            else:  # like
                condition_parts.append(f'[{key}*="{value}" i]')

    # Combine base selectors with conditions
    if not condition_parts:
        return ", ".join(base_selectors)
    selectors: list[str] = [
        f"{base}{condition}" for base in base_selectors for condition in condition_parts
    ]
    return ", ".join(selectors)


def _tsl_to_playwright(tsl: TSL, page: "Page") -> "Locator":
    # Process each part of the path sequentially
    part_selectors: list[str] = []
    for part in tsl.body_parts():
        function, conditions = _parse_tsl_part(part)
        selector = _generate_part_selector(function, conditions)
        part_selectors.append(selector)

    # Join all parts with Playwright's descendant combinator
    selector = " >> ".join(part_selectors)

    match tsl.cardinality:
        case "all":
            return page.locator(selector)
        case "unique" | "one" | "":
            return page.locator(selector).nth(0)
        case _:
            raise CardinalityError(tsl.cardinality, actual_count=1)


class BrowserPage(Handle, browser.Navigate, gui.MouseClick, gui.TypeText, gui.ReadText):
    def __init__(self, pw_page: "Page", tsl: TSL) -> None:
        self.pw_page = pw_page
        self.tsl = tsl

    @override
    @asynccontextmanager
    async def bind(self):
        if self.tsl.body:
            self.pw_locator = _tsl_to_playwright(self.tsl, self.pw_page)
        yield

    @override
    async def size(self) -> int:
        if self.pw_locator:
            await self.pw_locator.click()
            return await self.pw_locator.count()
        return 0

    @override
    def is_collection(self) -> bool:
        return self.tsl.cardinality == "all"

    @override
    async def goto_url(self, url: str) -> None:
        await self.pw_page.goto(url)

    @override
    def get_current_url(self) -> str:
        return self.pw_page.url

    @override
    async def go_back(self) -> None:
        await self.pw_page.go_back()

    @override
    async def go_forward(self) -> None:
        await self.pw_page.go_forward()

    @override
    async def mouse_move(self) -> None:
        await self.pw_locator.hover()

    @override
    async def mouse_move_coords(self, x: int, y: int) -> None:
        await self.pw_page.mouse.move(x, y)

    @override
    async def mouse_down(self, button: str = "left") -> None:
        match button:
            case "left" | "middle" | "right":
                await self.pw_page.mouse.down(button=button)
            case _:
                raise ValueError(f"Invalid mouse button: {button}")

    @override
    async def mouse_up(self, button: str = "left") -> None:
        match button:
            case "left" | "middle" | "right":
                await self.pw_page.mouse.up(button=button)
            case _:
                raise ValueError(f"Invalid mouse button: {button}")

    @override
    async def keydown(self, keys: Sequence[str]) -> None:
        await self.pw_page.keyboard.down("+".join(keys))

    @override
    async def keyup(self, keys: Sequence[str]) -> None:
        await self.pw_page.keyboard.up("+".join(keys))

    @override
    async def read_text(self) -> str:
        return await self.pw_locator.inner_text()

    @override
    async def type_text(self, text: str) -> None:
        await self.pw_locator.type(text)


class _Browser(Subject[BrowserPage]):
    """A browser subject that uses Playwright to interact with UI components.

    Acceptable TSL headerss: ``web``, ``browser``.
    """

    def __init__(self, context: "BrowserContext"):
        self.context = context
        self.page = None

    @override
    async def search(self, tsl: TSL, op_name: str) -> BrowserPage:
        if not self.page:
            self.page = await self.context.new_page()
        match tsl.header:
            case "web" | "browser" | "gui":
                return BrowserPage(self.page, tsl)
            case _:
                raise TSLError(f"Invalid TSL header: {tsl.header}")


Browser = managed_subject(_Browser)


class BrowserFactory(SubjectFactory[BrowserPage]):
    """A browser subject based on Playwright."""

    async_pw: Any = None

    def __init__(self):
        if self.async_pw is None:
            import importlib

            try:
                self.__class__.async_pw = staticmethod(
                    importlib.import_module("playwright.async_api").async_playwright
                )
            except ImportError:
                raise ImportError("Playwright is not installed")

        self.pw = None
        self.pw_browser = None
        self.pw_context = None

    @override
    async def create(self, **kwargs: Any) -> ManagedSubject[BrowserPage]:
        """Create a browser subject.

        No arguments are accepted.
        """
        if not self.pw:
            self.pw = await self.async_pw().start()
        if not self.pw_browser:
            self.pw_browser = await self.pw.chromium.launch()
        if not self.pw_context:
            self.pw_context = await self.pw_browser.new_context()
        return Browser([], context=self.pw_context)

    @override
    async def destroy(self) -> None:
        if self.pw:
            await self.pw.stop()
