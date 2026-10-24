"""Farkas certificates for infeasible linear programs.

The certificate is a nonnegative combination of the model's inequalities that
cancels every variable and leaves a negative constant::

    sum_k lambda_k * (a_k x <= b_k)  =>  0 <= sum_k lambda_k b_k < 0

which is a contradiction, hence the model is infeasible. The multipliers are
computed by solving an auxiliary LP, then re-checked here without trusting the
solver that produced them.
"""

from __future__ import annotations

import hashlib
import json
import math
from collections.abc import Sequence
from dataclasses import dataclass, field
from pathlib import Path

from .model import Constraint, LinearExpr, Model, Var
from .result import SolveOptions, Status

TOL = 1e-7
CHECKER = "ors.verify.farkas@1"

_TERM_KINDS = ("constraint_upper", "constraint_lower", "bound_upper", "bound_lower")


@dataclass
class CertificateTerm:
    kind: str
    name: str
    multiplier: float = 0.0

    def label(self) -> str:
        if self.kind == "constraint_upper":
            return f"{self.name} (<= side)"
        if self.kind == "constraint_lower":
            return f"{self.name} (>= side)"
        if self.kind == "bound_upper":
            return f"{self.name} <= upper"
        if self.kind == "bound_lower":
            return f"{self.name} >= lower"
        return f"{self.kind}:{self.name}"


@dataclass
class Certificate:
    kind: str = "farkas"
    terms: list[CertificateTerm] = field(default_factory=list)
    residual: float = 0.0
    value: float = 0.0
    verified: bool = False
    checker: str = CHECKER
    model_hash: str = ""

    def summary(self) -> str:
        lines = [
            (
                f"certificate: {self.kind} verified={self.verified} "
                f"value={self.value:.6g} residual={self.residual:.1e}"
            )
        ]
        for term in self.terms:
            lines.append(f"  {term.multiplier:.6g} x {term.label()}")
        return "\n".join(lines)

    def to_dict(self) -> dict:
        return {
            "kind": self.kind,
            "version": 1,
            "checker": self.checker,
            "model_hash": self.model_hash,
            "residual": self.residual,
            "value": self.value,
            "verified": self.verified,
            "terms": [
                {"kind": t.kind, "name": t.name, "multiplier": t.multiplier} for t in self.terms
            ],
        }

    @classmethod
    def from_dict(cls, data: dict) -> Certificate:
        terms = [
            CertificateTerm(
                kind=str(item["kind"]),
                name=str(item["name"]),
                multiplier=float(item.get("multiplier", 0.0)),
            )
            for item in data.get("terms", [])
        ]
        return cls(
            kind=str(data.get("kind", "farkas")),
            terms=terms,
            residual=float(data.get("residual", 0.0)),
            value=float(data.get("value", 0.0)),
            verified=bool(data.get("verified", False)),
            checker=str(data.get("checker", CHECKER)),
            model_hash=str(data.get("model_hash", "")),
        )

    def to_json(self, path: str) -> None:
        Path(path).write_text(
            json.dumps(self.to_dict(), indent=2, ensure_ascii=False), encoding="utf-8"
        )

    @classmethod
    def from_json(cls, path: str) -> Certificate:
        return cls.from_dict(json.loads(Path(path).read_text(encoding="utf-8")))


@dataclass
class VerifyResult:
    verified: bool
    reason: str
    residual: float = 0.0
    value: float = 0.0
    hash_match: bool = True


def model_fingerprint(model: Model) -> str:
    """Stable hash of the model, used to bind a certificate to its model."""
    payload = {
        "sense": model.sense,
        "vars": [[v.name, v.lb.hex(), v.ub.hex(), v.vtype] for v in model.variables],
        "objective": [
            [v.name, a.hex()]
            for v, a in sorted(model.objective.coeffs.items(), key=lambda kv: kv[0].index)
        ],
        "constraints": [
            [
                c.name,
                c.sense,
                c.rhs.hex(),
                [
                    [v.name, a.hex()]
                    for v, a in sorted(c.coeffs.items(), key=lambda kv: kv[0].index)
                ],
            ]
            for c in model.constraints
        ],
    }
    blob = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return "sha256:" + hashlib.sha256(blob.encode("utf-8")).hexdigest()


def _find_constraint(model: Model, name: str) -> Constraint:
    for constraint in model.constraints:
        if constraint.name == name:
            return constraint
    raise KeyError(f"unknown constraint {name!r}")


def _find_var(model: Model, name: str) -> Var:
    for var in model.variables:
        if var.name == name:
            return var
    raise KeyError(f"unknown variable {name!r}")


def _term_inequality(model: Model, term: CertificateTerm) -> tuple[dict[Var, float], float]:
    """Return ``(a, b)`` for the inequality ``a x <= b`` behind a term."""
    if term.kind == "constraint_upper":
        constraint = _find_constraint(model, term.name)
        return dict(constraint.coeffs), constraint.rhs
    if term.kind == "constraint_lower":
        constraint = _find_constraint(model, term.name)
        return {v: -a for v, a in constraint.coeffs.items()}, -constraint.rhs
    if term.kind == "bound_upper":
        var = _find_var(model, term.name)
        if not math.isfinite(var.ub):
            raise ValueError(f"variable {var.name!r} has no finite upper bound")
        return {var: 1.0}, var.ub
    if term.kind == "bound_lower":
        var = _find_var(model, term.name)
        if not math.isfinite(var.lb):
            raise ValueError(f"variable {var.name!r} has no finite lower bound")
        return {var: -1.0}, -var.lb
    raise ValueError(f"unknown term kind {term.kind!r}")


