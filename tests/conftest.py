from pathlib import Path
import sys


TOOLS = Path(__file__).resolve().parents[1] / "tools"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

from ti_parser_mechanics import register_collected_mechanic_test


def pytest_collection_modifyitems(config, items):
    root = Path(str(config.rootpath)).resolve()
    for item in items:
        try:
            relative = Path(str(item.path)).resolve().relative_to(root)
        except ValueError:
            continue
        module_name = ".".join(relative.with_suffix("").parts)
        class_name = getattr(getattr(item, "cls", None), "__name__", None)
        method_name = getattr(item, "originalname", None) or item.name.split("[", 1)[0]
        if class_name:
            test_id = f"{module_name}.{class_name}.{method_name}"
        else:
            test_id = f"{module_name}.{method_name}"
        register_collected_mechanic_test(test_id, item.obj)
