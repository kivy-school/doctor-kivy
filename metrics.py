# Minimal SQLite metrics store for doctor-kivy
# Tracks:
# - renders_attempted_total
# - renders_success_total
# - renders_failure_total
# - render_duration_seconds (count/sum/min/max)
# - screenshot_bytes (count/sum/min/max)

import os
import sqlite3
import threading
from datetime import datetime, timezone

_DEFAULT_COUNTERS = (
    "renders_attempted_total",
    "renders_success_total",
    "renders_failure_total",
)


class Metrics:
    def __init__(self, db_path: str = "./metrics.db") -> None:
        _ensure_parent_dir(db_path)
        self._lock = threading.Lock()
        # autocommit mode (isolation_level=None)
        self._conn = sqlite3.connect(
            db_path, isolation_level=None, check_same_thread=False
        )
        self._conn.execute("PRAGMA journal_mode=WAL;")
        self._conn.execute("PRAGMA synchronous=NORMAL;")
        self._init_schema()

    def _init_schema(self) -> None:
        with self._conn:
            self._conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS counters (
                    name  TEXT PRIMARY KEY,
                    value INTEGER NOT NULL
                );
                CREATE TABLE IF NOT EXISTS aggs (
                    name  TEXT PRIMARY KEY,
                    count INTEGER NOT NULL,
                    sum   REAL    NOT NULL,
                    min   REAL,
                    max   REAL
                );
                CREATE TABLE IF NOT EXISTS meta (
                    k TEXT PRIMARY KEY,
                    v TEXT
                );
                """
            )
            for c in _DEFAULT_COUNTERS:
                self._conn.execute(
                    "INSERT OR IGNORE INTO counters(name,value) VALUES (?,0)", (c,)
                )

    # ---- public API ----

    def inc_attempted(self, n: int = 1) -> None:
        self._inc("renders_attempted_total", n)

    def inc_success(self, n: int = 1) -> None:
        self._inc("renders_success_total", n)

    def inc_failure(self, n: int = 1) -> None:
        self._inc("renders_failure_total", n)

    def observe_duration(self, seconds: float) -> None:
        self._observe("render_duration_seconds", float(seconds))

    def observe_screenshot_bytes(self, nbytes: int) -> None:
        self._observe("screenshot_bytes", float(nbytes))

    def snapshot(self) -> dict:
        """Return a dict with current values (optional helper)."""
        with self._lock, self._conn:
            counters = dict(
                self._conn.execute("SELECT name, value FROM counters").fetchall()
            )
            aggs_rows = self._conn.execute(
                "SELECT name, count, sum, min, max FROM aggs"
            ).fetchall()
            aggs = {
                name: {"count": cnt, "sum": s, "min": mn, "max": mx}
                for (name, cnt, s, mn, mx) in aggs_rows
            }
            last_ts = self._conn.execute(
                "SELECT v FROM meta WHERE k='last_update_ts'"
            ).fetchone()
        return {
            "version": 1,
            "counters": counters,
            "render_duration_seconds": aggs.get(
                "render_duration_seconds",
                {"count": 0, "sum": 0.0, "min": None, "max": None},
            ),
            "screenshot_bytes": aggs.get(
                "screenshot_bytes", {"count": 0, "sum": 0.0, "min": None, "max": None}
            ),
            "last_update_ts": last_ts[0] if last_ts else None,
        }

    def close(self) -> None:
        with self._lock:
            self._conn.close()

    # ---- internals ----

    def _inc(self, name: str, delta: int) -> None:
        now = _utc_iso()
        with self._lock, self._conn:
            self._conn.execute(
                """
                INSERT INTO counters(name, value) VALUES (?, ?)
                ON CONFLICT(name) DO UPDATE SET value = counters.value + excluded.value
                """,
                (name, int(delta)),
            )
            self._conn.execute(
                """
                INSERT INTO meta(k, v) VALUES('last_update_ts', ?)
                ON CONFLICT(k) DO UPDATE SET v=excluded.v
                """,
                (now,),
            )

    def _observe(self, name: str, value: float) -> None:
        now = _utc_iso()
        v = float(value)
        with self._lock, self._conn:
            self._conn.execute(
                """
                INSERT INTO aggs(name, count, sum, min, max)
                VALUES (?, 1, ?, ?, ?)
                ON CONFLICT(name) DO UPDATE SET
                    count = aggs.count + 1,
                    sum   = aggs.sum + excluded.sum,
                    min   = CASE WHEN aggs.min IS NULL OR excluded.min < aggs.min THEN excluded.min ELSE aggs.min END,
                    max   = CASE WHEN aggs.max IS NULL OR excluded.max > aggs.max THEN excluded.max ELSE aggs.max END
                """,
                (name, v, v, v),
            )
            self._conn.execute(
                """
                INSERT INTO meta(k, v) VALUES('last_update_ts', ?)
                ON CONFLICT(k) DO UPDATE SET v=excluded.v
                """,
                (now,),
            )


def _ensure_parent_dir(path: str) -> None:
    parent = os.path.dirname(os.path.abspath(path))
    if parent and not os.path.exists(parent):
        os.makedirs(parent, exist_ok=True)


def _utc_iso() -> str:
    return datetime.now(timezone.utc).isoformat()
