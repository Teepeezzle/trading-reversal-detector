"""Trading Reversal Detector package.

Modules:
    data_fetcher:      Pulls OHLCV data from Yahoo Finance via yfinance.
    indicators:        Computes RSI, ATR, and Volume MA.
    price_levels:      Computes Daily/Weekly/Monthly/Yearly highs & lows.
    reversal_detector: Core 4-condition reversal signal logic.
    risk_manager:      SL/TP, position sizing, and session risk limits.
    signal_formatter:  Renders signals as human-readable alert blocks.
"""

__version__ = "1.0.0"
