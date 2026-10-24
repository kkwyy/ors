"""Infeasibility diagnosis.

The MVP covers linear programs:

* irreducible infeasible subsystem (IIS) via a deletion filter or the additive
  method;
* a structural health check of the model.

Certificates, minimal relaxations and MILP diagnosis are on the roadmap.
"""

from __future__ import annotations

import json
import time
from dataclasses import asdict, dataclass, field
from html import escape
from pathlib import Path

from .backend import highs_backend
from .model import Constraint, Model
from .result import SolveOptions, Status


class DiagnosisError(Exception):
    """Raised when diagnosis is requested for a model that is not infeasible."""

    def __init__(self, message: str, hint: str | None = None) -> None:
        super().__init__(message)
        self.hint = hint


@dataclass
class DiagnoseOptions:
    method: str = "auto"
    """``auto`` | ``deletion`` | ``additive``."""

    max_time: float = 60.0
    """Wall-clock budget for the whole diagnosis, in seconds."""

    max_solves: int = 1000
    """Maximum number of LP solves."""

    include_bounds: bool = True
    """Reserved: include variable bounds in the conflict set."""

    explain: bool = False
    """Reserved: attach a natural-language explanation."""

    explain_model: str | None = None
    """Reserved: ``local`` | ``cloud`` | a model name."""


@dataclass
class Finding:
    severity: str
    """``error`` | ``warning`` | ``info``."""

    code: str
    message: str
    refs: list[str] = field(default_factory=list)


@dataclass
class IIS:
    constraints: list[Constraint] = field(default_factory=list)
    minimal: bool = True
    method: str = "deletion"
    solves: int = 0
    note: str | None = None

    def summary(self) -> str:
        if not self.constraints:
            return "IIS: empty (variable bounds alone are infeasible)"
        lines = [f"IIS: {len(self.constraints)} constraint(s) [{self.method}, {self.solves} solves]"]
        lines += [f"  - {c.name}: {c.expression()}" for c in self.constraints]
        return "\n".join(lines)


@dataclass
class Diagnosis:
    status: str
    model: Model = field(repr=False)
    iis: IIS | None = None
    relaxation: object | None = None
    certificate: object | None = None
    findings: list[Finding] = field(default_factory=list)
    explanation: str | None = None
    elapsed: float = 0.0
    backend: str = "highs"

    def summary(self) -> str:
        lines = [
            f"status: {self.status}",
            f"backend: {self.backend}",
            f"elapsed: {self.elapsed:.3f}s",
        ]
        if self.iis is not None:
            lines.append(self.iis.summary())
        if self.findings:
            lines.append(f"findings: {len(self.findings)}")
            for finding in self.findings[:10]:
                lines.append(f"  [{finding.severity}] {finding.code}: {finding.message}")
            if len(self.findings) > 10:
                lines.append(f"  ... and {len(self.findings) - 10} more")
        return "\n".join(lines)

    def why(self, ref: str | Constraint) -> str:
        """Explain the role of one constraint in the conflict."""
        if self.status != Status.INFEASIBLE.value:
            return f"model status is {self.status!r}, not 'infeasible'"
        if self.iis is None:
            return "no IIS was computed"
        target = self._resolve(ref)
        in_iis = any(c is target for c in self.iis.constraints)
        if not in_iis:
            return f"'{target.name}' is not in the IIS; it is not needed for the conflict."

        active = {c.index for c in self.model.constraints if c is not target}
        trial = highs_backend.solve(
            self.model,
            options=SolveOptions(time_limit=min(30.0, max(1.0, self.elapsed * 4))),
            active_rows=active,
        )
        if trial.status is Status.INFEASIBLE:
            return (
                f"'{target.name}' is part of the conflict, but removing it alone "
                "does not restore feasibility."
            )
        return (
            f"'{target.name}' is essential: removing it restores feasibility "
            "while the other IIS members stay active."
        )

    def _resolve(self, ref: str | Constraint) -> Constraint:
        if isinstance(ref, Constraint):
            return ref
        for constraint in self.model.constraints:
            if constraint.name == ref:
                return constraint
        raise KeyError(f"unknown constraint {ref!r}")

    def to_dict(self) -> dict:
        return {
            "status": self.status,
            "backend": self.backend,
            "elapsed": round(self.elapsed, 6),
            "iis": None
            if self.iis is None
            else {
                "method": self.iis.method,
                "minimal": self.iis.minimal,
                "solves": self.iis.solves,
                "constraints": [
                    {"name": c.name, "expression": c.expression()} for c in self.iis.constraints
                ],
            },
            "findings": [asdict(f) for f in self.findings],
            "certificate": None,
            "explanation": self.explanation,
        }

    def report(self, path: str, format: str = "html") -> None:
        fmt = format.lower()
        if fmt == "json":
            text = json.dumps(self.to_dict(), indent=2, ensure_ascii=False)
        elif fmt in ("html", "htm"):
            text = self._html()
        else:
            raise ValueError(f"unsupported report format {format!r}")
        Path(path).write_text(text, encoding="utf-8")

    def _html(self) -> str:
        rows = ""
        if self.iis is not None:
            rows = "".join(
                f"<tr><td>{escape(c.name)}</td><td><code>{escape(c.expression())}</code></td></tr>"
                for c in self.iis.constraints
            )
        findings = "".join(
            f"<li><strong>[{escape(f.severity)}] {escape(f.code)}</strong> "
            f"{escape(f.message)}</li>"
            for f in self.findings
        )
        return f"""<!doctype html>
<html lang="zh-CN"><head><meta charset="utf-8">
<title>ors diagnosis report</title>
<style>
 body {{ font-family: -apple-system, system-ui, sans-serif; max-width: 900px;
        margin: 40px auto; padding: 0 20px; color: #1f2328; }}
 h1 {{ font-size: 22px; }} h2 {{ font-size: 16px; margin-top: 28px; }}
 table {{ border-collapse: collapse; width: 100%; }}
 td, th {{ border: 1px solid #d0d7de; padding: 8px 10px; text-align: left; }}
 th {{ background: #f6f8fa; }}
 code {{ font-family: ui-monospace, monospace; }}
 .meta {{ color: #57606a; }}
</style></head><body>
<h1>ors diagnosis report</h1>
<p class="meta">status: <strong>{escape(self.status)}</strong> ·
backend: {escape(self.backend)} · elapsed: {self.elapsed:.3f}s</p>
<h2>IIS</h2>
<table><thead><tr><th>constraint</th><th>expression</th></tr></thead>
<tbody>{rows}</tbody></table>
<h2>Findings</h2><ul>{findings or "<li>none</li>"}</ul>
<p class="meta">Generated by ors 0.0.1 (pre-alpha). Certificate verification is not
available for this model yet.</p>
</body></html>
"""


