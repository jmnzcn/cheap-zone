"""Métricas de desempeño y prueba de ventaja estadística de la señal."""
import numpy as np
import pandas as pd


def bars_per_year(index: pd.DatetimeIndex) -> float:
    years = (index[-1] - index[0]).days / 365.25
    return len(index) / years if years > 0 else 252.0


def summarize(equity: pd.Series, trades: pd.DataFrame | None = None) -> dict:
    bpy = bars_per_year(equity.index)
    years = len(equity) / bpy
    total = equity.iloc[-1] / equity.iloc[0] - 1
    cagr = (1 + total) ** (1 / years) - 1 if years > 0 and total > -1 else np.nan
    rets = equity.pct_change().dropna()
    sharpe = rets.mean() / rets.std() * np.sqrt(bpy) if rets.std() > 0 else np.nan
    max_dd = (equity / equity.cummax() - 1).min()
    out = dict(retorno_total=total, retorno_anual=cagr, caida_maxima=max_dd, sharpe=sharpe)
    if trades is not None:
        if len(trades):
            r = trades["retorno"]
            gains, losses = r[r > 0].sum(), -r[r < 0].sum()
            out.update(operaciones=len(r), pct_ganadoras=(r > 0).mean(), retorno_medio=r.mean(),
                       factor_beneficio=gains / losses if losses > 0 else np.inf,
                       exposicion=trades["barras"].sum() / len(equity))
        else:
            out.update(operaciones=0, pct_ganadoras=np.nan, retorno_medio=np.nan,
                       factor_beneficio=np.nan, exposicion=0.0)
    return out


def edge_test(d: pd.DataFrame, horizons=(1, 3, 5, 10), n_perm: int = 5000, seed: int = 0) -> pd.DataFrame:
    """¿Rinde más el mercado después de una señal que en una barra cualquiera?

    Compara el retorno medio de apertura(t+1) a apertura(t+1+k) tras cada señal
    con el de todas las barras, y estima por permutación la probabilidad de ver
    una diferencia igual o mayor por puro azar (valor p de una cola).
    """
    rng = np.random.default_rng(seed)
    o = d["Open"]
    rows = []
    for k in horizons:
        fwd = (o.shift(-(k + 1)) / o.shift(-1) - 1)
        valid = fwd.notna() & d[[c for c in d.columns if c.startswith("sma")]].notna().all(axis=1)
        allr = fwd[valid].to_numpy()
        sigr = fwd[valid & d["signal"]].to_numpy()
        if len(sigr) < 5:
            rows.append(dict(horizonte=k, senales=len(sigr)))
            continue
        diff = sigr.mean() - allr.mean()
        perm = np.array([rng.choice(allr, len(sigr), replace=False).mean() for _ in range(n_perm)])
        rows.append(dict(horizonte=k, senales=len(sigr), media_tras_senal=sigr.mean(),
                         media_cualquier_barra=allr.mean(), diferencia=diff,
                         pct_positivas_senal=(sigr > 0).mean(), pct_positivas_todas=(allr > 0).mean(),
                         valor_p=(perm >= sigr.mean()).mean()))
    return pd.DataFrame(rows)
