"""In-process operational counters (PHASE_09.md G, P9-M3): enough for a health probe and an
external alert rule without a metrics stack. Counters are per process and reset on restart; they
carry no tenant, user or request content. The alert workflow reads `/health/metrics` and compares
the error ratio and the failure counters between two probes."""

from __future__ import annotations

import time
from collections import Counter
from threading import Lock

_STARTED = time.time()
_lock = Lock()
_counters: Counter[str] = Counter()


def increment(name: str, amount: int = 1) -> None:
    with _lock:
        _counters[name] += amount


def snapshot() -> dict[str, object]:
    with _lock:
        counters = dict(_counters)
    requests_total = sum(v for k, v in counters.items() if k.startswith("http_responses_"))
    errors_5xx = counters.get("http_responses_5xx", 0)
    return {
        "uptime_seconds": int(time.time() - _STARTED),
        "http_responses_total": requests_total,
        "http_responses_5xx": errors_5xx,
        "http_5xx_ratio": round(errors_5xx / requests_total, 4) if requests_total else 0.0,
        "http_responses_429": counters.get("http_responses_429", 0),
        "auth_login_failures": counters.get("auth_login_failures", 0),
        "auth_login_throttled": counters.get("auth_login_throttled", 0),
        "auth_password_resets": counters.get("auth_password_resets", 0),
        "sync_push_operations": counters.get("sync_push_operations", 0),
        "sync_push_rejected": counters.get("sync_push_rejected", 0),
        "backup_runs": counters.get("backup_runs", 0),
        "backup_failures": counters.get("backup_failures", 0),
        "mail_failures": counters.get("mail_failures", 0),
        "reminders_sent": counters.get("reminders_sent", 0),
        "reminder_failures": counters.get("reminder_failures", 0),
        "job_failures": counters.get("job_failures", 0),
        "otp_sent": counters.get("otp_sent", 0),
        "otp_verified": counters.get("otp_verified", 0),
        "otp_wrong": counters.get("otp_wrong", 0),
        "otp_locked": counters.get("otp_locked", 0),
        "otp_throttled": counters.get("otp_throttled", 0),
        "otp_delivery_failures": counters.get("otp_delivery_failures", 0),
    }


def reset_for_tests() -> None:
    with _lock:
        _counters.clear()
