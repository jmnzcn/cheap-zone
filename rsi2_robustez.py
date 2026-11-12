"""Prueba de robustez de la reversión a la media con RSI de corto plazo.

Preguntas: ¿el resultado se repite en otros índices?, ¿sobrevive a parámetros
vecinos, a costos mayores y a ejecutar un día después?, ¿qué aporta remunerar
el efectivo? No se elige ningún parámetro a partir de estas tablas.

    python rsi2_robustez.py          # datos reales
    python rsi2_robustez.py --demo   # datos simulados
"""
import argparse
from pathlib import Path

import numpy as np
import pandas as pd

from src import data
from src import strategies as st
from src.portfolio import run_weights, stats

US = ["SPY", "QQQ", "IWM", "DIA"]
INTL = ["EFA", "EEM"]
CASH = "SHY"
EVAL_START = "2005-01-01"
PERIODS = [("2005-2009", "2005", "2009"), ("2010-2014", "2010", "2014"), ("2015-2019", "2015", "2019"),
           ("2020-2022", "2020", "2022"), ("2023-hoy", "2023", "2100")]


def show(title, t, pct=(), dec=(), integer=()):
    t = t.copy()
    for c in t.columns:
        if c in integer:
            t[c] = t[c].map(lambda v: "" if pd.isna(v) else f"{int(v)}")
        elif c in dec:
            t[c] = t[c].map(lambda v: "" if pd.isna(v) else f"{v:+.2f}")
        elif pct == "all" or c in pct:
            t[c] = t[c].map(lambda v: "" if pd.isna(v) else f"{v:+.2%}")
    print(f"\n=== {title} ===")
    print(t.to_string())