def _check_model(model: Model) -> list[Finding]:
    findings: list[Finding] = []
    for var in model.variables:
        if var.lb > var.ub:
            findings.append(
                Finding(
                    "error",
                    "CONTRADICTORY_BOUNDS",
                    f"variable '{var.name}' has lb={var.lb:g} > ub={var.ub:g}",
                    [var.name],
                )
            )
        if var.lb == float("-inf") and var.ub == float("inf"):
            findings.append(
                Finding("warning", "FREE_VAR", f"variable '{var.name}' is free", [var.name])
            )

    seen: dict[tuple, str] = {}
    for c in model.constraints:
        if not c.coeffs:
            findings.append(
                Finding("warning", "EMPTY_ROW", f"constraint '{c.name}' has no variables", [c.name])
            )
        for var, a in c.coeffs.items():
            if abs(a) >= 1e6:
                findings.append(
                    Finding(
                        "warning",
                        "BIG_COEF",
                        f"constraint '{c.name}' has coefficient {a:g} on '{var.name}'",
                        [c.name, var.name],
                    )
                )
            if 0 < abs(a) <= 1e-9:
                findings.append(
                    Finding(
                        "warning",
                        "TINY_COEF",
                        f"constraint '{c.name}' has tiny coefficient {a:g} on '{var.name}'",
                        [c.name, var.name],
                    )
                )
        key = (
            c.sense,
            round(c.rhs, 9),
            tuple(sorted((v.index, round(a, 9)) for v, a in c.coeffs.items())),
        )
        if key in seen:
            findings.append(
                Finding(
                    "warning",
                    "DUPLICATE_ROW",
                    f"constraint '{c.name}' duplicates '{seen[key]}'",
                    [c.name, seen[key]],
                )
            )
        else:
            seen[key] = c.name

    return findings


def _solve(
    model: Model,
    active: set[int],
    solves: int,
    deadline: float,
    options: DiagnoseOptions,
) -> tuple[Status, int]:
    remaining = deadline - time.perf_counter()
    if remaining <= 0 or solves >= options.max_solves:
        return Status.TIME_LIMIT, solves
    result = highs_backend.solve(
        model,
        options=SolveOptions(time_limit=max(0.5, remaining)),
        active_rows=active,
    )
    return result.status, solves + 1


def _compute_iis(model: Model, options: DiagnoseOptions) -> IIS:
    m = model.num_constrs
    if m == 0:
        return IIS([], True, "trivial", 0, note="no constraints; bounds are infeasible")

    deadline = time.perf_counter() + options.max_time
    method = options.method
    if method == "auto":
        method = "deletion" if m <= 200 else "additive"
    if method not in ("deletion", "additive"):
        raise ValueError(f"unknown method {method!r}")

    solves = 0
    if method == "additive":
        active: set[int] = set()
        found = False
        for constraint in model.constraints:
            active.add(constraint.index)
            status, solves = _solve(model, active, solves, deadline, options)
            if status is Status.INFEASIBLE:
                found = True
                break
            if status is Status.TIME_LIMIT:
                break
        if not found:
            return IIS([], True, method, solves, note="could not isolate a conflict")
        keep = set(active)
    else:
        keep = set(range(m))

    # Deletion filter over the current candidate set.
    complete = True
    for index in sorted(keep):
        status, solves = _solve(model, keep - {index}, solves, deadline, options)
        if status is Status.INFEASIBLE:
            keep.discard(index)
        elif status is Status.TIME_LIMIT:
            complete = False
            break

    selected = [c for c in model.constraints if c.index in keep]
    note = None
    if not selected:
        note = "variable bounds alone are infeasible"
    return IIS(selected, minimal=complete, method=method, solves=solves, note=note)


def diagnose(model: Model, options: DiagnoseOptions | None = None) -> Diagnosis:
    """Diagnose an infeasible linear model."""
    opts = options or DiagnoseOptions()
    start = time.perf_counter()

    result = highs_backend.solve(model, options=SolveOptions(time_limit=opts.max_time))
    elapsed = time.perf_counter() - start

    if result.status is not Status.INFEASIBLE:
        return Diagnosis(
            status=result.status.value,
            model=model,
            findings=_check_model(model),
            elapsed=elapsed,
        )

    iis = _compute_iis(model, opts)
    return Diagnosis(
        status=Status.INFEASIBLE.value,
        model=model,
        iis=iis,
        findings=_check_model(model),
        elapsed=time.perf_counter() - start,
        explanation=None,
    )
