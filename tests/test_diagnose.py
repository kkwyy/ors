import pytest

import ors

pytest.importorskip("highspy", reason="highspy backend not installed")


def test_iis_finds_conflict():
    m = ors.Model("inf")
    x = m.add_var(lb=0, name="x")
    m.add_constr(x >= 2, name="demand")
    m.add_constr(x <= 1, name="capacity")

    diagnosis = m.diagnose()
    assert diagnosis.status == "infeasible"
    assert diagnosis.iis is not None
    assert {c.name for c in diagnosis.iis.constraints} == {"demand", "capacity"}


def test_iis_excludes_irrelevant_constraint():
    m = ors.Model("inf")
    x = m.add_var(lb=0, name="x")
    y = m.add_var(lb=0, name="y")
    m.add_constr(x >= 2, name="demand")
    m.add_constr(x <= 1, name="capacity")
    m.add_constr(y <= 5, name="irrelevant")

    diagnosis = m.diagnose()
    names = {c.name for c in diagnosis.iis.constraints}
    assert names == {"demand", "capacity"}


def test_why_explains_essential_constraint():
    m = ors.Model("inf")
    x = m.add_var(lb=0, name="x")
    m.add_constr(x >= 2, name="demand")
    m.add_constr(x <= 1, name="capacity")

    diagnosis = m.diagnose()
    message = diagnosis.why("demand")
    assert "essential" in message


def test_findings_flag_big_coefficient_and_duplicates():
    m = ors.Model("dirty")
    x = m.add_var(lb=0, name="x")
    m.add_constr(1e7 * x <= 1, name="big")
    m.add_constr(x <= 1, name="a")
    m.add_constr(x <= 1, name="b")

    diagnosis = m.diagnose()
    codes = {f.code for f in diagnosis.findings}
    assert "BIG_COEF" in codes
    assert "DUPLICATE_ROW" in codes


def test_report_json_roundtrip(tmp_path):
    m = ors.Model("inf")
    x = m.add_var(lb=0, name="x")
    m.add_constr(x >= 2, name="demand")
    m.add_constr(x <= 1, name="capacity")

    diagnosis = m.diagnose()
    path = tmp_path / "report.json"
    diagnosis.report(str(path), format="json")
    text = path.read_text(encoding="utf-8")
    assert "demand" in text
    assert '"status": "infeasible"' in text
