"""Route discovery helpers."""

from collections.abc import Iterable
from importlib import import_module
from pkgutil import iter_modules
from types import ModuleType

from fastapi import APIRouter, FastAPI


def iter_route_modules(package: ModuleType) -> Iterable[ModuleType]:
    """Yield route modules in deterministic order."""
    package_path = getattr(package, "__path__", None)
    if package_path is None:
        raise TypeError(
            f"Expected a package module, but {package!r} has no '__path__'."
        )

    for module_info in sorted(iter_modules(package_path), key=lambda info: info.name):
        if module_info.ispkg or module_info.name.startswith("_"):
            continue
        yield import_module(f"{package.__name__}.{module_info.name}")


def include_discovered_routers(
    app: FastAPI,
    *,
    package: ModuleType | None = None,
    prefix: str = "/api",
) -> None:
    """Include every ``router`` exported by modules in the routes package."""
    if package is None:
        package = import_module(__name__)

    for module in iter_route_modules(package):
        router = getattr(module, "router", None)
        if isinstance(router, APIRouter):
            app.include_router(router, prefix=prefix)
