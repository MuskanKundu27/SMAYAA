"""Status of a value against its four limits (CLAUDE brief §9)."""

from dataclasses import dataclass
from typing import Literal

StatusLevel = Literal["good", "warn", "bad", "na"]
Direction = Literal["high", "low"]

# Extra probability points per out-of-range parameter in rule expressions (sev()).
SEVERITY_POINTS: dict[StatusLevel, int] = {"good": 0, "warn": 20, "bad": 40, "na": 0}


@dataclass(frozen=True)
class Limits:
    warn_min: float
    good_min: float
    good_max: float
    warn_max: float

    def is_ordered(self) -> bool:
        return self.warn_min <= self.good_min <= self.good_max <= self.warn_max


@dataclass(frozen=True)
class Status:
    level: StatusLevel
    direction: Direction | None = None


NO_DATA = Status("na")
GOOD = Status("good")


def status_of(value: float | None, limits: Limits | None) -> Status:
    """good inside [good_min, good_max]; warn inside the warning band; bad outside it.
    No limits → always good (shown, never alerts). No value → na."""
    if value is None:
        return NO_DATA
    if limits is None or limits.good_min <= value <= limits.good_max:
        return GOOD
    if limits.warn_min <= value <= limits.warn_max:
        return Status("warn", "high" if value > limits.good_max else "low")
    return Status("bad", "high" if value > limits.warn_max else "low")
