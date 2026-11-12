"""Diagnóstico de la señal: ¿el resultado depende de la interpretación de las reglas?

Evalúa variantes de la entrada, períodos, régimen de mercado y otros índices.
Para aislar la calidad de la entrada no usa reglas de salida: mide qué hace el
precio en las barras posteriores a cada señal y lo compara con una barra cualquiera.

    python diagnostico.py                 # SPY, QQQ, IWM y DIA en diario
    python diagnostico.py --demo          # datos simulados
"""
import argparse
from dataclasses import replace
from pathlib import Path

import numpy as np
import pandas as pd

from src import data
from src.config import StrategyParams
from src.metrics import summarize
from src.signals import pm40_signals

BASE = StrategyParams()
WARMUP = BASE.ma_floor2 + BASE.trend_bars

VARIANTS = {
    "A base (ruptura 2 barras)": BASE,
    "B ruptura 1 barra, sin exigir cuerpo": replace(BASE, break_bars=1, min_body_ratio=0.0),
    "C ruptura 3 barras": replace(BASE, break_bars=3),
    "D base sin filtro de cercanía": replace(BASE, max_dist_pct=None),
    "E base + piso fuerte": replace(BASE, require_floor=True),
    "F base, solo caída normal": replace(BASE, fall_filter="normal"),
    "G base, solo caída fuerte": replace(BASE, fall_filter="fuerte"),
    "H primer toque del PM40": replace(BASE, entry_mode="touch"),
    "I toque con vela verde": replace(BASE, entry_mode="touch_green"),
    "J martillo en el PM40": replace(BASE, entry_mode="hammer"),
    "K toque + piso fuerte": replace(BASE, entry_mode="touch", require_floor=True),
    "L toque, tendencia de 5 barras": replace(BASE, entry_mode="touch", trend_bars=5),
}

PERIODS = [("2005-2009", "2005", "2009"), ("2010-2014", "2010", "2014"), ("2015-2019", "2015", "2019"),
           ("2020-2022", "2020", "2022"), ("2023-hoy", "2023", "2100")]


def forward_stats(df: pd.DataFrame, k: int) -> pd.DataFrame:
    """Retorno, máxima ganancia (MFE) y máxima pérdida (MAE) de las k barras
    posteriores, entrando en la apertura de la barra siguiente."""
    entry = df["Open"].shift(-1)
    out = pd.DataFrame(index=df.index)
    out["ret"] = df["Open"].shift(-(k + 1)) / entry - 1
    out["mfe"] = df["High"].rolling(k).max().shift(-k) / entry - 1
    out["mae"] = df["Low"].rolling(k).min().shift(-k) / entry - 1
    return out


def compare(fs: pd.DataFrame, mask: pd.Series, rng: np.random.Generator) -> dict:
    """Compara las barras con señal contra todas las barras válidas."""
    allr = fs["ret"].dropna()
    sig = fs.loc[mask.reindex(fs.index, fill_value=False) & fs["ret"].notna()]
    n = len(sig)
    row = dict(senales=n)
    if n < 8:
        return row
    s, a = sig["ret"].to_numpy(), allr.to_numpy()
    diff = s.mean() - a.mean()
    t = diff / np.sqrt(s.var(ddof=1) / n + a.var(ddof=1) / len(a))
    boot = rng.choice(s, (2000, n), replace=True).mean(axis=1) - a.mean()
    row.update(media_senal=s.mean(), media_todas=a.mean(), diferencia=diff,
               ic95_inf=np.percentile(boot, 2.5), ic95_sup=np.percentile(boot, 97.5), t=t,
               pct_pos_senal=(s > 0).mean(), pct_pos_todas=(a > 0).mean(),
               sube2_senal=(sig["mfe"] >= 0.02).mean(), sube2_todas=(fs["mfe"].dropna() >= 0.02).mean(),
               baja2_senal=(sig["mae"] <= -0.02).mean(), baja2_todas=(fs["mae"].dropna() <= -0.02).mean())
    return row


def show(title: str, table: pd.DataFrame) -> None:
    t = table.copy()
    for c in t.columns:
        if c == "senales":
            t[c] = t[c].map(lambda v: f"{int(v)}")
        elif c in ("t", "sharpe"):
            t[c] = t[c].map(lambda v: "" if pd.isna(v) else f"{v:+.2f}")
        else:
            t[c] = t[c].map(lambda v: "" if pd.isna(v) else f"{v:+.2%}" if c.startswith(("dif", "ic", "media")) else f"{v:.1%}")
    print(f"\n=== {title} ===")
    print(t.to_string())


