"""Solve results and options."""

from __future__ import annotations

from dataclasses import dataclass, field

from .status import Status


@dataclass
class SolveOptions:
    """Options passed to :meth:`ors.Model.optimize`."""

    time_limit: float | None = None
    """Wall-clock limit in seconds. ``None`` means backend default."""

    threads: int | None = None
    """Number of threads. ``None`` means backend default."""

    verbose: bool = False
    """Forward backend log output to stdout."""


@dataclass
class Result:
    """Outcome of a solve.

    ``x`` and ``dual`` are keyed by user-facing names, not matrix indices.
    """

    status: Status
    objective: float | None = None
    x: dict[str, float] | None = None
    dual: dict[str, float] | None = None
    iterations: int = 0
    runtime: float = 0.0
    backend: str = "unknown"
    gap: float | None = None
    message: str | None = None

    @property
    def optimal(self) -> bool:
        return self.status is Status.OPTIMAL

    def __repr__(self) -> str:  # pragma: no cover - cosmetic
        return (
            f"Result(status={self.status.value!r}, objective={self.objective!r}, "
            f"runtime={self.runtime:.3f}s, backend={self.backend!r})"
        )
