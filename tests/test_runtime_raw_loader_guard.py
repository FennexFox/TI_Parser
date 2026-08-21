from __future__ import annotations

import ast
from collections import Counter
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
RUNTIME_FILES = [ROOT / "tools" / "ti_save_parser.py", *sorted((ROOT / "tools").glob("ti_parser_*.py"))]
PROHIBITED_CALLS = {
    "load_named_templates",
    "load_trait_templates",
    "resolve_templates_dir",
    "resolve_scenario_templates",
}

# Final allowlist: these two helpers implement explicit legacy/raw inspection
# utilities, but no normal command calls them.  All command, calculation,
# snapshot, org, research, hab, and ship raw-loader edges were removed.
AUDITED_RUNTIME_CALLS = Counter(
    {
        ("tools/ti_parser_core.py", "load_trait_templates", "load_named_templates"): 1,
        ("tools/ti_parser_core.py", "scenario_template_sources", "load_named_templates"): 1,
    }
)


def runtime_raw_loader_calls() -> Counter[tuple[str, str, str]]:
    calls: Counter[tuple[str, str, str]] = Counter()
    for path in RUNTIME_FILES:
        function_stack: list[str] = []

        class Visitor(ast.NodeVisitor):
            def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
                function_stack.append(node.name)
                self.generic_visit(node)
                function_stack.pop()

            visit_AsyncFunctionDef = visit_FunctionDef

            def visit_Call(self, node: ast.Call) -> None:
                name = None
                if isinstance(node.func, ast.Name):
                    name = node.func.id
                elif isinstance(node.func, ast.Attribute):
                    name = node.func.attr
                if name in PROHIBITED_CALLS:
                    calls[(path.relative_to(ROOT).as_posix(), function_stack[-1] if function_stack else "<module>", name)] += 1
                self.generic_visit(node)

        Visitor().visit(ast.parse(path.read_text(encoding="utf-8"), filename=str(path)))
    return calls


class RuntimeRawLoaderGuardTests(unittest.TestCase):
    def test_runtime_raw_loader_edges_do_not_expand_beyond_audited_baseline(self) -> None:
        actual = runtime_raw_loader_calls()
        self.assertEqual(actual, AUDITED_RUNTIME_CALLS)


if __name__ == "__main__":
    unittest.main()
