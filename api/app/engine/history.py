"""Time functions: let formulas and rules look back at a plant's recent readings.

Engineering KPIs such as "ΔP rate of change", "fan response" or "time since the last cleaning"
need history, not just the newest values. These functions give every formula and rule that
ability with one general mechanism, so new trend KPIs are configuration, not code:

    change('k', h)        k now minus k at the oldest reading in the last h hours
                          (needs readings spanning at least 10 % of the window)
    rate('k', h)          that change per hour (e.g. bar/h); times 24 for per day
    avg('k', h)           average of k over the last h hours (including now)
    total('k', h)         time integral of k over the last h hours (m³/h → m³)
    events('e', h)        how many times event e started in the last h hours
    hours_since('e')      hours since event e last started
    before_event('k','e') k just before event e last started (e.g. ΔP before cleaning)
    after_event('k','e')  k just after event e last ended (e.g. ΔP after cleaning)
    event_interval('e')   hours between the last two starts of event e (cleaning interval)

An "event" parameter is an on/off input such as cleaning status: on (≥ 0.5) or off.
Like everything in the engine: no data, not enough history or a zero time span gives None
("insufficient data"), never an error. "Now" is the time of the reading being calculated.
"""

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import datetime
from itertools import pairwise

Value = float | bool | str | list[object] | None

MAX_WINDOW_HOURS = 24 * 90  # longest look-back a formula may ask for
EVENT_LOOKBACK_HOURS = 24 * 30  # history loaded for the event functions
WINDOW_FUNCTIONS = ("change", "rate", "avg", "total", "events")
EVENT_FUNCTIONS = ("events", "hours_since", "event_interval", "before_event", "after_event")
TIME_FUNCTIONS = ("change", "rate", "avg", "total", "events", "hours_since", "event_interval",
                  "before_event", "after_event")  # fmt: skip
ON = 0.5  # event parameters: a value at or above this means "on"
# change() and rate() need readings covering at least this share of their window.
MIN_SPAN_FRACTION = 0.1


def _hours(a: datetime, b: datetime) -> float:
    return (b - a).total_seconds() / 3600


def _number(value: object) -> float | None:
    if isinstance(value, int | float) and not isinstance(value, bool):
        return float(value)
    return None


@dataclass(frozen=True)
class History:
    """Earlier readings of one plant, oldest first, all strictly before `now`."""

    now: datetime
    points: Sequence[tuple[datetime, Mapping[str, object]]] = field(default_factory=tuple)


class TimeFunctions:
    """Time functions bound to a history and to the current values being calculated."""

    def __init__(self, history: History | None, current: Mapping[str, float | None]):
        self._history = history
        self._current = current

    # --- helpers -------------------------------------------------------------------------------

    def _window(self, hours: Value) -> float | None:
        h = _number(hours)
        if h is None or h <= 0:
            return None
        return min(h, MAX_WINDOW_HOURS)

    def _series(self, key: Value, hours: float | None) -> list[tuple[datetime, float]]:
        """(time, value) of key inside the window, plus the current value; oldest first."""
        if self._history is None:
            return []
        now, name = self._history.now, str(key)
        series = [
            (t, v)
            for t, values in self._history.points
            if (hours is None or _hours(t, now) <= hours)
            and (v := _number(values.get(name))) is not None
        ]
        current = _number(self._current.get(name))
        if current is not None:
            series.append((now, current))
        return series

    def _states(self, event: Value) -> list[tuple[datetime, bool]]:
        """(time, on?) for the event parameter over all loaded history plus now."""
        return [(t, v >= ON) for t, v in self._series(event, None)]

    def _last_start(self, states: list[tuple[datetime, bool]]) -> int | None:
        """Index of the reading where the event last switched on."""
        last = None
        previous = False
        for i, (_, on) in enumerate(states):
            if on and not previous:
                last = i
            previous = on
        return last

    # --- the functions -------------------------------------------------------------------------

    def _endpoints(self, key: Value, hours: Value) -> tuple[float, float, float] | None:
        """(oldest value, current value, hours between them) for a trend over the window, or
        None when the readings don't span enough of it. Readings seconds apart (autosave)
        would otherwise turn tiny differences into absurd rates."""
        window = self._window(hours)
        series = self._series(key, window)
        if window is None or len(series) < 2 or series[-1][0] != self._now():
            return None
        elapsed = _hours(series[0][0], series[-1][0])
        if elapsed < window * MIN_SPAN_FRACTION:
            return None
        return series[0][1], series[-1][1], elapsed

    def change(self, key: Value, hours: Value) -> Value:
        ends = self._endpoints(key, hours)
        return None if ends is None else ends[1] - ends[0]

    def rate(self, key: Value, hours: Value) -> Value:
        ends = self._endpoints(key, hours)
        return None if ends is None else (ends[1] - ends[0]) / ends[2]

    def avg(self, key: Value, hours: Value) -> Value:
        series = self._series(key, self._window(hours))
        return sum(v for _, v in series) / len(series) if series else None

    def total(self, key: Value, hours: Value) -> Value:
        series = self._series(key, self._window(hours))
        if len(series) < 2:
            return None
        return sum((v0 + v1) / 2 * _hours(t0, t1) for (t0, v0), (t1, v1) in pairwise(series))

    def events(self, event: Value, hours: Value) -> Value:
        window = self._window(hours)
        if window is None or self._history is None:
            return None
        now = self._now()
        count, previous = 0, False
        for t, on in self._states(event):
            if on and not previous and _hours(t, now) <= window:
                count += 1
            previous = on
        return float(count)

    def hours_since(self, event: Value) -> Value:
        states = self._states(event)
        start = self._last_start(states)
        return None if start is None else _hours(states[start][0], self._now())

    def event_interval(self, event: Value) -> Value:
        starts = []
        previous = False
        for t, on in self._states(event):
            if on and not previous:
                starts.append(t)
            previous = on
        return _hours(starts[-2], starts[-1]) if len(starts) >= 2 else None

    def before_event(self, key: Value, event: Value) -> Value:
        states = self._states(event)
        start = self._last_start(states)
        if start is None:
            return None
        values = [v for t, v in self._series(key, None) if t < states[start][0]]
        return values[-1] if values else None

    def after_event(self, key: Value, event: Value) -> Value:
        states = self._states(event)
        start = self._last_start(states)
        if start is None:
            return None
        end = next((t for t, on in states[start:] if not on), None)
        if end is None:  # still cleaning
            return None
        values = [v for t, v in self._series(key, None) if t >= end]
        return values[0] if values else None

    def _now(self) -> datetime:
        # Only called through functions(), which never binds these methods without a history.
        return self._history.now  # type: ignore[union-attr]

    def functions(self) -> dict[str, Callable[..., Value]]:
        if self._history is None:
            return dict.fromkeys(TIME_FUNCTIONS, _no_history)
        return {name: getattr(self, name) for name in TIME_FUNCTIONS}


def _no_history(*_args: Value) -> Value:
    return None
