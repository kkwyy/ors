import pytest

import ors

pytest.importorskip("highspy", reason="highspy backend not installed")


def test_solve_optimal_lp():
    m = ors.Model("lp")
    x = m.add_var(lb=0, name="x")
    y = m.add_var(lb=0, name="y")
    m.add_constr(x + y >= 1, name="demand")
    m.set_objective(x + y, sense="min")

    result = m.optimize()
    assert result.status is ors.Status.OPTIMAL
    assert result.objective == pytest.approx(1.0)
    assert result.x["x"] + result.x["y"] == pytest.approx(1.0)


def test_solve_infeasible():
    m = ors.Model("inf")
    x = m.add_var(lb=0, name="x")
    m.add_constr(x >= 2, name="lo")
    m.add_constr(x <= 1, name="hi")

    result = m.optimize()
    assert result.status is ors.Status.INFEASIBLE


def test_solve_unbounded():
    m = ors.Model("unb")
    x = m.add_var(lb=0, name="x")
    m.set_objective(-1 * x, sense="min")

    result = m.optimize()
    assert result.status in (ors.Status.UNBOUNDED, ors.Status.INF_OR_UNB)


def test_dual_values_available_for_lp():
    m = ors.Model("dual")
    x = m.add_var(lb=0, name="x")
    m.add_constr(x >= 2, name="demand")
    m.set_objective(x, sense="min")

    result = m.optimize()
    assert result.status is ors.Status.OPTIMAL
    assert result.dual is not None
    assert result.dual["demand"] == pytest.approx(1.0, abs=1e-6)
