"""Portable Twelve Data HTTPS client — free-tier safe, runs anywhere (incl. GitHub Actions).

Enforces the $0 / free-plan guardrails (DECISIONS D-003): 8 requests/min and 800/day.
The daily counter is persisted to disk so it is correct across separate Actions runs on
the same UTC day (idempotent budget). If the key is missing or the daily budget is spent,
it raises a typed error the caller turns into a BLOCKERS entry + clean exit — it never
fabricates data to keep a pipeline green.

Only the standard library + requests + pandas are used, so it is identical off-peak and
interactively. All timestamps are returned in UTC, indexed by bar OPEN, ascending.
"""
from __future__ import annotations

import json
import os
import time
from collections import deque
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import requests

BASE = "https://api.twelvedata.com"


class TwelveDataError(RuntimeError):
    pass


class MissingKeyError(TwelveDataError):
    pass


class BudgetExhausted(TwelveDataError):
    pass


class TwelveDataClient:
    def __init__(self, usage_path: str | Path, per_minute: int = 8, per_day: int = 800,
                 session: requests.Session | None = None):
        self.key = os.environ.get("TWELVEDATA_API_KEY", "").strip()
        if not self.key:
            raise MissingKeyError(
                "TWELVEDATA_API_KEY is not set. Add it as a GitHub Secret (and a local env "
                "var for local runs). See research/BLOCKERS.md B-001.")
        self.per_minute = int(per_minute)
        self.per_day = int(per_day)
        self.usage_path = Path(usage_path)
        self.usage_path.parent.mkdir(parents=True, exist_ok=True)
        self._calls = deque()                     # monotonic timestamps of recent calls
        self._s = session or requests.Session()
        self._usage = self._load_usage()

    # ---- daily budget (persisted, UTC-day keyed) ----
    def _today(self) -> str:
        return datetime.now(timezone.utc).strftime("%Y-%m-%d")

    def _load_usage(self) -> dict:
        try:
            u = json.loads(self.usage_path.read_text("utf-8"))
        except Exception:
            u = {}
        return u if isinstance(u, dict) else {}

    def _save_usage(self):
        try:
            self.usage_path.write_text(json.dumps(self._usage), encoding="utf-8")
        except Exception:
            pass

    def calls_today(self) -> int:
        return int(self._usage.get(self._today(), 0))

    def remaining_today(self) -> int:
        return max(0, self.per_day - self.calls_today())

    # ---- rate limiting (<= per_minute in any trailing 60s) ----
    def _throttle(self):
        now = time.monotonic()
        while self._calls and now - self._calls[0] > 60:
            self._calls.popleft()
        if len(self._calls) >= self.per_minute:
            sleep_for = 60 - (now - self._calls[0]) + 0.25
            if sleep_for > 0:
                time.sleep(sleep_for)
            now = time.monotonic()
            while self._calls and now - self._calls[0] > 60:
                self._calls.popleft()

    def _spend(self):
        if self.remaining_today() <= 0:
            raise BudgetExhausted(
                f"Twelve Data daily free budget ({self.per_day}) exhausted for {self._today()}. "
                "Stopping (DECISIONS D-003). Resume tomorrow or raise the budget.")
        self._throttle()
        self._calls.append(time.monotonic())
        t = self._today()
        self._usage[t] = self.calls_today() + 1
        self._save_usage()

    # ---- endpoints ----
    def time_series(self, symbol: str, interval: str, outputsize: int = 5000) -> pd.DataFrame:
        """Return OHLCV as a UTC-indexed ascending DataFrame (open,high,low,close,volume)."""
        self._spend()
        params = {
            "symbol": symbol, "interval": interval, "outputsize": int(outputsize),
            "timezone": "UTC", "order": "ASC", "format": "JSON", "apikey": self.key,
        }
        r = self._s.get(f"{BASE}/time_series", params=params, timeout=30)
        r.raise_for_status()
        js = r.json()
        if isinstance(js, dict) and js.get("status") == "error":
            raise TwelveDataError(f"{symbol} {interval}: {js.get('message', js)}")
        values = js.get("values") if isinstance(js, dict) else None
        if not values:
            raise TwelveDataError(f"{symbol} {interval}: empty response ({js})")
        df = pd.DataFrame(values)
        df["time"] = pd.to_datetime(df["datetime"], utc=True).dt.tz_localize(None)
        for c in ("open", "high", "low", "close"):
            df[c] = pd.to_numeric(df[c], errors="coerce")
        df["volume"] = pd.to_numeric(df.get("volume", 0), errors="coerce").fillna(0)
        df = df[["time", "open", "high", "low", "close", "volume"]].dropna(
            subset=["open", "high", "low", "close"]).sort_values("time").reset_index(drop=True)
        return df
