import ast
import inspect
from types import ModuleType
from typing import Any, Callable, TypeAliasType

from spaceport.subject import TSL, Handle, Subject

from .errors import (
    TpyAssertionError,
    TpyOperationError,
    TpyRuntimeError,
    TpySubjectError,
)
from .resolver import Resolver


def _filter_locals(
    locals: dict[str, Any] | None,
    *,
    keep_private: bool = False,
) -> dict[str, Any] | None:
    if not locals:
        return locals

    criteria: tuple[Callable[[str, Any], bool], ...] = (
        lambda _k, v: not isinstance(v, (ModuleType, TypeAliasType, type)),
        lambda k, _v: keep_private or not k.startswith("_"),
    )
    return {k: v for k, v in locals.items() if all(c(k, v) for c in criteria)}


def _get_source_lineno_and_locals(
    e: Exception,
) -> tuple[int | None, dict[str, Any] | None]:
    """Try to find the line number in the original script."""
    if e.__traceback__ is None:
        return None, None
    tb = e.__traceback__
    lineno: int | None = None
    locals: dict[str, Any] | None = None
    while tb is not None:
        f_code = tb.tb_frame.f_code
        if f_code.co_filename == "<tpy>":
            lineno = tb.tb_lineno
        if f_code.co_name == "_tpy_exec":
            locals = tb.tb_frame.f_locals
        if lineno is not None and locals is not None:
            return lineno, _filter_locals(locals)
        tb = tb.tb_next
    return lineno, _filter_locals(locals)


class _SubjHolder:
    def __init__(self):
        self._subject: Subject[Any] | None = None

    @property
    def subject(self) -> Subject[Any] | None:
        return self._subject

    @subject.setter
    def subject(self, subject: Subject[Any] | None) -> None:
        self._subject = subject


class _TpyTransformer(ast.NodeTransformer):
    """Transform the AST to replace T invocations.

    This method:
    - Replaces ``T.use()`` with ``_tpy_use_subject()``
    - Replaces ``T.op()`` with ``_tpy_call()``
    - Replaces ``assert x`` with ``if not x: raise AssertionError(f"Cannot assert {x}")``
    """

    def visit_Assert(self, node: ast.Assert) -> Any:
        assertion_text = ast.unparse(node.test)
        # Transform any T.op calls inside the assertion
        node.test = self.visit(node.test)
        return ast.copy_location(
            ast.If(
                test=ast.UnaryOp(op=ast.Not(), operand=node.test),
                body=[
                    ast.Raise(
                        exc=ast.Call(
                            func=ast.Name(id="AssertionError", ctx=ast.Load()),
                            args=[
                                ast.JoinedStr(
                                    values=[
                                        ast.Constant(value="Cannot assert "),
                                        ast.Constant(value=assertion_text),
                                    ]
                                )
                            ],
                            keywords=[],
                        ),
                        cause=None,
                    )
                ],
                orelse=[],
            ),
            node,
        )

    def visit_Call(self, node: ast.Call) -> Any:
        # Transform any nested T.op calls like T.op().strip()
        node.func = self.visit(node.func)
        # Transform any args
        node.args = [self.visit(arg) for arg in node.args]
        node.keywords = [
            ast.keyword(kw.arg, self.visit(kw.value)) for kw in node.keywords
        ]
        # Match pattern: r.operation(...)
        if (
            isinstance(node.func, ast.Attribute)
            and isinstance(node.func.value, ast.Name)
            and node.func.value.id == "T"
        ):
            if node.func.attr == "use":
                # Special case for T.use()
                new_node = ast.Await(
                    ast.Call(
                        func=ast.Name(id="_tpy_use_subject", ctx=ast.Load()),
                        args=[
                            ast.Name(id="_tpy_subjholder", ctx=ast.Load()),
                            ast.Name(id="_tpy_resolver", ctx=ast.Load()),
                            node.args[0],  # Get the subject name
                        ],
                        keywords=node.keywords,
                    )
                )
            else:
                new_node = ast.Await(
                    ast.Call(
                        func=ast.Name(id="_tpy_call", ctx=ast.Load()),
                        args=[
                            ast.Name(id="_tpy_subjholder", ctx=ast.Load()),
                            ast.Constant(value=node.func.attr),  # op name as string
                            *node.args,  # tsl and other args
                        ],
                        keywords=node.keywords,
                    )
                )
            ast.copy_location(new_node, node)
            return new_node

        return node

    def visit_JoinedStr(self, node: ast.JoinedStr) -> Any:
        # Transform any T.op calls inside f-string expressions
        node.values = [
            self.visit(value) if isinstance(value, ast.FormattedValue) else value
            for value in node.values
        ]
        return node

    def visit_FormattedValue(self, node: ast.FormattedValue) -> Any:
        # Transform T.op calls inside the formatted value
        node.value = self.visit(node.value)
        return node


