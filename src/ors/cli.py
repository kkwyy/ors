"""Command line interface."""

from __future__ import annotations

import argparse
import json
import sys

from . import __version__
from .certificate import Certificate, verify_certificate
from .diagnose import DiagnoseOptions
from .model import Model, ModelError
from .result import SolveOptions, Status

_EXIT = {
    Status.OPTIMAL: 0,
    Status.INFEASIBLE: 1,
    Status.UNBOUNDED: 2,
    Status.INF_OR_UNB: 2,
}


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="ors",
        description="Explainable optimization: diagnose infeasible linear models.",
    )
    parser.add_argument("--version", action="version", version=f"ors {__version__}")
    sub = parser.add_subparsers(dest="command", required=True)

    solve = sub.add_parser("solve", help="solve an MPS/LP model")
    solve.add_argument("model")
    solve.add_argument("--time-limit", type=float, default=None)

    diag = sub.add_parser("diagnose", help="explain why a model is infeasible")
    diag.add_argument("model")
    diag.add_argument("--time-limit", type=float, default=60.0)
    diag.add_argument("--method", choices=["auto", "deletion", "additive"], default="auto")
    diag.add_argument("--report", metavar="PATH", default=None)
    diag.add_argument("--certificate", metavar="PATH", default=None)
    diag.add_argument("--format", choices=["text", "json"], default="text")

    diff = sub.add_parser("diff", help="compare two model versions (not implemented)")
    diff.add_argument("old")
    diff.add_argument("new")

    verify = sub.add_parser("verify", help="verify a Farkas certificate against a model")
    verify.add_argument("certificate")
    verify.add_argument("model")
    verify.add_argument("--allow-hash-mismatch", action="store_true")

    return parser


def _solve(args: argparse.Namespace) -> int:
    model = Model.read(args.model)
    result = model.optimize(SolveOptions(time_limit=args.time_limit))
    print(f"status:    {result.status.value}")
    if result.objective is not None:
        print(f"objective: {result.objective:.10g}")
    print(f"runtime:   {result.runtime:.3f}s")
    return _EXIT.get(result.status, 3)


def _diagnose(args: argparse.Namespace) -> int:
    model = Model.read(args.model)
    diagnosis = model.diagnose(DiagnoseOptions(method=args.method, max_time=args.time_limit))
    if args.format == "json":
        print(json.dumps(diagnosis.to_dict(), indent=2, ensure_ascii=False))
    else:
        print(diagnosis.summary())
    if args.report:
        fmt = "json" if args.report.endswith(".json") else "html"
        diagnosis.report(args.report, format=fmt)
        print(f"report written to {args.report}")
    if args.certificate:
        if diagnosis.certificate is None:
            print("no certificate available", file=sys.stderr)
        else:
            diagnosis.certificate.to_json(args.certificate)
            print(f"certificate written to {args.certificate}")
    return 1 if diagnosis.status == Status.INFEASIBLE.value else 0


def _verify(args: argparse.Namespace) -> int:
    model = Model.read(args.model)
    certificate = Certificate.from_json(args.certificate)
    check = verify_certificate(model, certificate, allow_hash_mismatch=args.allow_hash_mismatch)
    if certificate.model_hash:
        print(f"model hash: {'match' if check.hash_match else 'MISMATCH'}")
    print(f"verified:  {check.verified}")
    print(f"reason:    {check.reason}")
    print(f"residual:  {check.residual:.3e}")
    print(f"value:     {check.value:.6g}")
    return 0 if check.verified else 1


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    try:
        if args.command == "solve":
            return _solve(args)
        if args.command == "diagnose":
            return _diagnose(args)
        if args.command == "verify":
            return _verify(args)
    except ModelError as exc:
        print(f"error: {exc}", file=sys.stderr)
        if exc.hint:
            print(f"hint:  {exc.hint}", file=sys.stderr)
        return 4
    except FileNotFoundError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 4

    print(f"'{args.command}' is not implemented in {__version__}", file=sys.stderr)
    return 4


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
