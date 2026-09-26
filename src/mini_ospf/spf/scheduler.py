"""
SPF Throttling and Debounce Scheduler (RFC 2328 / Industry Standard SPF Timers).
"""

import asyncio
import logging
import time
from collections.abc import Callable

logger = logging.getLogger("mini_ospf.spf.scheduler")


class SPFScheduler:
    """
    Implements SPF timer throttling to debounce bursts of LSAs and avoid CPU exhaustion.
    Parameters (in seconds):
      - init_delay: initial delay before first SPF calculation (e.g. 0.05s)
      - hold_time: minimum time between consecutive SPF runs (e.g. 0.1s), doubles on rapid events
      - max_delay: maximum hold time cap (e.g. 5.0s)
    """

    def __init__(
        self,
        spf_callback: Callable[[], None],
        init_delay: float = 0.05,
        hold_time: float = 0.1,
        max_delay: float = 5.0,
    ) -> None:
        self.spf_callback = spf_callback
        self.init_delay = init_delay
        self.hold_time = hold_time
        self.max_delay = max_delay

        self._current_hold: float = hold_time
        self._last_run_time: float = 0.0
        self._scheduled_task: asyncio.Task[None] | None = None
        self._pending: bool = False

    def trigger(self) -> None:
        """Signal that topology changed and an SPF run is required."""
        self._pending = True

        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            # Running in non-async environment (e.g. synchronous unit test)
            self._execute_spf()
            return

        if self._scheduled_task is not None and not self._scheduled_task.done():
            return

        now = time.monotonic()
        time_since_last = now - self._last_run_time

        if time_since_last >= self._current_hold:
            delay = self.init_delay
        else:
            delay = max(0.0, self._current_hold - time_since_last)

        self._scheduled_task = loop.create_task(self._delayed_run(delay))

    async def _delayed_run(self, delay: float) -> None:
        if delay > 0:
            await asyncio.sleep(delay)
        self._execute_spf()

    def _execute_spf(self) -> None:
        if not self._pending:
            return

        try:
            self.spf_callback()
        except Exception as e:
            logger.error("Error during SPF computation callback: %s", e)
        finally:
            now = time.monotonic()
            self._last_run_time = now
            self._pending = False

            # Exponential backoff on hold time
            self._current_hold = min(self.max_delay, self._current_hold * 2)

    def reset_hold(self) -> None:
        """Reset hold time back to base hold_time when network is stable."""
        self._current_hold = self.hold_time
