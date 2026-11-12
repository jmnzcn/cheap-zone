"""Motor de backtest barra a barra, solo posiciones largas, una a la vez.

Supuestos (todos conservadores):
- La señal del cierre de t se ejecuta en la apertura de t+1.
- Si en una misma barra se alcanzan el stop y el objetivo, se asume el stop.
- Si la apertura salta por debajo del stop, se sale a la apertura (peor precio).
- Se cobra deslizamiento y comisión en la entrada y en la salida.
- El capital fuera de posición no genera intereses.
"""
from dataclasses import dataclass

import numpy as np
import pandas as pd

from .config import Costs, ExitRule


@dataclass
class Result:
    equity: pd.Series
    trades: pd.DataFrame


def run_backtest(d: pd.DataFrame, rule: ExitRule, costs: Costs = Costs(),
                 start_idx: int = 0) -> Result:
    o, h, l, c = (d[k].to_numpy(float) for k in ("Open", "High", "Low", "Close"))
    sig = d["signal"].to_numpy(bool)
    pb_low = d["pullback_low"].to_numpy(float)
    fall = d["fall_type"].to_numpy()
    ma = d[f"sma{rule.exit_below_ma}"].to_numpy(float) if rule.exit_below_ma else None
    cost = costs.slippage_pct + costs.commission_pct
    n = len(d)

    equity = np.ones(n)
    cash = 1.0
    in_pos = False
    pending_entry = pending_exit = False
    exit_reason = ""
    entry_px = stop = target = np.nan
    entry_i = sig_i = -1
    trades = []

    def close_trade(i, px, reason):
        nonlocal cash, in_pos
        exit_px = px * (1 - cost)
        ret = exit_px / entry_px - 1
        cash *= 1 + ret
        trades.append(dict(entrada=d.index[entry_i], salida=d.index[i], barras=i - entry_i + 1,
                           precio_entrada=entry_px, precio_salida=exit_px, retorno=ret,
                           motivo=reason, caida=fall[sig_i]))
        in_pos = False

    for i in range(start_idx, n):
        # --- Apertura: ejecutar decisiones tomadas al cierre anterior ---
        if pending_exit and in_pos:
            close_trade(i, o[i], exit_reason)
        pending_exit = False
        if pending_entry and not in_pos:
            entry_px = o[i] * (1 + cost)
            entry_i, sig_i = i, i - 1
            stop = target = np.nan
            if rule.stop_at_pullback_low:
                stop = pb_low[sig_i] * (1 - rule.stop_buffer_pct)
            if rule.stop_pct is not None:
                fixed = o[i] * (1 - rule.stop_pct)
                stop = fixed if np.isnan(stop) else max(stop, fixed)
            if rule.target_pct is not None:
                target = o[i] * (1 + rule.target_pct)
            in_pos = True
        pending_entry = False

        # --- Durante la barra: stop primero, luego objetivo ---
        if in_pos:
            if not np.isnan(stop) and l[i] <= stop:
                close_trade(i, min(o[i], stop), "stop")
            elif not np.isnan(target) and h[i] >= target:
                close_trade(i, max(o[i], target), "objetivo")

        # --- Cierre: decisiones para la apertura siguiente ---
        if in_pos:
            if rule.max_hold is not None and i - entry_i + 1 >= rule.max_hold:
                pending_exit, exit_reason = True, "tiempo"
            elif ma is not None and c[i] < ma[i]:
                pending_exit, exit_reason = True, f"cierre_bajo_pm{rule.exit_below_ma}"
            if i == n - 1:
                close_trade(i, c[i], "fin_de_datos")
        elif sig[i] and i < n - 1:
            pending_entry = True

        equity[i] = cash * (c[i] * (1 - cost) / entry_px) if in_pos else cash

    eq = pd.Series(equity, index=d.index).iloc[start_idx:]
    return Result(eq, pd.DataFrame(trades))
