"""ors — explainable optimization."""

from .certificate import Certificate, CertificateTerm, VerifyResult, verify_certificate
from .diagnose import (
    IIS,
    DiagnoseOptions,
    Diagnosis,
    DiagnosisError,
    Finding,
    diagnose,
)
from .model import Constraint, ConstraintSpec, LinearExpr, Model, ModelError, Var
from .result import Result, SolveOptions, Status
from .version import __version__

__all__ = [
    "IIS",
    "Certificate",
    "CertificateTerm",
    "Constraint",
    "ConstraintSpec",
    "DiagnoseOptions",
    "Diagnosis",
    "DiagnosisError",
    "Finding",
    "LinearExpr",
    "Model",
    "ModelError",
    "Result",
    "SolveOptions",
    "Status",
    "Var",
    "VerifyResult",
    "__version__",
    "diagnose",
    "verify_certificate",
]
