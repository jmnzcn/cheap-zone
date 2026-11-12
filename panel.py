"""Calcula el estado del mercado, las señales activas y el riesgo, y lo guarda como JSON.

    python panel.py          # datos reales; escribe panel/datos.json
    python panel.py --demo   # datos simulados
"""
import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd

from src import data
from src import strategies as st
from src.portfolio import run_weights, stats

ASSETS = {"SPY": "S&P 500", "QQQ": "Nasdaq 100", "IWM": "Russell 2000", "DIA": "Dow Jones"}
EVAL_START = "2005-01-01"
HISTORY = 504            # días hábiles de la serie para los gráficos (unos 2 años)


def r(x, n=4):
    return None if x is None or pd.isna(x) else round(float(x), n)


def regime_stats(c: pd.Series, cond: pd.Series) -> dict:
    """Retorno y volatilidad anualizados del día siguiente, según la condición del día."""
    ret = c.pct_change().shift(-1)
    out = {}
    for name, mask in (("si", cond), ("no", ~cond)):
        x = ret[mask.reindex(ret.index, fill_value=False)].loc[EVAL_START:].dropna()
        out[name] = dict(dias=int(len(x)), retorno_anual=r(x.mean() * 252), volatilidad=r(x.std() * np.sqrt(252)))
    return out


