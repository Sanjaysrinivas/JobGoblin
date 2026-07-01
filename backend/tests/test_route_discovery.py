import importlib
import sys
from types import ModuleType

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.routes import include_discovered_routers


def test_include_discovered_routers_adds_package_routers_under_api_prefix(tmp_path):
    package_dir = tmp_path / "fake_routes"
    package_dir.mkdir()
    (package_dir / "__init__.py").write_text("", encoding="utf-8")
    (package_dir / "alpha.py").write_text(
        "from fastapi import APIRouter\n"
        "router = APIRouter(prefix='/alpha')\n"
        "@router.get('')\n"
        "def read_alpha():\n"
        "    return {'route': 'alpha'}\n",
        encoding="utf-8",
    )
    (package_dir / "zeta.py").write_text(
        "from fastapi import APIRouter\n"
        "router = APIRouter(prefix='/zeta')\n"
        "@router.get('')\n"
        "def read_zeta():\n"
        "    return {'route': 'zeta'}\n",
        encoding="utf-8",
    )
    (package_dir / "without_router.py").write_text("VALUE = 1\n", encoding="utf-8")
    (package_dir / "_private.py").write_text(
        "raise AssertionError('private route modules must not be imported')\n",
        encoding="utf-8",
    )
    subpackage = package_dir / "nested"
    subpackage.mkdir()
    (subpackage / "__init__.py").write_text(
        "raise AssertionError('subpackages must not be imported')\n",
        encoding="utf-8",
    )

    sys.path.insert(0, str(tmp_path))
    try:
        importlib.invalidate_caches()
        package = importlib.import_module("fake_routes")
        app = FastAPI()

        include_discovered_routers(app, package=package, prefix="/api")

        client = TestClient(app)
        assert client.get("/api/alpha").json() == {"route": "alpha"}
        assert client.get("/api/zeta").json() == {"route": "zeta"}
        assert client.get("/api/without_router").status_code == 404
    finally:
        sys.path.remove(str(tmp_path))
        for module_name in list(sys.modules):
            if module_name == "fake_routes" or module_name.startswith("fake_routes."):
                del sys.modules[module_name]


def test_include_discovered_routers_rejects_non_package_module():
    app = FastAPI()
    module = ModuleType("not_a_package")

    with pytest.raises(TypeError, match="Expected a package module"):
        include_discovered_routers(app, package=module)
