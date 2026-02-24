"""Test configuration."""
import importlib
import importlib.abc
import importlib.machinery
import sys
from pathlib import Path
from unittest.mock import MagicMock

# Add the project root to the path so imports work
sys.path.insert(0, str(Path(__file__).parent.parent))


class _MockModule(MagicMock):
    """Mock module that supports attribute access and submodule imports."""

    def __init__(self, *args, name="mock", **kwargs):
        # Accept arbitrary positional args so subclassing works
        super().__init__(**kwargs)
        self._mock_name = name
        self.__name__ = name
        self.__path__ = [f"/fake/{name.replace('.', '/')}"]
        self.__file__ = f"/fake/{name.replace('.', '/')}.py"
        self.__all__ = []
        self.__spec__ = None
        self.__loader__ = None
        self.__package__ = name


class _CatchAllLoader(importlib.abc.Loader):
    def create_module(self, spec):
        return _MockModule(name=spec.name)

    def exec_module(self, module):
        pass


class _CatchAllFinder(importlib.abc.MetaPathFinder):
    """Auto-creates mock modules for specified top-level packages."""

    def __init__(self, packages):
        self.packages = packages

    def find_spec(self, fullname, path, target=None):
        for pkg in self.packages:
            if fullname == pkg or fullname.startswith(pkg + "."):
                if fullname not in sys.modules:
                    return importlib.machinery.ModuleSpec(
                        fullname,
                        _CatchAllLoader(),
                        is_package=True,
                    )
        return None


# Mock all external dependencies that the dreame_mower package needs
_MOCK_PACKAGES = [
    "homeassistant",
    "requests",
    "Crypto",
    "Cryptodome",
    # "PIL" — not mocked; pillow is installed for map_renderer tests
    "aiohttp",
    "cryptography",
    "micloud",
    "miio",
    "numpy",
    "paho",
    "py_mini_racer",
    "voluptuous",
]

sys.meta_path.insert(0, _CatchAllFinder(_MOCK_PACKAGES))