def evaluate(p, asset, lag=0, cost=0.0005, sl=slice(EVAL_START, None), **kw):
    w = st.rsi_reversion(p, asset, **kw)
    r = run_weights(p, w, lag=lag, cost_pct=cost).loc[sl]
    s = stats(r["ret"], p[asset].pct_change().loc[sl])
    s["exposicion"] = r["exposure"].mean()
    return s, w


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--demo", action="store_true")
    ap.add_argument("--outdir", default="resultados/rsi2")
    a = ap.parse_args()
    out = Path(a.outdir)
    out.mkdir(parents=True, exist_ok=True)
    tickers = US + INTL + [CASH]
    p = (data.synthetic_closes(tickers) if a.demo else data.download_closes(tickers)).dropna(subset=["SPY"]).ffill()
    assets = [t for t in US + INTL if t in p.columns]
    us = [t for t in US if t in p.columns]
    print(f"Datos: {p.index[0].date()} a {p.index[-1].date()}; activos: {', '.join(assets)}")
    KEY = ["retorno_anual", "caida_maxima", "alfa_anual", "exposicion"]

    # 1) Otros índices, parámetros originales, con estadísticas por operación
    rows = {}
    for t in assets:
        s, w = evaluate(p, t)
        tr = st.trades_from_position(p[t], w[t].loc[EVAL_START:])
        s.update(operaciones=len(tr), pct_ganadoras=(tr["retorno"] > 0).mean(), retorno_medio=tr["retorno"].mean(),
                 peor_operacion=tr["retorno"].min(), dias_medios=tr["dias"].mean())
        rows[t] = s
    t1 = pd.DataFrame(rows).T
    show("1. Parámetros originales en cada índice (ejecución al mismo cierre, 5 pb)",
         t1[KEY + ["sharpe", "t_alfa", "operaciones", "pct_ganadoras", "retorno_medio", "peor_operacion", "dias_medios"]],
         pct=KEY + ["pct_ganadoras", "retorno_medio", "peor_operacion"], dec=("sharpe", "t_alfa", "dias_medios"),
         integer=("operaciones",))
    t1.to_csv(out / "indices.csv")

    # 2) Cartera agrupada de los cuatro índices de EE. UU., por período
    def pooled(lag=0, cost=0.0005, **kw):
        w = pd.concat([st.rsi_reversion(p, t, **kw) for t in us], axis=1) / len(us)
        r = run_weights(p, w, lag=lag, cost_pct=cost)
        bench = p[us].pct_change().mean(axis=1)
        return r, bench

    r, bench = pooled()
    rows = {"2005-hoy": stats(r["ret"].loc[EVAL_START:], bench.loc[EVAL_START:])}
    for label, y0, y1 in PERIODS:
        rows[label] = stats(r["ret"].loc[y0:y1], bench.loc[y0:y1])
    t2 = pd.DataFrame(rows).T
    show(f"2. Cartera agrupada ({', '.join(us)} a partes iguales) por período",
         t2[["retorno_anual", "caida_maxima", "sharpe", "alfa_anual", "t_alfa"]],
         pct=("retorno_anual", "caida_maxima", "alfa_anual"), dec=("sharpe", "t_alfa"))
    t2.to_csv(out / "agrupada_periodos.csv")

    # 3) Sensibilidad a costos y al retardo de ejecución (cartera agrupada)
    rows = {}
    for lag in (0, 1):
        for cost in (0.0, 0.0005, 0.001, 0.002):
            r, bench = pooled(lag=lag, cost=cost)
            s = stats(r["ret"].loc[EVAL_START:], bench.loc[EVAL_START:])
            rows[f"{'mismo cierre' if lag == 0 else 'día siguiente'}, {cost * 1e4:.0f} pb"] = s
    t3 = pd.DataFrame(rows).T
    show("3. Costos y retardo de ejecución (cartera agrupada)", t3[["retorno_anual", "sharpe", "alfa_anual", "t_alfa"]],
         pct=("retorno_anual", "alfa_anual"), dec=("sharpe", "t_alfa"))
    t3.to_csv(out / "costos_retardo.csv")

    # 4) Rejilla de parámetros vecinos (cartera agrupada, mismo cierre, 5 pb)
    grid = []
    for n in (2, 3, 4):
        for entry in (5, 10, 15, 20, 25):
            for exit_n in (3, 5, 7, 10):
                for trend_n in (200, None):
                    r, bench = pooled(n=n, entry=entry, exit_n=exit_n, trend_n=trend_n)
                    s = stats(r["ret"].loc[EVAL_START:], bench.loc[EVAL_START:])
                    grid.append(dict(rsi=n, umbral=entry, salida=exit_n, filtro=trend_n or 0,
                                     alfa=s["alfa_anual"], t=s["t_alfa"], sharpe=s["sharpe"],
                                     caida=s["caida_maxima"], retorno=s["retorno_anual"]))
    g = pd.DataFrame(grid)
    g.to_csv(out / "rejilla.csv", index=False)
    sub = g[(g.rsi == 2) & (g.filtro == 200)]
    show("4a. Rejilla RSI(2) con filtro de 200 días: t del alfa (filas: umbral de entrada; columnas: días del promedio de salida)",
         sub.pivot(index="umbral", columns="salida", values="t"), dec=(3, 5, 7, 10))
    show("4b. La misma rejilla: alfa anual", sub.pivot(index="umbral", columns="salida", values="alfa"), pct="all")
    summ = g.groupby(["rsi", "filtro"]).agg(combinaciones=("t", "size"), alfa_positivo=("alfa", lambda x: (x > 0).mean()),
                                           t_mediana=("t", "median"), t_min=("t", "min"), t_max=("t", "max"),
                                           alfa_mediano=("alfa", "median"))
    show("4c. Resumen de las 120 combinaciones (filtro 0 = sin filtro de tendencia)", summ,
         pct=("alfa_positivo", "alfa_mediano"), dec=("t_mediana", "t_min", "t_max"), integer=("combinaciones",))
    print(f"Combinaciones con alfa positivo: {(g.alfa > 0).mean():.1%}; con t > 2: {(g.t > 2).mean():.1%}; "
          f"t mediana: {g.t.median():+.2f}")

    # 5) Efectivo remunerado y combinación con una posición fija en el índice
    if CASH in p.columns:
        w_rsi = st.rsi_reversion(p, "SPY")
        combos = {
            "SPY comprar y mantener": pd.DataFrame({"SPY": 1.0}, index=p.index),
            f"{CASH} (bonos del Tesoro de 1 a 3 años)": pd.DataFrame({CASH: 1.0}, index=p.index),
            "RSI(2) en SPY, efectivo sin intereses": w_rsi,
            f"RSI(2) en SPY, efectivo en {CASH}": pd.DataFrame({"SPY": w_rsi["SPY"], CASH: 1 - w_rsi["SPY"]}),
            f"50 % SPY fijo + 50 % RSI(2) con efectivo en {CASH}":
                pd.DataFrame({"SPY": 0.5 + 0.5 * w_rsi["SPY"], CASH: 0.5 * (1 - w_rsi["SPY"])}),
            f"60 % SPY + 40 % {CASH}": pd.DataFrame({"SPY": 0.6, CASH: 0.4}, index=p.index),
        }
        rows = {}
        spy = p["SPY"].pct_change()
        for name, w in combos.items():
            r = run_weights(p, w, lag=0, cost_pct=0.0005).loc[EVAL_START:]
            s = stats(r["ret"], spy.loc[EVAL_START:])
            rows[name] = {k: s[k] for k in ("retorno_anual", "volatilidad", "sharpe", "caida_maxima")}
        t5 = pd.DataFrame(rows).T
        show("5. Efectivo remunerado y combinaciones (SPY)", t5,
             pct=("retorno_anual", "volatilidad", "caida_maxima"), dec=("sharpe",))
        t5.to_csv(out / "efectivo.csv")

    # 6) Las peores operaciones en el SPY: el riesgo de comprar una caída que sigue
    tr = st.trades_from_position(p["SPY"], st.rsi_reversion(p, "SPY")["SPY"].loc[EVAL_START:])
    worst = tr.nsmallest(6, "retorno").assign(entrada=lambda d: d["entrada"].dt.date, salida=lambda d: d["salida"].dt.date)
    show("6. Las seis peores operaciones en el SPY", worst.set_index("entrada"), pct=("retorno",))
    if a.demo:
        print("\nAVISO: datos simulados; solo sirven para verificar la instalación.")


if __name__ == "__main__":
    main()
