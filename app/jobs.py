"""What is running right now, and what has just finished.

In memory on purpose. A row on disk can lie: a process killed mid-run leaves
"in progress" behind forever, and reading it then needs a rule about when to
stop believing it. A registry in memory cannot lie — if the process restarted,
nothing is running, by definition. One uvicorn process per deployment is what
makes this the simple answer rather than the naive one.

The finished slot matters as much as the running one. Until now the UI could
only say a job had *started*: you clicked scan, landed on a banner, changed page
and lost it, and nothing ever told you it was over. A completion is worth
announcing for a couple of minutes and then not at all — after that the queue
and its badge are where that information lives.
"""
import threading
import time
from contextlib import contextmanager

# How long a completed job stays worth mentioning. Long enough to catch the eye
# of whoever started it, short enough that the nightly run is not still being
# announced at nine in the morning.
FINISHED_TTL = 180.0

_lock = threading.Lock()
_running: dict[str, dict] = {}
_finished: dict | None = None


def progress(key: str, detail: str) -> None:
    """Update what a running job is doing. Silently ignored when the job is not
    registered, so a function can call it whether or not it was tracked."""
    with _lock:
        if key in _running:
            _running[key]["detail"] = detail


@contextmanager
def track(key: str, label: str):
    """Register a job for as long as it runs, and its outcome for a while after.

    The `finally` is the point: a job that raises still has to disappear from
    the registry, or one failure would leave the toast claiming forever that
    something is running.
    """
    with _lock:
        _running[key] = {"key": key, "label": label, "started": time.time(), "detail": ""}
    outcome = "done"
    try:
        yield
    except Exception:
        outcome = "failed"
        raise
    finally:
        with _lock:
            job = _running.pop(key, None)
            global _finished
            _finished = {
                "key": key, "label": label, "outcome": outcome,
                "detail": (job or {}).get("summary", ""),
                "at": time.time(),
            }


def summarize(key: str, summary: str) -> None:
    """What to say once the job is over. Set by the caller, which is the only
    party that knows what the result meant."""
    with _lock:
        if key in _running:
            _running[key]["summary"] = summary


def snapshot() -> dict:
    """Everything the toast needs: what is running, and what just finished."""
    now = time.time()
    with _lock:
        running = [
            {"label": j["label"], "detail": j["detail"],
             "seconds": int(now - j["started"])}
            for j in sorted(_running.values(), key=lambda j: j["started"])
        ]
        finished = None
        if _finished and now - _finished["at"] < FINISHED_TTL:
            finished = {"label": _finished["label"], "outcome": _finished["outcome"],
                        "detail": _finished["detail"]}
    return {"running": running, "finished": finished}


def clear() -> None:
    """Tests only."""
    global _finished
    with _lock:
        _running.clear()
        _finished = None
