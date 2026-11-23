"""CUIA docstrings: params are positional, documented in a "Params:" section (static analysis)."""

import ast
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
GUI = REPO / "zyngui" / "zynthian_gui.py"


def _cuia_docstrings():
    tree = ast.parse(GUI.read_text(encoding="utf-8"))
    for cls in (n for n in tree.body if isinstance(n, ast.ClassDef)):
        for fn in cls.body:
            if isinstance(fn, ast.FunctionDef) and fn.name.startswith("cuia_"):
                yield fn, ast.get_docstring(fn) or ""


def test_no_keyword_args_sections():
    bad = [fn.name for fn, doc in _cuia_docstrings()
           if re.search(r"^\s*(Keyword|Kwy\w*) Args:", doc, re.M)]
    assert not bad, f'Use "Params:" (positional), not "Keyword Args:": {bad}'


def test_params_order_matches_docstring():
    sys.path.insert(0, str(REPO / "zynagent"))
    try:
        import zynagent_tools
    except ImportError:
        import pytest
        pytest.skip("zynagent_tools dependencies not available")
    zynagent_tools._cuia_param_order.clear()
    zynagent_tools.generate_zynthian_cuia_tools()
    for fn, doc in _cuia_docstrings():
        m = re.search(r"^\s*Params:\n(.*?)(?:\n\s*\n|\Z)", doc, re.M | re.S)
        expected = re.findall(r"^\s{4}(\w+)\b[^\n]*:", m.group(1), re.M) if m else []
        # entries are the least-indented lines of the section
        assert zynagent_tools._cuia_param_order.get(fn.name[5:]) == expected or not doc.strip(), fn.name
