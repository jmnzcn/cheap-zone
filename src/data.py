"""Carga de datos OHLCV: descarga con yfinance, lectura de CSV o serie sintética."""
from pathlib import Path

import numpy as np
import pandas as pd

COLS = ["Open", "High", "Low", "Close", "Volume"]


def _clean(df: pd.DataFrame) -> pd.DataFrame:
    if isinstance(df.columns, pd.MultiIndex):          # yfinance devuelve (campo, ticker)
        df.columns = df.columns.get_level_values(0)
    df = df.rename(columns={c: str(c).strip().title() for c in df.columns})
    if "Volume" not in df.columns:
        df["Volume"] = 0
    df = df[COLS].apply(pd.to_numeric, errors="coerce").dropna(subset=COLS[:4])
    df.index = pd.to_datetime(df.index, utc=True).tz_localize(None)
    df = df[~df.index.duplicated()].sort_index()
    if df.empty:
        raise ValueError("No se obtuvieron datos. Revise el ticker, el intervalo o la conexión.")
    return df


def download(ticker: str, interval: str = "1d", start: str = "2005-01-01",
             cache_dir: str = "data") -> pd.DataFrame:
    """Descarga precios ajustados y los guarda en caché como CSV."""
    import yfinance as yf

    kwargs = dict(interval=interval, auto_adjust=True, progress=False)
    if interval == "1d":
        raw = yf.download(ticker, start=start, **kwargs)
    else:                       # Yahoo limita los datos por hora a unos 730 días
        raw = yf.download(ticker, period="720d", **kwargs)
    df = _clean(raw)
    Path(cache_dir).mkdir(exist_ok=True)
    df.to_csv(Path(cache_dir) / f"{ticker}_{interval}.csv")
    return df


def load_csv(path: str) -> pd.DataFrame:
    """Lee un CSV con columnas Date/Datetime, Open, High, Low, Close[, Volume]."""
    raw = pd.read_csv(path)
    date_col = next(c for c in raw.columns if c.strip().lower() in ("date", "datetime", "fecha"))
    raw = raw.set_index(date_col)
    return _clean(raw)


def synthetic(n: int = 4000, seed: int = 7, drift: float = 0.0003, vol: float = 0.011) -> pd.DataFrame:
    """Serie simulada (caminata aleatoria). Solo para probar que el código corre;
    sus resultados no dicen nada sobre el mercado real."""
    rng = np.random.default_rng(seed)
    close = 100 * np.exp(np.cumsum(rng.normal(drift, vol, n)))
    open_ = np.r_[100, close[:-1]] * np.exp(rng.normal(0, vol / 4, n))
    span = np.abs(rng.normal(0, vol / 2, n))
    high = np.maximum(open_, close) * (1 + span)
    low = np.minimum(open_, close) * (1 - span)
    idx = pd.bdate_range("2008-01-01", periods=n)
    return pd.DataFrame({"Open": open_, "High": high, "Low": low, "Close": close,
                         "Volume": 1_000_000}, index=idx)
