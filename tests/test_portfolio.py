"""Pruebas del motor de carteras y de la ausencia de anticipación en las estrategias."""
import numpy as np
import pandas as pd

from src import data
from src import strategies as st
from src.portfolio import run_weights, stats

TICKERS = ["SPY", "EFA", "AGG", "SHY"] + st.SECTORS


def test_comprar_y_mantener_reproduce_el_precio():
    p = data.synthetic_closes(["SPY"], n=600)
    r = run_weights(p, st.buy_hold(p), lag=0, cost_pct=0.0)
    assert np.isclose((1 + r["ret"]).prod(), p["SPY"].iloc[-1] / p["SPY"].iloc[0])


def test_el_retardo_y_el_costo_se_aplican():
    idx = pd.bdate_range("2020-01-01", periods=6)
    p = pd.DataFrame({"SPY": [100, 110, 121, 133.1, 146.41, 161.051]}, index=idx)
    w = pd.DataFrame({"SPY": [0, 1, 1, 1, 1, 1.0]}, index=idx)      # señal al cierre del día 1
    r0 = run_weights(p, w, lag=0, cost_pct=0.0)["ret"]
    r1 = run_weights(p, w, lag=1, cost_pct=0.0)["ret"]
    assert np.allclose(r0.to_numpy(), [0, 0, 0.1, 0.1, 0.1, 0.1])    # compra al cierre del día 1
    assert np.allclose(r1.to_numpy(), [0, 0, 0, 0.1, 0.1, 0.1])      # compra al cierre del día 2
    rc = run_weights(p, w, lag=0, cost_pct=0.01)["ret"]
    assert np.isclose(rc.iloc[2], 0.1 - 0.01)


def test_las_estrategias_no_usan_informacion_futura():
    p = data.synthetic_closes(TICKERS, n=1600)
    for fn in (st.faber_sma10, st.tsmom_12m, st.dual_momentum, st.sector_momentum, st.rsi2_reversion):
        full = fn(p)
        cut = 1205                                    # corte a mitad de mes
        part = fn(p.iloc[:cut])
        last_me = st.month_ends(p.iloc[:cut - 1]).index[-2]   # meses completos en ambos casos
        a, b = part.loc[:last_me], full.loc[:last_me]
        assert np.allclose(a.to_numpy(), b[a.columns].to_numpy()), fn.__name__


def test_alfa_de_una_copia_del_benchmark_es_cero():
    p = data.synthetic_closes(["SPY"], n=800)
    r = p["SPY"].pct_change().dropna()
    s = stats(r, r)
    assert abs(s["alfa_anual"]) < 1e-10 and np.isclose(s["beta"], 1.0)
