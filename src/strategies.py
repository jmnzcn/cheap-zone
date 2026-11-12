"""Estrategias con respaldo publicado, con los parámetros de sus autores.

Cada función devuelve una tabla de pesos objetivo (fechas x activos) decidida con
información disponible hasta el cierre de cada fecha. Ningún parámetro fue
ajustado con estos datos.
"""
import numpy as np
import pandas as pd

SECTORS = ["XLB", "XLE", "XLF", "XLI", "XLK", "XLP", "XLU", "XLV", "XLY"]


def month_ends(p: pd.DataFrame) -> pd.DataFrame:
    """Cierres del último día hábil de cada mes."""
    return p.groupby(p.index.to_period("M")).tail(1)


def _daily(monthly_w: pd.DataFrame, index: pd.DatetimeIndex) -> pd.DataFrame:
    return monthly_w.reindex(index).ffill().fillna(0.0)


def buy_hold(p, asset="SPY"):
    return pd.DataFrame({asset: 1.0}, index=p.index)


def sixty_forty(p):
    return pd.DataFrame({"SPY": 0.6, "AGG": 0.4}, index=p.index)


def faber_sma10(p, asset="SPY"):
    """Faber (2007): invertido si el cierre mensual supera su promedio de 10 meses."""
    m = month_ends(p[[asset]])
    return _daily((m > m.rolling(10).mean()).astype(float), p.index)


def tsmom_12m(p, asset="SPY"):
    """Moskowitz, Ooi y Pedersen (2012): invertido si el retorno de 12 meses es positivo."""
    m = month_ends(p[[asset]])
    return _daily((m / m.shift(12) - 1 > 0).astype(float), p.index)


def dual_momentum(p):
    """Antonacci (2014): la mejor entre renta variable de EE. UU. e internacional si
    supera a los bonos de corto plazo en 12 meses; en caso contrario, bonos agregados."""
    m = month_ends(p[["SPY", "EFA", "AGG", "SHY"]])
    r = m / m.shift(12) - 1
    w = pd.DataFrame(0.0, index=m.index, columns=["SPY", "EFA", "AGG"])
    valid = r.notna().all(axis=1)
    risk_on = r["SPY"] > r["SHY"]
    w.loc[valid & risk_on & (r["SPY"] >= r["EFA"]), "SPY"] = 1.0
    w.loc[valid & risk_on & (r["SPY"] < r["EFA"]), "EFA"] = 1.0
    w.loc[valid & ~risk_on, "AGG"] = 1.0
    return _daily(w, p.index)


def sector_momentum(p, top=3):
    """Jegadeesh y Titman (1993) aplicado a sectores: los 3 sectores con mayor
    retorno de los meses 12 a 2 (se omite el más reciente), a partes iguales."""
    cols = [c for c in SECTORS if c in p.columns]
    m = month_ends(p[cols])
    mom = m.shift(1) / m.shift(12) - 1
    rank = mom.rank(axis=1, ascending=False)
    w = (rank <= top).astype(float).div(top).where(mom.notna().all(axis=1), 0.0)
    return _daily(w, p.index)


def rsi(series: pd.Series, n: int = 2) -> pd.Series:
    d = series.diff()
    up = d.clip(lower=0).ewm(alpha=1 / n, adjust=False).mean()
    dn = (-d.clip(upper=0)).ewm(alpha=1 / n, adjust=False).mean()
    return 100 - 100 / (1 + up / dn.replace(0, np.nan))


def rsi2_reversion(p, asset="SPY"):
    """Connors y Alvarez (2008): compra si RSI(2) < 10 con el precio sobre el promedio
    de 200 días; vende cuando el cierre supera el promedio de 5 días."""
    c = p[asset]
    entry = (rsi(c, 2) < 10) & (c > c.rolling(200).mean())
    exit_ = c > c.rolling(5).mean()
    pos, state = np.zeros(len(c)), 0.0
    for i, (e, x) in enumerate(zip(entry.to_numpy(), exit_.to_numpy())):
        if state == 0.0 and e:
            state = 1.0
        elif state == 1.0 and x:
            state = 0.0
        pos[i] = state
    return pd.DataFrame({asset: pos}, index=p.index)


def turn_of_month(p, asset="SPY"):
    """Lakonishok y Smidt (1988): invertido desde el cierre del penúltimo día hábil
    del mes hasta el cierre del tercer día hábil del mes siguiente."""
    per = p.index.to_period("M")
    from_start = pd.Series(1, index=p.index).groupby(per).cumsum()
    from_end = pd.Series(1, index=p.index).iloc[::-1].groupby(per[::-1]).cumsum().iloc[::-1]
    hold = (from_end <= 2) | (from_start <= 2)
    return pd.DataFrame({asset: hold.astype(float)}, index=p.index)
