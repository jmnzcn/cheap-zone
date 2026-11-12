"""Backtest de carteras por pesos y estadísticos de comparación.

Convención temporal: los pesos objetivo de la fila t se deciden con información
disponible hasta el cierre de t. Con `lag=1` (por defecto) la orden se ejecuta en
el cierre del día siguiente; con `lag=0` se ejecuta en el mismo cierre (solo es
realista para reglas que pueden calcularse minutos antes del cierre o que
dependen del calendario).
"""
import numpy as np
import pandas as pd


def run_weights(prices: pd.DataFrame, target: pd.DataFrame, lag: int = 1,
                cost_pct: float = 0.0005) -> pd.DataFrame:
    """Devuelve retorno diario neto, exposición y rotación de la cartera.
    `cost_pct` se cobra sobre cada unidad de cartera que cambia de manos (5 pb por defecto)."""
    rets = prices.pct_change()
    held = target.reindex(prices.index).ffill().fillna(0.0).shift(lag).fillna(0.0)
    gross = (held.shift(1) * rets[held.columns]).sum(axis=1)
    turnover = held.diff().abs().sum(axis=1).fillna(0.0)
    return pd.DataFrame({"ret": gross - turnover.shift(1).fillna(0.0) * cost_pct,
                         "exposure": held.shift(1).sum(axis=1), "turnover": turnover})


def stats(ret: pd.Series, bench: pd.Series) -> dict:
    """Retorno anual, volatilidad, Sharpe, caída máxima y alfa frente al benchmark."""
    ret, bench = ret.dropna(), bench.reindex(ret.dropna().index).fillna(0.0)
    eq = (1 + ret).cumprod()
    years = len(ret) / 252
    x = np.column_stack([np.ones(len(ret)), bench.to_numpy()])
    y = ret.to_numpy()
    coef, *_ = np.linalg.lstsq(x, y, rcond=None)
    resid = y - x @ coef
    se = np.sqrt(resid.var(ddof=2) * np.linalg.inv(x.T @ x)[0, 0])
    return dict(retorno_anual=eq.iloc[-1] ** (1 / years) - 1, volatilidad=ret.std() * np.sqrt(252),
                sharpe=ret.mean() / ret.std() * np.sqrt(252) if ret.std() > 0 else np.nan,
                caida_maxima=(eq / eq.cummax() - 1).min(),
                alfa_anual=coef[0] * 252, beta=coef[1],
                t_alfa=coef[0] / se if resid.std() > 1e-9 else np.nan)   # sin residuo no hay prueba
