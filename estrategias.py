"""Compara estrategias con respaldo publicado contra comprar y mantener el SPY.

    python estrategias.py          # datos reales desde 2003, evaluación desde 2005
    python estrategias.py --demo   # datos simulados
"""
import argparse
from pathlib import Path

import pandas as pd

from src import data
from src import strategies as st
from src.portfolio import run_weights, stats

TICKERS = ["SPY", "EFA", "AGG", "SHY"] + st.SECTORS
EVAL_START = "2005-01-01"
SPLIT = "2015-01-01"          # las reglas se publicaron entre 1988 y 2014

# nombre: (función, retardo de ejecución en días, referencia)
RULES = {
    "comprar y mantener SPY": (st.buy_hold, 0, "referencia"),
    "60/40 SPY y bonos": (st.sixty_forty, 0, "referencia"),
    "promedio de 10 meses": (st.faber_sma10, 1, "Faber 2007"),
    "momentum 12 meses": (st.tsmom_12m, 1, "Moskowitz et al. 2012"),
    "momentum dual": (st.dual_momentum, 1, "Antonacci 2014"),
    "momentum sectorial top 3": (st.sector_momentum, 1, "Jegadeesh y Titman 1993"),
    "RSI(2), ejecuta al mismo cierre": (st.rsi2_reversion, 0, "Connors y Alvarez 2008"),
    "RSI(2), ejecuta al día siguiente": (st.rsi2_reversion, 1, "Connors y Alvarez 2008"),
    "cambio de mes": (st.turn_of_month, 0, "Lakonishok y Smidt 1988"),
}


def show(title: str, t: pd.DataFrame) -> None:
    t = t.copy()
    for c in t.columns:
        if c in ("sharpe", "t_alfa", "beta"):
            t[c] = t[c].map(lambda v: "" if pd.isna(v) else f"{v:+.2f}")
        elif c == "operaciones_por_ano":
            t[c] = t[c].map(lambda v: f"{v:.1f}")
        elif c != "fuente":
            t[c] = t[c].map(lambda v: f"{v:.1%}")
    print(f"\n=== {title} ===")
    print(t.to_string())


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--demo", action="store_true")
    ap.add_argument("--outdir", default="resultados/estrategias")
    a = ap.parse_args()
    out = Path(a.outdir)
    out.mkdir(parents=True, exist_ok=True)

    p = data.synthetic_closes(TICKERS) if a.demo else data.download_closes(TICKERS)
    print("Activos disponibles:", ", ".join(f"{c} desde {p[c].first_valid_index().date()}" for c in p.columns))
    p = p.dropna(subset=["SPY"]).ffill()

    runs = {}
    for name, (fn, lag, src) in RULES.items():
        try:
            runs[name] = run_weights(p, fn(p), lag=lag).loc[EVAL_START:]
        except KeyError as e:
            print(f"[aviso] se omite '{name}': falta el activo {e}")
    bench = runs["comprar y mantener SPY"]["ret"]
    print(f"Evaluación: {bench.index[0].date()} a {bench.index[-1].date()} ({len(bench)} días). "
          "Costo: 5 pb por unidad de cartera negociada. Efectivo sin intereses.")

    def table(sl: slice) -> pd.DataFrame:
        rows = {}
        for name, r in runs.items():
            s = stats(r["ret"].loc[sl], bench.loc[sl])
            s["exposicion"] = r["exposure"].loc[sl].mean()
            s["operaciones_por_ano"] = r["turnover"].loc[sl].sum() / 2 / (len(r.loc[sl]) / 252)
            rows[name] = s
        return pd.DataFrame(rows).T

    full = table(slice(None))
    full["fuente"] = [RULES[n][2] for n in full.index]
    show("Período completo", full)
    full.to_csv(out / "periodo_completo.csv")
    cols = ["retorno_anual", "sharpe", "caida_maxima", "alfa_anual", "t_alfa"]
    first, second = table(slice(None, SPLIT)), table(slice(SPLIT, None))
    show(f"Hasta {SPLIT[:4]} (en parte anterior a la publicación de las reglas)", first[cols])
    show(f"Desde {SPLIT[:4]} (posterior a la publicación de todas las reglas)", second[cols])
    first.to_csv(out / "antes_2015.csv")
    second.to_csv(out / "desde_2015.csv")

    # Peores años y valor acumulado, para ver cuándo ayuda o estorba cada regla
    eq = pd.DataFrame({n: (1 + r["ret"]).cumprod() for n, r in runs.items()})
    yearly = eq.groupby(eq.index.year).last().pct_change()
    yearly.iloc[0] = eq.groupby(eq.index.year).last().iloc[0] - 1
    print("\n=== Retorno por año ===")
    print(yearly.map(lambda v: f"{v:+.1%}").T.to_string())
    yearly.to_csv(out / "retorno_por_ano.csv")
    eq.to_csv(out / "curvas.csv")
    if a.demo:
        print("\nAVISO: datos simulados; solo sirven para verificar la instalación.")


if __name__ == "__main__":
    main()
