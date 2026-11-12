"""Arma la página del panel y los documentos que se escriben en su almacén."""
import json, datetime, sys
from pathlib import Path

IDX = [("SPY", "S&amp;P 500"), ("QQQ", "Nasdaq 100"), ("IWM", "Russell 2000"), ("DIA", "Dow Jones")]

def val(field, fmt, where=None, src="activos", tone=False, row=None, cls=""):
    w = f' data-where="{where}"' if where else f' data-row="{row or 0}"'
    t = ' data-tone="change"' if tone else ""
    return (f'<span class="dash-skeleton {cls}" data-draw="val" data-source="{src}" data-field="{field}"{w} '
            f'data-fmt="{fmt}"{t}>—</span>')

cards = "\n".join(f'''    <article class="mp-card" id="tarjeta-{t.lower()}">
      <div class="mp-card-h"><span class="mp-name">{n}</span><span class="mp-tk">{t}</span></div>
      <div class="mp-price">{val("precio", "num2", f"ticker={t}")}</div>
      <div class="mp-line">{val("cambio_1d", "spct2", f"ticker={t}", tone=True)}<span class="mp-muted">último día</span></div>
      <div class="mp-line"><span class="mp-pill" data-draw="regimen" data-source="activos" data-field="sobre_pm200" data-where="ticker={t}">—</span></div>
      <div class="mp-line">{val("dist_pm200", "spct1", f"ticker={t}")}<span class="mp-muted">frente al PM200</span></div>
    </article>''' for t, n in IDX)

seg = "\n".join(f'      <button type="button" data-ticker="{t}" aria-pressed="{"true" if i == 0 else "false"}">{t}</button>'
                for i, (t, _) in enumerate(IDX))

html = (Path(__file__).parent / "plantilla.html").read_text(encoding="utf-8")
html = html.replace("<!--CARDS-->", cards).replace("<!--SEG-->", seg)
html = html.replace("<!--FECHA-->", val("fecha", "date", cls="mp-b"))
html = html.replace("<!--N_SOBRE-->", val("sobre", "int", src="resumen", cls="mp-b"))
html = html.replace("<!--N_TOTAL-->", val("total", "int", src="resumen", cls="mp-b"))
html = html.replace("<!--VOL-->", val("volatilidad_20d", "pct1", "ticker=SPY", cls="mp-b"))
html = html.replace("<!--VOLMED-->", val("volatilidad_mediana", "pct1", "ticker=SPY", cls="mp-b"))
html = html.replace("<!--B_MENOS-->", val("menos", "int", src="balance", cls="mp-b"))
html = html.replace("<!--B_TOTAL-->", val("total", "int", src="balance", cls="mp-b"))
html = html.replace("<!--B_CAIDA-->", val("menor_caida", "int", src="balance", cls="mp-b"))
html = html.replace("<!--SCRIPT-->", (Path(__file__).parent / "panel.js").read_text(encoding="utf-8"))
assert "<!--" not in html, "queda un marcador sin reemplazar"
out = Path(sys.argv[1]); out.mkdir(parents=True, exist_ok=True)
(out / "index.html").write_text(html, encoding="utf-8")
(out / "index.json").write_text(json.dumps({"text": html, "edit": {"via": "claude", "at": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")}}, ensure_ascii=False), encoding="utf-8")
print(len(html), "caracteres")
