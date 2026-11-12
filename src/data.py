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


def download_closes(tickers: list[str], start: str = "2003-01-01") -> pd.DataFrame:
    """Cierres ajustados (incluyen dividendos) de varios activos, una columna por ticker.
    Los tickers que fallen se omiten con un aviso."""
    import yfinance as yf

    cols = {}
    try:
        raw = yf.download(tickers, start=start, auto_adjust=True, progress=False)["Close"]
        cols = {t: raw[t].dropna() for t in tickers if t in raw and raw[t].notna().sum() > 300}
    except Exception as e:
        print(f"[aviso] descarga conjunta fallida ({e}); se intenta ticker por ticker")
    for t in tickers:
        if t not in cols:
            try:
                cols[t] = download(t, "1d", start)["Close"]
            except Exception as e:
                print(f"[aviso] no se pudo descargar {t}: {e}")
    df = pd.DataFrame(cols)
    df.index = pd.to_datetime(df.index, utc=True).tz_localize(None)
    return df.sort_index()


def synthetic_closes(tickers: list[str], n: int = 5800, seed: int = 3) -> pd.DataFrame:
    """Cierres simulados para varios activos. Solo para verificar que el código corre."""
    rng = np.random.default_rng(seed)
    idx = pd.bdate_range("2003-01-01", periods=n)
    market = rng.normal(0.0003, 0.009, n)
    out = {}
    for t in tickers:
        bond = t in ("AGG", "SHY")
        r = (0.00008 + rng.normal(0, 0.001 if t == "SHY" else 0.003, n)) if bond \
            else market * rng.uniform(0.8, 1.2) + rng.normal(0, 0.006, n)
        out[t] = 100 * np.exp(np.cumsum(r))
    return pd.DataFrame(out, index=idx)
