"""ors — explainable optimization."""

from .diagnose import (
    DiagnoseOptions,
    Diagnosis,
    DiagnosisError,
    Finding,
    IIS,
    diagnose,
)
from .model import Constraint, ConstraintSpec, LinearExpr, Model, ModelError, Var
from .result import Result, SolveOptions, Status

__version__ = "0.0.1"

__all__ = [
    "Constraint",
    "ConstraintSpec",
    "DiagnoseOptions",
    "Diagnosis",
    "DiagnosisError",
    "Finding",
    "IIS",
    "LinearExpr",
    "Model",
    "ModelError",
    "Result",
    "SolveOptions",
    "Status",
    "Var",
    "diagnose",
    "__version__",
]
