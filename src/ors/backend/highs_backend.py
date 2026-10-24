"""HiGHS backend.

The MVP rebuilds the model on every solve. That is slower than the incremental
API but keeps the diagnostics layer honest: no hidden state can leak between
IIS trials.
"""

from __future__ import annotations

import math
import time
from collections.abc import Iterable

import numpy as np

from ..model import LinearExpr, Model, ModelError
from ..result import Result, SolveOptions, Status


class BackendNotAvailable(RuntimeError):
    def __init__(self, message: str, hint: str | None = None) -> None:
        super().__init__(message)
        self.hint = hint


def available() -> bool:
    try:
        import highspy  # noqa: F401
    except ImportError:
        return False
    return True


def _highspy():
    try:
        import highspy
    except ImportError as exc:  # pragma: no cover - environment dependent
        raise BackendNotAvailable(
            "highspy is not installed",
            hint='pip install "ors[highs]"',
        ) from exc
    return highspy


def _map_status(highspy, status) -> Status:
    H = highspy.HighsModelStatus
    if status == H.kOptimal:
        return Status.OPTIMAL
    if status == H.kInfeasible:
        return Status.INFEASIBLE
    if status == H.kUnbounded:
        return Status.UNBOUNDED
    if status == H.kUnboundedOrInfeasible:
        return Status.INF_OR_UNB
    if status == H.kTimeLimit:
        return Status.TIME_LIMIT
    if status == H.kIterationLimit:
        return Status.ITERATION_LIMIT
    if status == H.kModelEmpty:
        return Status.OPTIMAL
    return Status.ERROR


def _build(highspy, model: Model, active_rows: Iterable[int] | None):
    """Assemble a :class:`highspy.HighsLp` and hand it to HiGHS in one call.

    Building the LP object (instead of incremental ``addRows``/``addCols``)
    keeps this independent of the backend's incremental-API version.
    """
    variables = model.variables
    nv = len(variables)
    active = None if active_rows is None else set(active_rows)
    rows = [c for c in model.constraints if active is None or c.index in active]
    nr = len(rows)

    # Column-wise sparse matrix (CSC), as HiGHS expects by default.
    columns: list[list[tuple[int, float]]] = [[] for _ in range(nv)]
    row_lower = np.empty(nr, dtype=np.float64)
    row_upper = np.empty(nr, dtype=np.float64)
    for i, c in enumerate(rows):
        if c.sense == "<=":
            row_lower[i], row_upper[i] = -math.inf, c.rhs
        elif c.sense == ">=":
            row_lower[i], row_upper[i] = c.rhs, math.inf
        else:
            row_lower[i] = row_upper[i] = c.rhs
        for var, a in c.coeffs.items():
            columns[var.index].append((i, a))

    nnz = sum(len(col) for col in columns)
    starts = np.zeros(nv + 1, dtype=np.int32)
    indices = np.empty(nnz, dtype=np.int32)
    values = np.empty(nnz, dtype=np.float64)
    k = 0
    for j, entries in enumerate(columns):
        for row_index, value in entries:
            indices[k] = row_index
            values[k] = value
            k += 1
        starts[j + 1] = k

    lp = highspy.HighsLp()
    lp.num_col_ = nv
    lp.num_row_ = nr
    lp.col_cost_ = np.array([model._obj_coeff(v) for v in variables], dtype=np.float64)
    lp.col_lower_ = np.array([v.lb for v in variables], dtype=np.float64)
    lp.col_upper_ = np.array([v.ub for v in variables], dtype=np.float64)
    lp.row_lower_ = row_lower
    lp.row_upper_ = row_upper
    lp.a_matrix_.format_ = highspy.MatrixFormat.kColwise
    lp.a_matrix_.start_ = starts
    lp.a_matrix_.index_ = indices
    lp.a_matrix_.value_ = values
    lp.sense_ = highspy.ObjSense.kMinimize if model.sense == "min" else highspy.ObjSense.kMaximize
    if any(v.vtype != "continuous" for v in variables):
        lp.integrality_ = [
            highspy.HighsVarType.kContinuous
            if v.vtype == "continuous"
            else highspy.HighsVarType.kInteger
            for v in variables
        ]

    h = highspy.Highs()
    h.setOptionValue("output_flag", False)
    if h.passModel(lp) != highspy.HighsStatus.kOk:
        raise ModelError("backend rejected the model")
    return h, rows


