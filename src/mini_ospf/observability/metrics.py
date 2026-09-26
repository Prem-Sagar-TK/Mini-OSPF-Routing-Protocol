"""
Metrics Collector for Mini-OSPF Daemon.
"""

import time
from collections import defaultdict


class MetricsCollector:
    """
    In-memory metrics accumulator tracking packet I/O, SPF performance, FSM events, and errors.
    """

    def __init__(self) -> None:
        self._counters: dict[str, int] = defaultdict(int)
        self._gauges: dict[str, float] = {}
        self._spf_durations: list[float] = []
        self._start_time: float = time.monotonic()

    def inc(self, metric: str, value: int = 1) -> None:
        self._counters[metric] += value

    def set_gauge(self, metric: str, value: float) -> None:
        self._gauges[metric] = value

    def record_spf_run(self, duration_seconds: float) -> None:
        self.inc("spf_runs_total")
        self._spf_durations.append(duration_seconds)
        self.set_gauge("spf_last_duration_ms", duration_seconds * 1000.0)

    def snapshot(self) -> dict[str, object]:
        uptime = time.monotonic() - self._start_time
        avg_spf = (
            sum(self._spf_durations) / len(self._spf_durations) * 1000.0
            if self._spf_durations
            else 0.0
        )
        return {
            "uptime_seconds": round(uptime, 2),
            "counters": dict(self._counters),
            "gauges": dict(self._gauges),
            "spf_summary": {
                "total_runs": len(self._spf_durations),
                "avg_duration_ms": round(avg_spf, 3),
                "last_duration_ms": round(self._gauges.get("spf_last_duration_ms", 0.0), 3),
            },
        }
