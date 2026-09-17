from __future__ import annotations

import ast
import subprocess
import sys
from pathlib import Path
import unittest


TOOLS = Path(__file__).resolve().parents[1] / "tools"
DOMAIN_MODULES = (
    "ti_parser_config",
    "ti_parser_runtime",
    "ti_parser_hab_ui",
    "ti_parser_hab_construction",
    "ti_parser_hab_plan",
    "ti_parser_research",
    "ti_parser_research_plan",
    "ti_parser_project_analysis",
    "ti_parser_ship_plan",
    "ti_parser_topbar",
    "ti_parser_world",
    "ti_parser_nation_ui",
    "ti_parser_projection_adapter",
    "ti_parser_commands",
)


class DomainBoundaryTests(unittest.TestCase):
    def test_each_domain_imports_without_loading_the_public_facade(self):
        # Separate interpreters expose order-dependent cycles hidden by the facade.
        script = (
            "import importlib, sys; "
            "sys.path.insert(0, sys.argv[1]); "
            "importlib.import_module(sys.argv[2]); "
            "assert 'ti_save_parser' not in sys.modules"
        )
        for module in DOMAIN_MODULES:
            with self.subTest(module=module):
                result = subprocess.run(
                    [sys.executable, "-B", "-c", script, str(TOOLS), module],
                    stdin=subprocess.DEVNULL,
                    capture_output=True,
                    text=True,
                    encoding="utf-8",
                    timeout=30,
                    check=False,
                )
                self.assertEqual(result.returncode, 0, result.stderr)

    def test_domain_dependencies_are_acyclic_even_for_local_imports(self):
        graph = {}
        for module in DOMAIN_MODULES:
            tree = ast.parse((TOOLS / f"{module}.py").read_text(encoding="utf-8"))
            imports = set()
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    imports.update(alias.name for alias in node.names)
                elif isinstance(node, ast.ImportFrom):
                    imports.add(node.module)
            self.assertNotIn("ti_save_parser", imports, module)
            graph[module] = imports.intersection(DOMAIN_MODULES)

        visited = set()

        def visit(module, path):
            self.assertNotIn(module, path, " -> ".join((*path, module)))
            if module in visited:
                return
            for dependency in graph[module]:
                visit(dependency, (*path, module))
            visited.add(module)

        for module in graph:
            visit(module, ())


if __name__ == "__main__":
    unittest.main()
