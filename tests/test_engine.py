"""Pruebas del motor: operación conocida, prioridad del stop y ausencia de anticipación."""
import numpy as np
import pandas as pd

from src import data
from src.backtest import run_backtest
from src.config import Costs, ExitRule, StrategyParams
from src.signals import pm40_signals

NO_COST = Costs(0.0, 0.0)


def frame(rows, signal_at):
    idx = pd.bdate_range("2020-01-01", periods=len(rows))
    d = pd.DataFrame(rows, columns=["Open", "High", "Low", "Close"], index=idx)
    d["signal"] = False
    d.iloc[signal_at, d.columns.get_loc("signal")] = True
    d["pullback_low"] = 95.0
    d["fall_type"] = "normal"
    return d


def test_entra_en_la_apertura_siguiente_y_sale_en_el_objetivo():
    d = frame([(100, 101, 99, 100), (100, 102, 99.5, 101), (101, 104, 100.5, 103), (103, 104, 102, 103)], 0)
    res = run_backtest(d, ExitRule("t", target_pct=0.03, stop_pct=0.02), NO_COST)
    t = res.trades.iloc[0]
    assert t["precio_entrada"] == 100 and t["motivo"] == "objetivo"
    assert np.isclose(t["retorno"], 0.03)
    assert t["entrada"] == d.index[1]


def test_si_se_tocan_stop_y_objetivo_en_la_misma_barra_gana_el_stop():
    d = frame([(100, 101, 99, 100), (100, 104, 97, 100), (100, 101, 99, 100)], 0)
    res = run_backtest(d, ExitRule("t", target_pct=0.03, stop_pct=0.02), NO_COST)
    assert res.trades.iloc[0]["motivo"] == "stop"
    assert np.isclose(res.trades.iloc[0]["retorno"], -0.02)


def test_apertura_con_brecha_bajo_el_stop_sale_a_la_apertura():
    d = frame([(100, 101, 99, 100), (100, 101, 99, 100), (95, 96, 94, 95), (95, 96, 94, 95)], 0)
    res = run_backtest(d, ExitRule("t", stop_pct=0.02), NO_COST)
    assert np.isclose(res.trades.iloc[0]["retorno"], -0.05)


def test_salida_por_tiempo_y_costos():
    d = frame([(100, 101, 99, 100)] * 6, 0)
    res = run_backtest(d, ExitRule("t", max_hold=2), Costs(0.001, 0.0))
    t = res.trades.iloc[0]
    assert t["motivo"] == "tiempo" and t["barras"] == 3
    assert np.isclose(t["retorno"], 0.999 / 1.001 - 1)


def test_la_curva_de_capital_coincide_con_las_operaciones():
    d = pm40_signals(data.synthetic(3000))
    res = run_backtest(d, ExitRule("t", target_pct=0.03, stop_pct=0.02, max_hold=15), Costs(), start_idx=210)
    assert len(res.trades) > 5
    assert np.isclose(res.equity.iloc[-1], (1 + res.trades["retorno"]).prod())


def test_las_senales_no_usan_informacion_futura():
    df = data.synthetic(1500)
    full = pm40_signals(df, StrategyParams())
    for cut in (600, 900, 1200):
        part = pm40_signals(df.iloc[:cut], StrategyParams())
        assert part["signal"].equals(full["signal"].iloc[:cut])
        assert np.allclose(part["pullback_low"].dropna(), full["pullback_low"].iloc[:cut].dropna())