def _conflict_terms(
    model: Model, constraints: Sequence[Constraint]
) -> tuple[list[CertificateTerm], set[Var]]:
    terms: list[CertificateTerm] = []
    relevant: set[Var] = set()
    for constraint in constraints:
        relevant.update(constraint.coeffs)
        if constraint.sense in ("<=", "=="):
            terms.append(CertificateTerm("constraint_upper", constraint.name))
        if constraint.sense in (">=", "=="):
            terms.append(CertificateTerm("constraint_lower", constraint.name))
    for var in model.variables:
        if var.lb > var.ub:
            relevant.add(var)
    for var in sorted(relevant, key=lambda v: v.index):
        if math.isfinite(var.ub):
            terms.append(CertificateTerm("bound_upper", var.name))
        if math.isfinite(var.lb):
            terms.append(CertificateTerm("bound_lower", var.name))
    return terms, relevant


def build_certificate(
    model: Model,
    constraints: Sequence[Constraint],
    max_time: float = 10.0,
) -> Certificate | None:
    """Compute a Farkas certificate for the given (infeasible) subsystem.

    Returns ``None`` when no certificate could be produced or verified.
    """
    terms, relevant = _conflict_terms(model, constraints)
    if not terms:
        return None
    try:
        inequalities = [_term_inequality(model, term) for term in terms]
    except (KeyError, ValueError):
        return None

    aux = Model("farkas_certificate")
    multipliers = [aux.add_var(lb=0.0, name=f"lam[{k}]") for k in range(len(terms))]

    for var in sorted(relevant, key=lambda v: v.index):
        balance = LinearExpr()
        for k, (coeffs, _) in enumerate(inequalities):
            a = coeffs.get(var, 0.0)
            if a:
                balance = balance + a * multipliers[k]
        aux.add_constr(balance.eq(0.0), name=f"balance_{var.name}")

    aux.add_constr(sum(multipliers, LinearExpr()).eq(1.0), name="normalize")

    objective = LinearExpr()
    for k, (_, rhs) in enumerate(inequalities):
        if rhs:
            objective = objective + rhs * multipliers[k]
    aux.set_objective(objective, sense="min")

    result = aux.optimize(SolveOptions(time_limit=max(1.0, max_time)))
    if result.status is not Status.OPTIMAL or result.x is None:
        return None
    if result.objective is None or result.objective > -1e-9:
        return None

    kept = []
    for k, term in enumerate(terms):
        value = max(0.0, result.x[multipliers[k].name])
        if value > 1e-12:
            kept.append(CertificateTerm(term.kind, term.name, value))
    if not kept:
        return None

    certificate = Certificate(
        kind="farkas",
        terms=kept,
        model_hash=model_fingerprint(model),
    )
    check = verify_certificate(model, certificate, allow_hash_mismatch=True)
    certificate.residual = check.residual
    certificate.value = check.value
    certificate.verified = check.verified
    return certificate if check.verified else None


def verify_certificate(
    model: Model,
    certificate: Certificate,
    tol: float = TOL,
    allow_hash_mismatch: bool = False,
) -> VerifyResult:
    """Independently check a certificate against a model.

    The check does not call a solver: it only does sparse linear algebra on the
    multipliers and the model data.
    """
    hash_match = True
    if certificate.model_hash:
        hash_match = certificate.model_hash == model_fingerprint(model)
    if not hash_match and not allow_hash_mismatch:
        return VerifyResult(False, "model hash mismatch", hash_match=False)

    if certificate.kind != "farkas":
        return VerifyResult(
            False, f"unsupported certificate kind {certificate.kind!r}", hash_match=hash_match
        )
    if not certificate.terms:
        return VerifyResult(False, "empty certificate", hash_match=hash_match)

    total: dict[Var, float] = {}
    value = 0.0
    lam_sum = 0.0
    max_coef = 0.0
    for term in certificate.terms:
        if not math.isfinite(term.multiplier) or term.multiplier < -tol:
            return VerifyResult(
                False, f"invalid multiplier on {term.label()}", hash_match=hash_match
            )
        if term.multiplier <= 0.0:
            continue
        try:
            coeffs, rhs = _term_inequality(model, term)
        except (KeyError, ValueError) as exc:
            return VerifyResult(False, f"unknown term {term.label()}: {exc}", hash_match=hash_match)
        for var, a in coeffs.items():
            total[var] = total.get(var, 0.0) + term.multiplier * a
            max_coef = max(max_coef, abs(a))
        value += term.multiplier * rhs
        lam_sum += term.multiplier

    if lam_sum <= tol:
        return VerifyResult(False, "all multipliers are zero", hash_match=hash_match)

    residual = max((abs(x) for x in total.values()), default=0.0)
    scale = max(1.0, lam_sum * max(1.0, max_coef))
    if residual > tol * scale:
        reason = f"dual residual too large ({residual:.3g} > {tol * scale:.3g})"
        return VerifyResult(False, reason, residual, value, hash_match)
    if value > -tol * scale:
        reason = f"certificate value is not negative ({value:.3g})"
        return VerifyResult(False, reason, residual, value, hash_match)
    return VerifyResult(True, "ok", residual, value, hash_match)