def asset_block(p: pd.DataFrame, t: str) -> dict:
    c = p[t].dropna()
    sma = {n: c.rolling(n).mean() for n in (20, 40, 200)}
    ret = c.pct_change()
    vol20 = ret.rolling(20).std() * np.sqrt(252)
    dd = c / c.cummax() - 1
    rsi2 = st.rsi(c, 2)
    hist = slice(EVAL_START, None)

    # Señales, con las mismas funciones que usan los backtests
    w_rsi = st.rsi_reversion(p[[t]].dropna(), t)[t]
    trades = st.trades_from_position(c, w_rsi.loc[hist])
    closed = trades.iloc[:-1] if w_rsi.iloc[-1] == 1 else trades
    m = st.month_ends(c.to_frame())[t]
    faber_on = bool(m.iloc[-1] > m.rolling(10).mean().iloc[-1])
    tsmom = m.iloc[-1] / m.shift(12).iloc[-1] - 1
    above200 = c > sma[200]

    def rule_stats(weights):
        rr = run_weights(p[[t]].dropna(), weights, lag=1).loc[hist]
        s = stats(rr["ret"], ret.loc[hist])
        return dict(retorno_anual=r(s["retorno_anual"]), caida_maxima=r(s["caida_maxima"]),
                    exposicion=r(rr["exposure"].mean()))

    bh = stats(ret.loc[hist].dropna(), ret.loc[hist])
    rsi_state = "en posición" if w_rsi.iloc[-1] == 1 else "sin posición"
    if w_rsi.iloc[-1] == 1 and w_rsi.iloc[-2] == 0:
        rsi_state = "compra hoy"
    elif w_rsi.iloc[-1] == 0 and w_rsi.iloc[-2] == 1:
        rsi_state = "venta hoy"

    return dict(
        ticker=t, nombre=ASSETS[t], fecha=str(c.index[-1].date()),
        precio=r(c.iloc[-1], 2), cambio_1d=r(ret.iloc[-1]), cambio_1m=r(c.iloc[-1] / c.iloc[-22] - 1),
        cambio_1a=r(c.iloc[-1] / c.iloc[-253] - 1),
        dist_pm40=r(c.iloc[-1] / sma[40].iloc[-1] - 1), dist_pm200=r(c.iloc[-1] / sma[200].iloc[-1] - 1),
        sobre_pm200=bool(above200.iloc[-1]), pm20_sobre_pm40=bool(sma[20].iloc[-1] > sma[40].iloc[-1]),
        dias_en_regimen=int((above200 != above200.iloc[-1]).iloc[::-1].cumsum().eq(0).sum()),
        volatilidad_20d=r(vol20.iloc[-1]), volatilidad_mediana=r(vol20.loc[hist].median()),
        volatilidad_percentil=r((vol20.loc[hist] <= vol20.iloc[-1]).mean()),
        caida_actual=r(dd.iloc[-1]), caida_maxima_historica=r(dd.loc[hist].min()),
        caida_percentil=r((dd.loc[hist] >= dd.iloc[-1]).mean()),
        dias_desde_maximo=int(len(c) - 1 - np.argmax(c.to_numpy())),
        rsi2=r(rsi2.iloc[-1], 1),
        regimen_pm200=regime_stats(c, above200),
        comprar_y_mantener=dict(retorno_anual=r(bh["retorno_anual"]), caida_maxima=r(bh["caida_maxima"])),
        senales=dict(
            tendencia_10m=dict(activa=faber_on, historial=rule_stats(st.faber_sma10(p[[t]].dropna(), t))),
            momentum_12m=dict(activa=bool(tsmom > 0), retorno_12m=r(tsmom),
                              historial=rule_stats(st.tsmom_12m(p[[t]].dropna(), t))),
            rsi2=dict(estado=rsi_state, operaciones=int(len(closed)),
                      pct_ganadoras=r((closed["retorno"] > 0).mean()), retorno_medio=r(closed["retorno"].mean()),
                      peor_operacion=r(closed["retorno"].min()), dias_medios=r(closed["dias"].mean(), 1),
                      ultima_entrada=str(trades["entrada"].iloc[-1].date()) if len(trades) else None),
        ),
        serie=dict(fechas=[str(d.date()) for d in c.index[-HISTORY:]],
                   cierre=[r(v, 2) for v in c.iloc[-HISTORY:]],
                   pm200=[r(v, 2) for v in sma[200].iloc[-HISTORY:]],
                   pm40=[r(v, 2) for v in sma[40].iloc[-HISTORY:]],
                   caida=[r(v) for v in dd.iloc[-HISTORY:]]),
    )


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--demo", action="store_true")
    ap.add_argument("--out", default="panel/datos.json")
    a = ap.parse_args()
    tickers = list(ASSETS)
    p = data.synthetic_closes(tickers) if a.demo else data.download_closes(tickers)
    p = p.dropna(subset=["SPY"]).ffill()
    # Si la sesión de Nueva York sigue abierta, la última fila es parcial: se descarta
    ny = pd.Timestamp.now(tz="America/New_York")
    if not a.demo and p.index[-1].date() == ny.date() and (ny.hour, ny.minute) < (16, 15):
        p = p.iloc[:-1]
    blocks = [asset_block(p, t) for t in tickers if t in p.columns]
    payload = dict(
        generado=pd.Timestamp.now(tz="UTC").strftime("%Y-%m-%d %H:%M UTC"),
        ultimo_cierre=blocks[0]["fecha"], historial_desde=EVAL_START,
        fuente="Yahoo Finance, precios de cierre ajustados por dividendos" if not a.demo else "DATOS SIMULADOS",
        supuestos="Reglas con ejecución al cierre del día siguiente y costo de 5 pb por lado; "
                  "RSI(2) con ejecución al mismo cierre. Efectivo sin intereses; sin impuestos.",
        activos=blocks,
    )
    out = Path(a.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print(f"Escrito {out} ({out.stat().st_size / 1024:.0f} KB), último cierre {payload['ultimo_cierre']}")
    for b in blocks:
        s = b["senales"]
        print(f"{b['ticker']}: {b['precio']}  PM200 {b['dist_pm200']:+.1%}  vol {b['volatilidad_20d']:.1%} "
              f"(pct {b['volatilidad_percentil']:.0%})  caída {b['caida_actual']:.1%}  RSI2 {b['rsi2']}  "
              f"10m {'sí' if s['tendencia_10m']['activa'] else 'no'}  12m {'sí' if s['momentum_12m']['activa'] else 'no'}  "
              f"rsi2: {s['rsi2']['estado']}")


if __name__ == "__main__":
    main()
