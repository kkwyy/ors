"""Lightweight linear model layer.

Design goals: predictable operator semantics, user-facing names preserved all
the way to diagnostics, no hidden global state.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Iterable, Sequence

Number = int | float

INF = math.inf


class ModelError(Exception):
    """Raised when a model is malformed."""

    def __init__(self, message: str, hint: str | None = None) -> None:
        super().__init__(message)
        self.hint = hint


def _as_expr(value: object) -> "LinearExpr":
    if isinstance(value, LinearExpr):
        return value
    if isinstance(value, Var):
        return LinearExpr({value: 1.0})
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return LinearExpr({}, float(value))
    raise TypeError(f"cannot use {type(value).__name__} in a linear expression")


def _format_linear(coeffs: dict["Var", float], const: float = 0.0) -> str:
    terms: list[str] = []
    for var in sorted(coeffs, key=lambda v: v.index):
        a = coeffs[var]
        if a == 0.0:
            continue
        if a == 1.0:
            term = var.name
        elif a == -1.0:
            term = f"-{var.name}"
        else:
            term = f"{a:g}*{var.name}"
        if not terms:
            terms.append(term)
        elif term.startswith("-"):
            terms.append("- " + term[1:])
        else:
            terms.append("+ " + term)
    text = " ".join(terms) if terms else "0"
    if const:
        if terms:
            text += f" + {const:g}" if const > 0 else f" - {-const:g}"
        else:
            text = f"{const:g}"
    return text


class Var:
    """A decision variable. Hashable by identity; never override ``__eq__``."""

    __slots__ = ("index", "name", "lb", "ub", "vtype")

    def __init__(
        self,
        index: int,
        name: str,
        lb: float = 0.0,
        ub: float = INF,
        vtype: str = "continuous",
    ) -> None:
        self.index = index
        self.name = name
        self.lb = float(lb)
        self.ub = float(ub)
        self.vtype = vtype

    def __repr__(self) -> str:
        return f"Var({self.name!r})"

    # -- expression building -------------------------------------------------
    def __mul__(self, other: Number) -> "LinearExpr":
        if isinstance(other, (int, float)) and not isinstance(other, bool):
            return LinearExpr({self: float(other)})
        return NotImplemented  # type: ignore[return-value]

    __rmul__ = __mul__

    def __neg__(self) -> "LinearExpr":
        return LinearExpr({self: -1.0})

    def __add__(self, other: object) -> "LinearExpr":
        return LinearExpr({self: 1.0}) + other

    def __radd__(self, other: object) -> "LinearExpr":
        return self.__add__(other)

    def __sub__(self, other: object) -> "LinearExpr":
        return LinearExpr({self: 1.0}) - other

    def __rsub__(self, other: object) -> "LinearExpr":
        return _as_expr(other) - LinearExpr({self: 1.0})

    def __le__(self, other: object) -> "ConstraintSpec":
        return ConstraintSpec(LinearExpr({self: 1.0}), "<=", _as_expr(other))

    def __ge__(self, other: object) -> "ConstraintSpec":
        return ConstraintSpec(LinearExpr({self: 1.0}), ">=", _as_expr(other))

    def eq(self, other: object) -> "ConstraintSpec":
        """Equality constraint. Use this instead of ``==`` (which stays identity)."""
        return ConstraintSpec(LinearExpr({self: 1.0}), "==", _as_expr(other))


@dataclass
class LinearExpr:
    """A linear expression: ``sum(a_i * x_i) + const``."""

    coeffs: dict[Var, float] = field(default_factory=dict)
    const: float = 0.0

    def __post_init__(self) -> None:
        self.coeffs = {v: float(a) for v, a in self.coeffs.items() if float(a) != 0.0}
        self.const = float(self.const)

    def __add__(self, other: object) -> "LinearExpr":
        o = _as_expr(other)
        merged = dict(self.coeffs)
        for var, a in o.coeffs.items():
            merged[var] = merged.get(var, 0.0) + a
        return LinearExpr(merged, self.const + o.const)

    __radd__ = __add__

    def __sub__(self, other: object) -> "LinearExpr":
        return self + (-_as_expr(other))

    def __rsub__(self, other: object) -> "LinearExpr":
        return _as_expr(other) - self

    def __neg__(self) -> "LinearExpr":
        return LinearExpr({v: -a for v, a in self.coeffs.items()}, -self.const)

    def __mul__(self, other: Number) -> "LinearExpr":
        if not isinstance(other, (int, float)) or isinstance(other, bool):
            return NotImplemented  # type: ignore[return-value]
        k = float(other)
        return LinearExpr({v: a * k for v, a in self.coeffs.items()}, self.const * k)

    __rmul__ = __mul__

    def __truediv__(self, other: Number) -> "LinearExpr":
        if not isinstance(other, (int, float)) or isinstance(other, bool) or other == 0:
            raise ModelError("division by zero or non-scalar")
        return self * (1.0 / float(other))

    def __le__(self, other: object) -> "ConstraintSpec":
        return ConstraintSpec(self, "<=", _as_expr(other))

    def __ge__(self, other: object) -> "ConstraintSpec":
        return ConstraintSpec(self, ">=", _as_expr(other))

    def eq(self, other: object) -> "ConstraintSpec":
        return ConstraintSpec(self, "==", _as_expr(other))

    def __repr__(self) -> str:
        return f"LinearExpr({_format_linear(self.coeffs, self.const)!r})"


@dataclass
class ConstraintSpec:
    """A comparison before it is attached to a model."""

    lhs: LinearExpr
    sense: str
    rhs: LinearExpr

    def normalize(self) -> tuple[dict[Var, float], str, float]:
        expr = self.lhs - self.rhs
        return expr.coeffs, self.sense, -expr.const


@dataclass
class Constraint:
    """A normalized row ``coeffs @ x (sense) rhs`` with provenance."""

    index: int
    name: str
    coeffs: dict[Var, float]
    sense: str
    rhs: float

    def expression(self) -> str:
        return f"{_format_linear(self.coeffs)} {self.sense} {self.rhs:g}"

    def __repr__(self) -> str:
        return f"Constraint({self.name!r}, {self.expression()!r})"


class Model:
    """A linear program or MILP under construction."""

    def __init__(self, name: str = "model") -> None:
        self.name = name
        self._vars: list[Var] = []
        self._constrs: list[Constraint] = []
        self._obj = LinearExpr()
        self._sense = "min"
        self._var_names: set[str] = set()
        self._constr_names: set[str] = set()

    # -- construction --------------------------------------------------------
    def _unique_var_name(self, name: str | None) -> str:
        if name is None:
            name = f"x{len(self._vars)}"
        base = name
        k = 2
        while name in self._var_names:
            name = f"{base}_{k}"
            k += 1
        self._var_names.add(name)
        return name

    def add_var(
        self,
        lb: float = 0.0,
        ub: float = INF,
        vtype: str = "continuous",
        name: str | None = None,
    ) -> Var:
        if vtype not in ("continuous", "integer", "binary"):
            raise ModelError(f"unknown vtype {vtype!r}", hint="use continuous/integer/binary")
        if vtype == "binary":
            lb, ub = max(float(lb), 0.0), min(float(ub), 1.0)
        var = Var(len(self._vars), self._unique_var_name(name), lb, ub, vtype)
        self._vars.append(var)
        return var

    def add_vars(
        self,
        n: int,
        lb: float = 0.0,
        ub: float = INF,
        vtype: str = "continuous",
        name: str | None = None,
    ) -> list[Var]:
        if n < 0:
            raise ModelError("n must be non-negative")
        return [
            self.add_var(lb=lb, ub=ub, vtype=vtype, name=None if name is None else f"{name}[{i}]")
            for i in range(n)
        ]

    def _unique_constr_name(self, name: str | None) -> str:
        if name is None:
            name = f"c{len(self._constrs)}"
        base = name
        k = 2
        while name in self._constr_names:
            name = f"{base}_{k}"
            k += 1
        self._constr_names.add(name)
        return name

    def add_constr(self, spec: ConstraintSpec, name: str | None = None) -> Constraint:
        if not isinstance(spec, ConstraintSpec):
            raise TypeError("add_constr expects an expression built with <=, >= or .eq()")
        coeffs, sense, rhs = spec.normalize()
        return self._add_raw(coeffs, sense, rhs, name)

    def _add_raw(
        self,
        coeffs: dict[Var, float],
        sense: str,
        rhs: float,
        name: str | None = None,
    ) -> Constraint:
        if sense not in ("<=", ">=", "=="):
            raise ModelError(f"unknown sense {sense!r}")
        for var in coeffs:
            if var.index >= len(self._vars) or self._vars[var.index] is not var:
                raise ModelError("constraint references a variable from another model")
        clean = {v: float(a) for v, a in coeffs.items() if float(a) != 0.0}
        constr = Constraint(
            index=len(self._constrs),
            name=self._unique_constr_name(name),
            coeffs=clean,
            sense=sense,
            rhs=float(rhs),
        )
        self._constrs.append(constr)
        return constr

    def set_objective(self, expr: object, sense: str = "min") -> None:
        if sense not in ("min", "max"):
            raise ModelError(f"unknown sense {sense!r}", hint="use 'min' or 'max'")
        self._obj = _as_expr(expr)
        self._sense = sense

    # -- inspection ----------------------------------------------------------
    @property
    def variables(self) -> Sequence[Var]:
        return tuple(self._vars)

    @property
    def constraints(self) -> Sequence[Constraint]:
        return tuple(self._constrs)

    @property
    def num_vars(self) -> int:
        return len(self._vars)

    @property
    def num_constrs(self) -> int:
        return len(self._constrs)

    @property
    def objective(self) -> LinearExpr:
        return self._obj

    @property
    def sense(self) -> str:
        return self._sense

    def _obj_coeff(self, var: Var) -> float:
        return self._obj.coeffs.get(var, 0.0)

    # -- solve / diagnose ----------------------------------------------------
    def optimize(self, options=None):
        from .backend import highs_backend

        return highs_backend.solve(self, options=options)

    def diagnose(self, options=None):
        from .diagnose import diagnose

        return diagnose(self, options=options)

    # -- io ------------------------------------------------------------------
    @classmethod
    def read(cls, path: str) -> "Model":
        from .backend import highs_backend

        return highs_backend.read_model(path)

    def write(self, path: str) -> None:
        raise NotImplementedError(
            "MPS/LP writing lands in 0.2; use highspy.Highs().writeModel(path) meanwhile"
        )

    def __repr__(self) -> str:
        return (
            f"Model({self.name!r}, vars={self.num_vars}, "
            f"constrs={self.num_constrs}, sense={self._sense!r})"
        )
