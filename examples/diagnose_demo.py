"""Minimal end-to-end demo.

Run after ``pip install -e ".[highs]"``::

    python examples/diagnose_demo.py
"""

import ors


def main() -> None:
    m = ors.Model("demo")
    x = m.add_var(lb=0, name="x")
    y = m.add_var(lb=0, name="y")

    m.add_constr(x + y >= 10, name="demand")
    m.add_constr(x + y <= 5, name="capacity")
    m.set_objective(x + y, sense="min")

    result = m.optimize()
    print(result)

    if result.status is ors.Status.INFEASIBLE:
        diagnosis = m.diagnose()
        print()
        print(diagnosis.summary())
        print()
        print(diagnosis.why("demand"))
        diagnosis.report("demo-report.html")
        print("\nreport: demo-report.html")


if __name__ == "__main__":
    main()
