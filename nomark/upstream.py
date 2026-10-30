"""Load pinned upstream modules without changing the application's import path."""
import builtins
import importlib.util
from pathlib import Path
import sys
import threading
import types

SCRIPTS = Path(__file__).resolve().parents[1] / 'watermarks-remover/service/scripts'
MODULES = frozenset({'common', 'text_unicode', 'image_meta', 'container_meta', 'av_meta'})
_lock = threading.RLock()
_namespace = '_nomark_upstream'


def _import(name, globals=None, locals=None, fromlist=(), level=0):
    if level == 0 and name in MODULES:
        return load(name)
    return builtins.__import__(name, globals, locals, fromlist, level)


def load(name):
    if name not in MODULES:
        raise ImportError('Unsupported upstream module')
    qualified = f'{_namespace}.{name}'
    source = SCRIPTS / f'{name}.py'
    with _lock:
        if qualified in sys.modules:
            module = sys.modules[qualified]
            if getattr(module, '__file__', None) != str(source):
                raise ImportError('Upstream module origin mismatch')
            return module
        if _namespace not in sys.modules:
            package = types.ModuleType(_namespace)
            package.__path__ = []
            sys.modules[_namespace] = package
        spec = importlib.util.spec_from_file_location(qualified, source)
        if spec is None or spec.loader is None:
            raise ImportError('Upstream module is unavailable')
        module = importlib.util.module_from_spec(spec)
        # Upstream uses absolute sibling imports; scope their resolution to this loader.
        module.__dict__['__builtins__'] = {**vars(builtins), '__import__': _import}
        sys.modules[qualified] = module
        try:
            spec.loader.exec_module(module)
        except BaseException:
            sys.modules.pop(qualified, None)
            raise
        return module


common = load('common')
text_unicode = load('text_unicode')
image_meta = load('image_meta')
container_meta = load('container_meta')
av_meta = load('av_meta')
