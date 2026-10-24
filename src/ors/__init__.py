"""ors — explainable optimization."""

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

__version__ = "0.0.1"

__all__ = [
    "IIS",
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
    "__version__",
    "diagnose",
]
