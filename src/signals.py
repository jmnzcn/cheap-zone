"""Indicadores y señal de entrada de la estrategia del promedio móvil de 40.

Cada condición usa únicamente información disponible al cierre de la barra,
de modo que la señal de la barra t se ejecuta, como muy pronto, en la apertura
de t+1 (sin sesgo de anticipación).
"""
import numpy as np
import pandas as pd

from .config import StrategyParams


def sma(s: pd.Series, n: int) -> pd.Series:
    return s.rolling(n, min_periods=n).mean()


def add_indicators(df: pd.DataFrame, p: StrategyParams) -> pd.DataFrame:
    d = df.copy()
    for n in sorted({p.ma_fast, p.ma_slow, p.ma_floor1, p.ma_floor2}):
        d[f"sma{n}"] = sma(d["Close"], n)
    rng = d["High"] - d["Low"]
    d["body_ratio"] = ((d["Close"] - d["Open"]).abs() / rng).where(rng > 0, 0.0)
    d["green"] = d["Close"] > d["Open"]
    d["ret1"] = d["Close"].pct_change()
    return d


def pm40_signals(df: pd.DataFrame, p: StrategyParams = StrategyParams()) -> pd.DataFrame:
    """Devuelve el DataFrame con indicadores y las columnas:
    signal (bool), fall_type ('normal' | 'fuerte'), pullback_low (float)."""
    d = add_indicators(df, p)
    fast, slow = d[f"sma{p.ma_fast}"], d[f"sma{p.ma_slow}"]

    # 1) Tendencia alcista clara: PM20 sobre PM40, sin cruces recientes
    trend = (fast > slow).astype(float).rolling(p.trend_bars).sum() == p.trend_bars
    if p.require_rising_slow:
        trend &= slow > slow.shift(p.trend_bars)

    # 2) El precio tocó o se acercó al PM40 en las últimas barras ("zona barata")
    touch_now = (d["Low"] <= slow * (1 + p.touch_pct)).astype(float)
    touched = touch_now.rolling(p.pullback_lookback).max() == 1.0
    not_broken = d["Close"] >= slow * (1 - p.max_break_pct)

    # 3) Ruptura de la caída: vela verde y sólida que supera los máximos previos
    prior_high = d["High"].shift(1).rolling(p.break_bars).max()
    breakout = (d["Close"] > prior_high) & d["green"] & (d["body_ratio"] >= p.min_body_ratio)

    # 4) No comprar lejos del PM40
    near = d["Close"] <= slow * (1 + p.max_dist_pct)

    signal = trend & touched & not_broken & breakout & near

    # 5) Filtro opcional de piso fuerte (PM100 y PM200)
    if p.require_floor:
        f1, f2 = d[f"sma{p.ma_floor1}"], d[f"sma{p.ma_floor2}"]
        signal &= (d["Close"] > f1) & (d["Close"] > f2) & (f1 > f2)

    worst_drop = d["ret1"].rolling(p.pullback_lookback).min()
    d["fall_type"] = np.where(worst_drop <= -p.strong_fall_pct, "fuerte", "normal")
    d["pullback_low"] = d["Low"].rolling(p.pullback_lookback).min()
    d["signal"] = signal.fillna(False).astype(bool)
    return d
