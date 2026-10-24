"""Solver status codes."""

from __future__ import annotations

from enum import Enum


class Status(str, Enum):
    """Outcome of an optimization run.

    Only ``OPTIMAL`` guarantees that a primal feasible solution is available.
    ``INF_OR_UNB`` means the backend could not distinguish the two cases.
    """

    OPTIMAL = "optimal"
    INFEASIBLE = "infeasible"
    UNBOUNDED = "unbounded"
    INF_OR_UNB = "infeasible_or_unbounded"
    TIME_LIMIT = "time_limit"
    ITERATION_LIMIT = "iteration_limit"
    NUMERICAL = "numerical"
    ERROR = "error"

    @property
    def has_solution(self) -> bool:
        return self in (Status.OPTIMAL, Status.TIME_LIMIT)

    @property
    def is_infeasible(self) -> bool:
        return self is Status.INFEASIBLE
