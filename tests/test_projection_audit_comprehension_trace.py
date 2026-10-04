import sys
from pathlib import Path
from types import SimpleNamespace


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import audit_projection_reads as audit
from projection_audit_dependencies import dependency_append_sites


def test_nested_comprehension_rule_read_maps_to_enclosing_function_and_edge(tmp_path, monkeypatch):
    tools = tmp_path / "tools"
    tools.mkdir()
    source_path = tools / "ti_parser_probe.py"
    source = (
        "def probe():\n"
        "    execution = {'ruleId': 'parent.rule', 'dependencies': []}\n"
        "    execution['dependencies'].append(next(iter(\n"
        "        {outer: {inner: Rules.sample.id for inner in (0,)} for outer in (0,)}.values()\n"
        "    ))[0])\n"
        "    return execution\n"
    )
    source_path.write_text(source, encoding="utf-8")
    tracker = audit.ReadTracker()
    monkeypatch.setattr(audit, "ROOT", tmp_path)
    monkeypatch.setattr(audit, "TOOLS", tools)

    rules = SimpleNamespace(sample=SimpleNamespace(id="sample.rule"))
    append_sites = {
        (row["module"], row["function"], row["line"], row["ruleName"])
        for row in dependency_append_sites(tools)
    }
    namespace = {
        "__name__": "ti_parser_probe",
        "__file__": str(source_path),
        "Rules": audit._TracedRuleNamespace(rules, tracker, append_sites),
    }
    exec(compile(source, str(source_path), "exec"), namespace)

    assert namespace["probe"]()["dependencies"] == ["sample.rule"]

    [reference] = tracker.runtime_rule_reference_events.values()
    assert reference["consumer"] == "ti_parser_probe.probe"
    assert reference["sourceLocation"]["file"] == "tools/ti_parser_probe.py"
    assert reference["sourceLocation"]["line"] == 4
    assert reference["sourceControlFlow"]["sourceMapped"] is True
    assert reference["sourceControlFlow"]["function"] == "probe"

    [edge] = tracker.runtime_dependency_edge_events.values()
    assert edge["from"] == "parent.rule"
    assert edge["to"] == "sample.rule"
    assert edge["consumer"] == "ti_parser_probe.probe"
    assert edge["sourceLocation"]["line"] == 4
