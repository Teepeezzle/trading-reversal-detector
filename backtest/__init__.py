"""Replay backtester for the deployed reversal-signal logic.

This package deliberately imports the production functions from ``src`` so
the backtest exercises the exact code that generated live signals — no
re-implementation, no drift.
"""
