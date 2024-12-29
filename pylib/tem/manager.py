import asyncio
from typing import Any, Callable, Optional

from jinja2 import Environment, FunctionLoader

from .fileloader import FileLoader


class TemplateManager:
    """The manager of templates in a directory."""

    def __init__(self, template_dir: str) -> None:
        self.template_dir = template_dir
        self.file_loader = FileLoader(template_dir)
        self.not_uptodate: set[tuple[str, str]] = set()

        self.jinja_env = Environment(
            loader=FunctionLoader(self._jinja_function_loader),
            extensions=["jinja2.ext.do"],
            autoescape=False,
            trim_blocks=True,
            keep_trailing_newline=True,
        )

        self._watching_task: asyncio.Task[Any] | None = None

    def watch_for_update(self, *, interval: int) -> None:
        async def __reload_templates() -> None:
            # Need a new instance in a new thread
            while True:
                await asyncio.sleep(interval)
                await self.load_templates_from_files()

        self._watching_task = asyncio.create_task(__reload_templates())

    async def load_templates_from_files(self) -> None:
        self.not_uptodate.update(await self.file_loader.load(recursive=True))

    def _jinja_function_loader(
        self,
        qualified_name: str,
    ) -> tuple[str, Optional[str], Optional[Callable[[], bool]]]:
        module, name = qualified_name.split("$")
        template = self.file_loader.get_template(module, name)
        self.not_uptodate.discard((module, name))

        def __uptodate() -> bool:
            return (module, name) not in self.not_uptodate

        return template, None, __uptodate

    def render(self, module: str, name: str, /, **context: Any) -> str:
        template = self.jinja_env.get_template(f"{module}${name}")
        return template.render(**context)

    def for_module(self, module: str) -> "ModuleTemplates":
        """Get the templates for a specific module.

        The returned object is callable. When called with a template name, it renders
        the template by its name and returns the rendered string.
        """

        return ModuleTemplates(self, module)


class ModuleTemplates:
    """Templates of a specific module.

    An instance of this class is callable. When called with a template name, it renders
    the template by its name and returns the rendered string. Keyword arguments passed
    to the call are forwarded to the template as variables.
    """

    def __init__(self, manager: TemplateManager, module: str) -> None:
        self.manager = manager
        self.module = module

    def __call__(self, name: str, /, **context: Any) -> str:
        return self.manager.render(self.module, name, **context)

    def get_or_default(self, name: str, default: str, /, **context: Any) -> str:
        try:
            return self(name, **context)
        except Exception:
            return default