def trend_baselines(df: pd.DataFrame) -> pd.DataFrame:
    """Usos alternativos de los promedios: como filtro de exposición, no como gatillo."""
    c = df["Close"]
    r = c.pct_change().fillna(0)
    sma = {n: c.rolling(n).mean() for n in (20, 40, 200)}
    rules = {"comprar y mantener": pd.Series(True, index=c.index),
             "invertido solo si cierre > PM200": c > sma[200],
             "invertido solo si PM20 > PM40": sma[20] > sma[40],
             "invertido solo si cierre > PM40": c > sma[40]}
    rows = {}
    for name, cond in rules.items():
        pos = cond.shift(1, fill_value=False).iloc[WARMUP:]
        eq = (1 + r.iloc[WARMUP:] * pos).cumprod()
        m = summarize(eq)
        rows[name] = dict(retorno_anual=m["retorno_anual"], caida_maxima=m["caida_maxima"],
                          sharpe=m["sharpe"], exposicion=pos.mean())
    return pd.DataFrame(rows).T


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--tickers", default="SPY,QQQ,IWM,DIA")
    ap.add_argument("--demo", action="store_true")
    ap.add_argument("--outdir", default="resultados/diagnostico")
    a = ap.parse_args()
    out = Path(a.outdir)
    out.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(0)

    frames = {}
    if a.demo:
        frames = {f"SIM{i}": data.synthetic(4000, seed=i) for i in range(3)}
    else:
        for tk in a.tickers.split(","):
            try:
                frames[tk] = data.download(tk, "1d", "2005-01-01")
            except Exception as e:                       # un ticker caído no detiene el resto
                print(f"[aviso] no se pudo descargar {tk}: {e}")
    main_tk = next(iter(frames))
    for tk, df in frames.items():
        print(f"{tk}: {len(df)} barras, {df.index[0].date()} a {df.index[-1].date()}")

    # Señales de cada variante por ticker (se calculan una sola vez)
    sigs = {tk: {name: pm40_signals(df, p)["signal"].iloc[WARMUP:] for name, p in VARIANTS.items()}
            for tk, df in frames.items()}
    fwd = {tk: {k: forward_stats(df, k).iloc[WARMUP:] for k in (3, 5, 10, 20)} for tk, df in frames.items()}

    # 1) Variantes de entrada en el activo principal, a 5 y 10 barras
    for k in (5, 10):
        tab = pd.DataFrame({name: compare(fwd[main_tk][k], sigs[main_tk][name], rng) for name in VARIANTS}).T
        show(f"1. Variantes de entrada en {main_tk}, {k} barras después", tab)
        tab.to_csv(out / f"variantes_{main_tk}_{k}.csv")

    # 2) Horizontes para las dos lecturas principales
    for name in ("A base (ruptura 2 barras)", "H primer toque del PM40"):
        tab = pd.DataFrame({f"{k} barras": compare(fwd[main_tk][k], sigs[main_tk][name], rng)
                            for k in (3, 5, 10, 20)}).T
        show(f"2. Horizontes en {main_tk}: {name}", tab[["senales", "media_senal", "media_todas", "diferencia", "t"]])

    # 3) Por período (cada período se compara contra sus propias barras)
    for name in ("A base (ruptura 2 barras)", "H primer toque del PM40"):
        rows = {}
        for label, y0, y1 in PERIODS:
            fs = fwd[main_tk][5].loc[y0:y1]
            if len(fs) > 50:
                rows[label] = compare(fs, sigs[main_tk][name], rng)
        tab = pd.DataFrame(rows).T
        cols = [c for c in ("senales", "media_senal", "media_todas", "diferencia", "t") if c in tab.columns]
        show(f"3. Por período en {main_tk}, 5 barras: {name}", tab[cols])

    # 4) Por régimen: sobre o bajo el PM200
    c = frames[main_tk]["Close"]
    above = (c > c.rolling(200).mean()).iloc[WARMUP:]
    for name in ("A base (ruptura 2 barras)", "H primer toque del PM40"):
        rows = {"sobre PM200": compare(fwd[main_tk][5][above], sigs[main_tk][name], rng),
                "bajo PM200": compare(fwd[main_tk][5][~above], sigs[main_tk][name], rng)}
        tab = pd.DataFrame(rows).T
        cols = [c_ for c_ in ("senales", "media_senal", "media_todas", "diferencia", "t") if c_ in tab.columns]
        show(f"4. Por régimen en {main_tk}, 5 barras: {name}", tab[cols])

    # 5) Otros índices y resultado agrupado
    for name in ("A base (ruptura 2 barras)", "H primer toque del PM40", "J martillo en el PM40"):
        rows = {tk: compare(fwd[tk][5], sigs[tk][name], rng) for tk in frames}
        pooled_fs = pd.concat([fwd[tk][5].reset_index(drop=True) for tk in frames], ignore_index=True)
        pooled_sig = pd.concat([sigs[tk][name].reset_index(drop=True) for tk in frames], ignore_index=True)
        rows["AGRUPADO"] = compare(pooled_fs, pooled_sig, rng)
        tab = pd.DataFrame(rows).T
        show(f"5. Otros índices, 5 barras: {name}",
             tab[["senales", "media_senal", "media_todas", "diferencia", "ic95_inf", "ic95_sup", "t"]])
        tab.to_csv(out / f"indices_{name[0]}.csv")

    # 6) Los promedios como filtro de exposición
    for tk, df in frames.items():
        show(f"6. Promedios como filtro de exposición en {tk} (sin costos, ejecución al cierre)", trend_baselines(df))

    n_tests = len(VARIANTS) * 2
    print(f"\nNota: la sección 1 hace {n_tests} comparaciones; con tantas, alguna |t| > 2 aparece por azar. "
          f"Con corrección de Bonferroni el umbral sube a |t| > {2.9:.1f} aproximadamente. "
          "Las señales cercanas en el tiempo se solapan, lo que hace que t sobreestime la certeza.")


if __name__ == "__main__":
    main()