async def _tpy_use_subject(
    subjholder: _SubjHolder,
    resolver: Resolver[Any],
    subj_name: str | None,
    **kwargs: Any,
) -> None:
    try:
        subject = await resolver.resolve(subj_name, **kwargs)
    except Exception as e:
        kwargs_str = (
            (", " + ", ".join(f"{k}={v!r}" for k, v in kwargs.items()))
            if kwargs
            else ""
        )
        raise TpySubjectError(f"T.use({subj_name!r}{kwargs_str}): {e}") from e

    subjholder.subject = subject


async def _tpy_call(
    subjholder: _SubjHolder, op_name: str, *args: Any, **kwargs: Any
) -> Any:
    try:
        target = args[0]
        if isinstance(target, str):  # TSL also inherits from str
            subject = subjholder.subject
            if subject is None:
                raise RuntimeError("No subject provided")
            try:
                tsl = TSL(target)
            except ValueError:
                raise RuntimeError(f"Invalid TSL expression: {target}")
            handle = await subject.search(tsl, op_name)
        elif isinstance(target, Handle):
            handle = target
        else:
            raise RuntimeError(f"Invalid target type: {type(target)}")

        try:
            func = getattr(handle, op_name)
        except AttributeError:
            raise RuntimeError(f"Operation '{op_name}' not found on handle")

        async with handle.bind():
            ret = func(*args[1:], **kwargs)
            if inspect.isawaitable(ret):
                ret = await ret
            return ret
    except Exception as e:
        pargs_str = ", ".join(map(repr, args))
        kwargs_str = (
            (", " + ", ".join(f"{k}={v!r}" for k, v in kwargs.items()))
            if kwargs
            else ""
        )
        raise TpyOperationError(f"T.{op_name}({pargs_str}{kwargs_str}): {e}") from e


async def execute(code: str, resolver: Resolver[Any]) -> Any:
    # Parse and transform
    tree = ast.parse(code)
    transformer = _TpyTransformer()
    new_tree = transformer.visit(tree)
    new_tree.body.append(
        ast.Return(
            value=ast.Call(
                func=ast.Name(id="locals", ctx=ast.Load()), args=[], keywords=[]
            )
        )
    )

    # Wrap in async function
    wrapper = ast.Module(
        body=[
            ast.AsyncFunctionDef(
                name="_tpy_exec",
                args=ast.arguments(
                    args=[],
                    posonlyargs=[],
                    kwonlyargs=[],
                    defaults=[],
                    kw_defaults=[],
                ),
                body=new_tree.body,
                decorator_list=[],
                returns=None,
                type_params=[],
            )
        ],
        type_ignores=[],
    )
    ast.fix_missing_locations(wrapper)
    ast.copy_location(wrapper, tree)

    # Compile and execute
    namespace = {
        "_tpy_call": _tpy_call,
        "_tpy_use_subject": _tpy_use_subject,
        "_tpy_resolver": resolver,
        "_tpy_subjholder": _SubjHolder(),
    }
    code_obj = compile(wrapper, "<tpy>", "exec")
    exec(code_obj, namespace)

    # Run the wrapped code
    try:
        return _filter_locals(await namespace["_tpy_exec"]())  # type:ignore
    except (TpyOperationError, TpySubjectError) as e:
        # Must be called here so that both errors' traceback includes the frame of
        # _tpy_exec, whose linenos are equal to those in the original script
        e.lineno, e.locals = _get_source_lineno_and_locals(e)
        raise e
    except AssertionError as e:
        raise TpyAssertionError(e.args[0], *_get_source_lineno_and_locals(e)) from e
    except Exception as e:
        raise TpyRuntimeError(repr(e), *_get_source_lineno_and_locals(e)) from e
