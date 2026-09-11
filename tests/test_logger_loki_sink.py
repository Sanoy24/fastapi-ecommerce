"""
Tests for the Loki log sink's enqueue=True (app/core/logger.py).

The stdout and file handlers both already used enqueue=True; the Loki
handler didn't. Every log call reaching that sink ran LokiSink.write()
synchronously — including the one call/response line
app.middleware.request_logger.LoggingMiddleware writes for every single
HTTP request — so a real network POST to Loki happened inline on the
request-handling path. A slow or unreachable Loki meant every request in
the app got slow, not just the logging.

app/core/logger.py only registers the Loki sink at all when
"pytest" not in sys.modules, so it's never actually wired up during this
suite's own run — there's no live sink here to attach a slow fake handler
to and measure. This file instead:

1. Proves the underlying mechanism (loguru's enqueue=True genuinely
   decouples the caller from a slow sink) directly, independent of this
   app's specific config, so the claim "enqueue=True fixes this class of
   bug" is verified rather than assumed.
2. Statically confirms app/core/logger.py's actual Loki registration
   passes enqueue=True — the real regression guard for this fix, checking
   the source of the specific call site since it can't be exercised live
   under the module's own pytest guard.
"""
import inspect
import re
import time

from loguru import logger as loguru_logger


class TestEnqueueTrueDecouplesFromASlowSink:
    """Proves the mechanism app/core/logger.py's fix relies on, using a
    throwaway logger instance rather than the app's own (which never
    registers its Loki sink under pytest — see the module docstring)."""

    def test_a_slow_sink_without_enqueue_blocks_the_caller(self):
        test_logger = loguru_logger.bind()
        handler_id = test_logger.add(lambda msg: time.sleep(0.3), enqueue=False)
        try:
            started = time.monotonic()
            test_logger.info("hello")
            elapsed = time.monotonic() - started
        finally:
            test_logger.remove(handler_id)

        assert elapsed >= 0.3, "a synchronous sink should block the caller for its own duration"

    def test_enqueue_true_returns_immediately_regardless_of_sink_speed(self):
        test_logger = loguru_logger.bind()
        processed = []
        handler_id = test_logger.add(
            lambda msg: (time.sleep(0.5), processed.append(msg)), enqueue=True
        )
        try:
            started = time.monotonic()
            test_logger.info("hello")
            elapsed = time.monotonic() - started

            # The call returns almost instantly — the 0.5s sink is still
            # running on loguru's background thread at this point.
            assert elapsed < 0.1, f"logger call took {elapsed:.3f}s — enqueue=True should return immediately"
            assert processed == [], "sink should not have run yet at this point"

            # ...but the message isn't lost — it completes shortly after.
            deadline = time.monotonic() + 2
            while not processed and time.monotonic() < deadline:
                time.sleep(0.05)
            assert len(processed) == 1, "the enqueued log call should still be delivered, just asynchronously"
        finally:
            test_logger.remove(handler_id)


class TestLokiSinkRegistrationUsesEnqueue:
    """The actual regression guard: app/core/logger.py's real Loki
    registration must pass enqueue=True, same as its other two handlers."""

    def test_loki_handler_registration_passes_enqueue_true(self):
        import app.core.logger as logger_module

        source = inspect.getsource(logger_module)
        # Find the specific logger.add(LokiSink(...), ...) call rather than
        # just grepping the whole file for "enqueue=True" — the stdout and
        # file handlers already have it; asserting on the file overall
        # wouldn't catch a regression in the Loki line specifically.
        match = re.search(r"logger\.add\(LokiSink\([^)]*\),[^)]*\)", source, re.DOTALL)
        assert match, "could not find the LokiSink registration in app/core/logger.py"
        assert "enqueue=True" in match.group(0), (
            f"LokiSink registration is missing enqueue=True: {match.group(0)!r}"
        )
