from typing import Annotated
from datetime import datetime
import os
import pandas as pd

from .stockstats_utils import _clean_dataframe


def _get_exchange(exchange_id: str):
    """Instantiate a CCXT exchange by ID."""
    try:
        import ccxt
    except ImportError:
        raise ImportError("ccxt is required: pip install ccxt")
    exchange_class = getattr(ccxt, exchange_id)
    return exchange_class({"enableRateLimit": True})


def _fetch_ohlcv_df(symbol: str, start_date: str, end_date: str, exchange_id: str) -> pd.DataFrame:
    """
    Fetch OHLCV data from a CCXT exchange and return a cleaned DataFrame.
    Uses file-level caching keyed by symbol + exchange + date range.
    """
    from .config import get_config

    config = get_config()
    cache_dir = config.get("data_cache_dir", "data")
    os.makedirs(cache_dir, exist_ok=True)

    safe_symbol = symbol.replace("/", "-")
    cache_file = os.path.join(
        cache_dir, f"{safe_symbol}-{exchange_id}-{start_date}-{end_date}.csv"
    )

    if os.path.exists(cache_file):
        return pd.read_csv(cache_file, parse_dates=["Date"])

    exchange = _get_exchange(exchange_id)

    since = int(datetime.strptime(start_date, "%Y-%m-%d").timestamp() * 1000)
    end_ts = int(datetime.strptime(end_date, "%Y-%m-%d").timestamp() * 1000)

    all_candles = []
    while since < end_ts:
        candles = exchange.fetch_ohlcv(symbol, timeframe="1d", since=since, limit=1000)
        if not candles:
            break
        all_candles.extend(candles)
        since = candles[-1][0] + 1

    if not all_candles:
        return pd.DataFrame()

    df = pd.DataFrame(all_candles, columns=["timestamp", "Open", "High", "Low", "Close", "Volume"])
    df["Date"] = pd.to_datetime(df["timestamp"], unit="ms").dt.normalize()
    df = df.drop(columns=["timestamp"])
    df = df[df["Date"] <= pd.Timestamp(end_date)]
    df = df.sort_values("Date").reset_index(drop=True)

    df.to_csv(cache_file, index=False)
    return df


def _default_exchange() -> str:
    from .config import get_config
    return get_config().get("ccxt_exchange", "binance")


def get_crypto_ohlcv(
    symbol: Annotated[str, "crypto pair in CCXT format, e.g. BTC/USDT"],
    start_date: Annotated[str, "start date in yyyy-mm-dd format"],
    end_date: Annotated[str, "end date in yyyy-mm-dd format"],
    exchange_id: Annotated[str, "CCXT exchange id, e.g. binance, bybit, okx"] = None,
) -> str:
    """Fetch daily OHLCV data for a crypto pair and return as a formatted CSV string."""
    if exchange_id is None:
        exchange_id = _default_exchange()
    datetime.strptime(start_date, "%Y-%m-%d")
    datetime.strptime(end_date, "%Y-%m-%d")

    df = _fetch_ohlcv_df(symbol, start_date, end_date, exchange_id)

    if df.empty:
        return f"No data found for '{symbol}' on {exchange_id} between {start_date} and {end_date}"

    for col in ["Open", "High", "Low", "Close"]:
        if col in df.columns:
            df[col] = df[col].round(4)

    header = (
        f"# Crypto OHLCV data for {symbol} ({exchange_id}) from {start_date} to {end_date}\n"
        f"# Total records: {len(df)}\n"
        f"# Data retrieved on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
    )
    return header + df.to_csv(index=False)


def get_crypto_indicators(
    symbol: Annotated[str, "crypto pair in CCXT format, e.g. BTC/USDT"],
    indicator: Annotated[str, "technical indicator name (same set as stock indicators)"],
    curr_date: Annotated[str, "current trading date in yyyy-mm-dd format"],
    look_back_days: Annotated[int, "number of days to look back"],
    exchange_id: Annotated[str, "CCXT exchange id, e.g. binance, bybit, okx"] = None,
) -> str:
    """
    Compute technical indicators on crypto OHLCV data using stockstats.
    Supports the same indicator set as the stock market analyst.
    """
    from dateutil.relativedelta import relativedelta
    from stockstats import wrap

    INDICATOR_DESCRIPTIONS = {
        "close_50_sma": (
            "50 SMA: Medium-term trend indicator. "
            "Identify trend direction and dynamic support/resistance."
        ),
        "close_200_sma": (
            "200 SMA: Long-term trend benchmark. "
            "Confirm overall market trend and golden/death cross setups."
        ),
        "close_10_ema": (
            "10 EMA: Responsive short-term average. "
            "Capture quick momentum shifts and potential entries."
        ),
        "macd": (
            "MACD: Momentum via EMA differences. "
            "Look for crossovers and divergence as trend-change signals."
        ),
        "macds": (
            "MACD Signal: EMA smoothing of the MACD line. "
            "Crossovers with MACD trigger trades."
        ),
        "macdh": (
            "MACD Histogram: Gap between MACD and signal. "
            "Visualize momentum strength and early divergence."
        ),
        "rsi": (
            "RSI: Momentum oscillator flagging overbought/oversold. "
            "70/30 thresholds; watch for divergence to signal reversals."
        ),
        "boll": "Bollinger Middle: 20 SMA as dynamic price benchmark.",
        "boll_ub": "Bollinger Upper Band: Potential overbought / breakout zone.",
        "boll_lb": "Bollinger Lower Band: Potential oversold zone.",
        "atr": (
            "ATR: Average True Range measures volatility. "
            "Use for stop-loss sizing and position sizing."
        ),
        "vwma": (
            "VWMA: Volume-weighted moving average. "
            "Confirms trends by integrating price and volume."
        ),
        "mfi": (
            "MFI: Money Flow Index — price + volume momentum. "
            "Overbought >80, oversold <20."
        ),
    }

    if exchange_id is None:
        exchange_id = _default_exchange()

    if indicator not in INDICATOR_DESCRIPTIONS:
        raise ValueError(
            f"Indicator '{indicator}' not supported. Choose from: {list(INDICATOR_DESCRIPTIONS.keys())}"
        )

    curr_dt = datetime.strptime(curr_date, "%Y-%m-%d")
    start_dt = curr_dt - relativedelta(days=look_back_days + 300)  # extra buffer for indicator warmup
    start_date = start_dt.strftime("%Y-%m-%d")

    df = _fetch_ohlcv_df(symbol, start_date, curr_date, exchange_id)

    if df.empty:
        return f"No data found for '{symbol}' on {exchange_id} to compute {indicator}"

    df = _clean_dataframe(df)
    stock_df = wrap(df)
    stock_df["Date"] = stock_df["Date"].dt.strftime("%Y-%m-%d")
    stock_df[indicator]  # trigger stockstats computation

    date_map = dict(zip(stock_df["Date"], stock_df[indicator]))

    lines = []
    ptr = curr_dt
    before = curr_dt - relativedelta(days=look_back_days)
    while ptr >= before:
        date_str = ptr.strftime("%Y-%m-%d")
        value = date_map.get(date_str)
        if value is None or (isinstance(value, float) and pd.isna(value)):
            lines.append(f"{date_str}: N/A")
        else:
            lines.append(f"{date_str}: {value}")
        ptr -= relativedelta(days=1)

    result = (
        f"## {indicator} for {symbol} ({exchange_id}) "
        f"from {before.strftime('%Y-%m-%d')} to {curr_date}:\n\n"
        + "\n".join(lines)
        + f"\n\n{INDICATOR_DESCRIPTIONS[indicator]}"
    )
    return result
