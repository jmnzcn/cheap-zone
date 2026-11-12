"""Ejecuta el backtest de la estrategia PM40 y lo compara con comprar y mantener.

Ejemplos:
    python run_backtest.py                      # SPY diario desde 2005
    python run_backtest.py --interval 1h        # SPY por hora (unos 720 días)
    python run_backtest.py --csv mis_datos.csv  # datos propios
    python run_backtest.py --demo               # datos simulados, sin internet
"""
import argparse
from pathlib import Path

import pandas as pd

from src import data
from src.backtest import run_backtest
from src.config import EXIT_RULES, Costs, StrategyParams, with_floor
from src.metrics import edge_test, summarize
from src.signals import pm40_signals

PCT = ["retorno_total", "retorno_anual", "caida_maxima", "pct_ganadoras", "retorno_medio", "exposicion"]


def fmt(table: pd.DataFrame) -> str:
    t = table.copy()
    for col in t.columns:
        if col in PCT or col.startswith(("media_", "diferencia", "pct_")):
            t[col] = t[col].map(lambda v: "" if pd.isna(v) else f"{v:.2%}")
        elif col in ("sharpe", "factor_beneficio"):
            t[col] = t[col].map(lambda v: "" if pd.isna(v) else f"{v:.2f}")
        elif col == "valor_p":
            t[col] = t[col].map(lambda v: "" if pd.isna(v) else f"{v:.3f}")
        elif col in ("operaciones", "senales"):
            t[col] = t[col].map(lambda v: "" if pd.isna(v) else f"{int(v)}")
    return t.to_string()


def plot(curves: dict, title: str, path: Path) -> None:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    ink, muted, surface = "#0b0b0b", "#52514e", "#fcfcfb"
    palette = ["#2a78d6", "#eb6834", "#1baf7a"]
    fig, ax = plt.subplots(figsize=(11, 5.5), facecolor=surface)
    ax.set_facecolor(surface)
    names = list(curves)
    for i, name in enumerate(names):
        bench = i == 0
        ax.plot(curves[name].index, curves[name].values, lw=1.2 if bench else 2, label=name,
                color=muted if bench else palette[(i - 1) % 3])
    ax.set_yscale("log")
    from matplotlib.ticker import FuncFormatter
    for axis_fmt in (ax.yaxis.set_major_formatter, ax.yaxis.set_minor_formatter):
        axis_fmt(FuncFormatter(lambda v, _: f"{v:g}"))
    ax.set_title(title, loc="left", color=ink, fontsize=13, fontweight="bold")
    ax.set_ylabel("Valor de 1 unidad invertida (escala logarítmica)", color=muted)
    ax.grid(True, which="major", color="#e4e3df", lw=0.8)
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    for side in ("left", "bottom"):
        ax.spines[side].set_color("#c9c8c2")
    ax.tick_params(colors=muted)
    ax.legend(frameon=False, labelcolor=ink, loc="upper left")
    fig.tight_layout()
    fig.savefig(path, dpi=140)
    plt.close(fig)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--ticker", default="SPY")
    ap.add_argument("--interval", default="1d", choices=["1d", "1h"])
    ap.add_argument("--start", default="2005-01-01")
    ap.add_argument("--csv", help="ruta a un CSV propio con columnas Date, Open, High, Low, Close")
    ap.add_argument("--demo", action="store_true", help="usa datos simulados (no dicen nada del mercado)")
    ap.add_argument("--outdir", default="resultados")
    a = ap.parse_args()

    if a.demo:
        df, label = data.synthetic(), "DATOS SIMULADOS"
    elif a.csv:
        df, label = data.load_csv(a.csv), Path(a.csv).stem
    else:
        df, label = data.download(a.ticker, a.interval, a.start), f"{a.ticker} {a.interval}"

    out = Path(a.outdir)
    out.mkdir(parents=True, exist_ok=True)
    base = StrategyParams()
    warmup = base.ma_floor2 + base.trend_bars
    print(f"\n{label}: {len(df)} barras, de {df.index[0].date()} a {df.index[-1].date()}")

    bench = (df["Close"] / df["Close"].iloc[warmup]).iloc[warmup:]
    rows = {"comprar_y_mantener": summarize(bench)}
    curves = {"Comprar y mantener": bench}

    for tag, params in (("base", base), ("piso_fuerte", with_floor(base))):
        d = pm40_signals(df, params)
        n_sig = int(d["signal"].iloc[warmup:].sum())
        print(f"\nVariante '{tag}': {n_sig} señales "
              f"({d.iloc[warmup:].loc[d['signal'].iloc[warmup:], 'fall_type'].value_counts().to_dict()})")
        print("Prueba de ventaja de la señal (retorno posterior frente a una barra cualquiera):")
        edge = edge_test(d.iloc[warmup:])
        print(fmt(edge.set_index("horizonte")))
        edge.to_csv(out / f"ventaja_{tag}.csv", index=False)

        for rule in EXIT_RULES[a.interval]:
            res = run_backtest(d, rule, Costs(), start_idx=warmup)
            name = f"{tag}/{rule.name}"
            rows[name] = summarize(res.equity, res.trades)
            res.trades.to_csv(out / f"operaciones_{tag}_{rule.name}.csv", index=False)
            if tag == "base":
                curves[rule.name] = res.equity

    table = pd.DataFrame(rows).T
    print("\nResumen (costos incluidos):")
    print(fmt(table))
    table.to_csv(out / "resumen.csv")
    plot(curves, f"Estrategia PM40 frente a comprar y mantener ({label})", out / "curvas.png")
    print(f"\nArchivos guardados en la carpeta '{out}'.")
    if a.demo:
        print("AVISO: resultados sobre datos simulados; solo sirven para verificar la instalación.")


if __name__ == "__main__":
    main()