def solve(
    model: Model,
    options: SolveOptions | None = None,
    active_rows: Iterable[int] | None = None,
) -> Result:
    opts = options or SolveOptions()
    for var in model.variables:
        if var.lb > var.ub:
            return Result(
                status=Status.INFEASIBLE,
                runtime=0.0,
                backend="precheck",
                message=f"variable {var.name!r} has lb={var.lb:g} > ub={var.ub:g}",
            )
    highspy = _highspy()
    start = time.perf_counter()

    h, rows = _build(highspy, model, active_rows)
    if opts.time_limit is not None:
        h.setOptionValue("time_limit", float(opts.time_limit))
    if opts.threads is not None:
        h.setOptionValue("threads", int(opts.threads))
    if opts.verbose:
        h.setOptionValue("output_flag", True)

    h.run()
    status = _map_status(highspy, h.getModelStatus())
    info = h.getInfo()
    runtime = time.perf_counter() - start

    objective: float | None = None
    if status is Status.OPTIMAL:
        objective = float(info.objective_function_value) + model.objective.const
    elif status is Status.TIME_LIMIT:
        value = float(info.objective_function_value)
        objective = value + model.objective.const if math.isfinite(value) else None

    x: dict[str, float] | None = None
    if status.has_solution and model.num_vars:
        solution = h.getSolution()
        if len(solution.col_value) >= model.num_vars:
            x = {v.name: float(solution.col_value[v.index]) for v in model.variables}

    dual: dict[str, float] | None = None
    is_lp = all(v.vtype == "continuous" for v in model.variables)
    if status is Status.OPTIMAL and is_lp and rows:
        solution = h.getSolution()
        dual = {rows[i].name: float(solution.row_dual[i]) for i in range(len(rows))}

    gap = getattr(info, "mip_gap", None)
    if gap is not None and not math.isfinite(gap):
        gap = None

    return Result(
        status=status,
        objective=objective,
        x=x,
        dual=dual,
        iterations=int(getattr(info, "simplex_iteration_count", 0) or 0),
        runtime=runtime,
        backend="highs",
        gap=gap,
    )


def read_model(path: str) -> Model:
    """Read an MPS or LP file into a :class:`~ors.model.Model`."""
    highspy = _highspy()
    h = highspy.Highs()
    h.setOptionValue("output_flag", False)
    if h.readModel(str(path)) != highspy.HighsStatus.kOk:
        raise ModelError(
            f"could not read {path!r}",
            hint="supported formats: .mps, .lp; check the file is well-formed",
        )

    lp = h.getLp()
    stem = str(path).rsplit("/", 1)[-1].rsplit(".", 1)[0]
    model = Model(name=stem)

    col_names = list(lp.col_names_)
    integrality = list(lp.integrality_)
    for j in range(lp.num_col_):
        name = col_names[j] if j < len(col_names) and col_names[j] else f"x{j}"
        vtype = "continuous"
        if j < len(integrality) and integrality[j] != highspy.HighsVarType.kContinuous:
            vtype = "integer"
        model.add_var(
            lb=float(lp.col_lower_[j]),
            ub=float(lp.col_upper_[j]),
            vtype=vtype,
            name=name,
        )

    objective = LinearExpr()
    for j, var in enumerate(model.variables):
        cost = float(lp.col_cost_[j])
        if cost:
            objective = objective + var * cost
    model.set_objective(
        objective,
        sense="min" if lp.sense_ == highspy.ObjSense.kMinimize else "max",
    )

    nrows = lp.num_row_
    row_coeffs: list[dict[int, float]] = [{} for _ in range(nrows)]
    matrix = lp.a_matrix_
    if matrix.format_ == highspy.MatrixFormat.kColwise:
        for j in range(lp.num_col_):
            for k in range(matrix.start_[j], matrix.start_[j + 1]):
                row_coeffs[matrix.index_[k]][j] = float(matrix.value_[k])
    elif matrix.format_ == highspy.MatrixFormat.kRowwise:
        for i in range(nrows):
            for k in range(matrix.start_[i], matrix.start_[i + 1]):
                row_coeffs[i][matrix.index_[k]] = float(matrix.value_[k])
    else:  # pragma: no cover - defensive
        raise ModelError("unknown matrix format in model file")

    row_names = list(lp.row_names_)
    for i in range(nrows):
        name = row_names[i] if i < len(row_names) and row_names[i] else f"c{i}"
        coeffs = {model.variables[j]: a for j, a in row_coeffs[i].items()}
        lo = float(lp.row_lower_[i])
        up = float(lp.row_upper_[i])
        if lo == up:
            model._add_raw(coeffs, "==", lo, name)
        elif math.isinf(up):
            model._add_raw(coeffs, ">=", lo, name)
        elif math.isinf(lo):
            model._add_raw(coeffs, "<=", up, name)
        else:
            # Ranged row: split into two named constraints to keep the model linear.
            model._add_raw(coeffs, ">=", lo, f"{name}_lo")
            model._add_raw(coeffs, "<=", up, f"{name}_hi")
    return model
