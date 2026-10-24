import pytest

import ors


def test_expression_coefficients():
    m = ors.Model()
    x = m.add_var(name="x")
    y = m.add_var(name="y")
    expr = 2 * x + 3 * y - 1
    assert expr.coeffs[x] == 2
    assert expr.coeffs[y] == 3
    assert expr.const == -1


def test_constraint_normalization():
    m = ors.Model()
    x = m.add_var(name="x")
    y = m.add_var(name="y")
    c = m.add_constr(2 * x + 3 * y - 1 <= 10, name="cap")
    assert c.sense == "<="
    assert c.rhs == 11
    assert c.coeffs[x] == 2
    assert c.coeffs == {x: 2, y: 3}


def test_equality_uses_eq_method():
    m = ors.Model()
    x = m.add_var(name="x")
    c = m.add_constr(x.eq(3), name="fix")
    assert c.sense == "=="
    assert c.rhs == 3


def test_duplicate_names_get_suffix():
    m = ors.Model()
    x = m.add_var(name="x")
    y = m.add_var(name="x")
    assert x.name == "x"
    assert y.name == "x_2"
    m.add_constr(x <= 1, name="c")
    c2 = m.add_constr(y <= 1, name="c")
    assert c2.name == "c_2"


def test_cross_model_variable_rejected():
    m1 = ors.Model()
    x = m1.add_var(name="x")
    m2 = ors.Model()
    with pytest.raises(ors.ModelError):
        m2.add_constr(x <= 1)


def test_model_counts():
    m = ors.Model("demo")
    x = m.add_var(name="x")
    ys = m.add_vars(3, name="y")
    assert [v.name for v in ys] == ["y[0]", "y[1]", "y[2]"]
    m.add_constr(x + ys[0] >= 1)
    assert m.num_vars == 4
    assert m.num_constrs == 1
