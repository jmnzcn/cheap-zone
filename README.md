# cheap-zone

Backtest en Python de una estrategia de retroceso al promedio móvil de 40 períodos sobre el SPY, comparada con la alternativa de comprar y mantener.

El objetivo del proyecto es responder con datos una pregunta concreta: **¿las reglas de entrada que se enseñan en seminarios populares de bolsa tienen una ventaja medible, o el resultado se explica por la tendencia general del mercado?**

> **Aviso.** Proyecto educativo. No constituye asesoría financiera ni una recomendación de inversión. Los resultados históricos no garantizan resultados futuros. El proyecto no está afiliado a ningún educador ni seminario; las reglas son una interpretación propia elaborada a partir de apuntes públicos de terceros y pueden diferir del método original.

## Estado del proyecto

| Etapa | Contenido | Estado |
|---|---|---|
| 1 | Señales de entrada sobre el SPY (diario y por hora) | Lista |
| 2 | Backtest con acciones y comparación con comprar y mantener | Lista |
| 2b | Diagnóstico de la señal: variantes de entrada, períodos, régimen y otros índices | Lista |
| 3 | Simulación con opciones (prima estimada con Black-Scholes) | Pendiente |
| 4 | Operación simulada con un bróker (paper trading) | Pendiente |

## Instalación y uso

Requiere Python 3.10 o superior.

```bash
python -m venv .venv
.venv\Scripts\activate          # en Windows; en macOS o Linux: source .venv/bin/activate
pip install -r requirements.txt

python run_backtest.py                 # SPY diario desde 2005
python run_backtest.py --interval 1h   # SPY por hora (aproximadamente 720 días)
python run_backtest.py --csv datos.csv # datos propios
python run_backtest.py --demo          # datos simulados, sin conexión
python diagnostico.py                  # diagnóstico en SPY, QQQ, IWM y DIA
pytest -q                              # pruebas del motor
```

El flujo de GitHub Actions (`.github/workflows/backtest.yml`) ejecuta las pruebas, el backtest y el diagnóstico en cada envío a `main` y publica los archivos como artefacto `resultados`.

Cada ejecución imprime un resumen y guarda en `resultados/` el cuadro comparativo (`resumen.csv`), la prueba de ventaja (`ventaja_*.csv`), el detalle de cada operación (`operaciones_*.csv`) y el gráfico de curvas de capital (`curvas.png`).

## Reglas de entrada

Se genera una señal al cierre de una barra cuando se cumplen todas las condiciones siguientes. Los umbrales están en `src/config.py`.

1. **Tendencia alcista clara.** El promedio móvil de 20 se mantiene por encima del de 40 durante 10 barras consecutivas y el de 40 es creciente.
2. **Retroceso a la zona de piso.** En las últimas 5 barras el mínimo tocó el promedio de 40 o se acercó a menos de 0,5 %, sin que el cierre quede más de 1 % por debajo.
3. **Ruptura de la caída.** Vela verde y sólida (cuerpo de al menos 50 % del rango) cuyo cierre supera el máximo de las 2 barras anteriores.
4. **Cercanía al piso.** El cierre no está más de 2 % por encima del promedio de 40.
5. **Piso fuerte (variante opcional).** El precio está sobre los promedios de 100 y 200, y el de 100 sobre el de 200.

Cada señal se etiqueta según la caída previa: *fuerte* si hubo una barra con descenso de 1 % o más, *normal* en caso contrario.

### Decisiones de interpretación

- La «ruptura de la línea bajista» se traza a mano en el método original. Aquí se sustituye por una regla objetiva: cierre por encima de los máximos recientes.
- **Las reglas de salida no forman parte del material consultado.** Se evalúan tres familias sin optimizar ninguna: objetivo y stop fijos, stop bajo el mínimo del retroceso con salida al perder el promedio de 20, y salida por tiempo.
- El método original opera opciones. En esta etapa se opera el activo subyacente para aislar la calidad de la señal; si la entrada no muestra ventaja con acciones, el apalancamiento de las opciones solo amplifica el resultado.

## Supuestos del motor

- La señal del cierre de la barra *t* se ejecuta en la apertura de *t+1*.
- Si el stop y el objetivo se alcanzan en la misma barra, se asume el stop.
- Si la apertura queda por debajo del stop, la salida ocurre a la apertura.
- Se descuentan 2 puntos básicos de deslizamiento por lado.
- Una posición a la vez, con todo el capital; el efectivo no genera intereses.

## Cómo leer los resultados

- **Resumen.** Compare `retorno_anual` y `caida_maxima` de cada variante con `comprar_y_mantener`. La columna `exposicion` indica la fracción del tiempo con posición abierta: una estrategia que pasa casi todo el tiempo en efectivo difícilmente supera al índice en retorno, aunque puede hacerlo en riesgo.
- **Prueba de ventaja.** Compara el retorno medio posterior a una señal con el de una barra cualquiera. El `valor_p` estima la probabilidad de observar esa diferencia por azar. Se calculan varios horizontes y variantes, por lo que un valor bajo aislado no es evidencia suficiente: debe repetirse en varios horizontes y sostenerse en subperíodos distintos.
- **Datos simulados.** El modo `--demo` usa una caminata aleatoria. Sirve para verificar la instalación; sus cifras carecen de significado financiero.

## Hallazgos (ejecución del 12 de noviembre de 2026)

Datos diarios de enero de 2005 a noviembre de 2026. Las cifras comparan el retorno medio de las 5 barras posteriores a la señal con el de una barra cualquiera del mismo activo.

| Lectura de la entrada | Señales (SPY) | Tras la señal | Barra cualquiera | Diferencia (IC 95 %) |
|---|---|---|---|---|
| Con vela de confirmación (regla base) | 93 | -0,48 % | +0,24 % | -0,72 % (-1,13 % a -0,34 %) |
| Primer toque del promedio de 40, sin confirmación | 143 | +0,39 % | +0,24 % | +0,15 % (-0,18 % a +0,47 %) |

1. **Las entradas con confirmación rinden menos que una barra cualquiera.** El resultado se mantiene al variar la regla de ruptura (1, 2 o 3 barras), al quitar el filtro de cercanía, con el filtro de piso fuerte, con velas de martillo y al agrupar SPY, QQQ, IWM y DIA (314 señales, diferencia de -0,52 %). El efecto se concentra de 2020 en adelante; entre 2005 y 2009 y entre 2015 y 2019 fue prácticamente nulo.
2. **Comprar en el primer toque, sin esperar confirmación, no se distingue del azar.** La diferencia es positiva en los cinco subperíodos, pero pequeña, y su intervalo de confianza incluye el cero (agrupado: +0,13 %, de -0,06 % a +0,32 %).
3. **Con las tres reglas de salida probadas, ninguna variante de la regla base superó a comprar y mantener** (11,16 % anual en el SPY); la mayoría terminó con pérdida.
4. **Como filtro de exposición, el promedio de 200 redujo la caída máxima del SPY de -55 % a -21 %**, con un retorno anual menor (8,9 % frente a 11,2 %) y sin considerar costos ni impuestos. En QQQ, IWM y DIA la reducción de la caída es similar y el costo en retorno, mayor.

Cautelas: las señales cercanas se solapan, por lo que los estadísticos sobreestiman la certeza; se realizaron más de veinte comparaciones; la variante de «primer toque» se definió después de observar el resultado de la regla base; y la comparación contra la media de la propia muestra introduce un sesgo negativo pequeño (del orden de 0,1 puntos a 10 barras en series aleatorias). Los hallazgos se refieren a esta codificación, no al método original, que opera opciones y admite criterio discrecional.

## Limitaciones

- Un solo activo y un solo conjunto de parámetros; no se realizó validación fuera de muestra.
- Los precios ajustados por dividendos de Yahoo Finance pueden cambiar retroactivamente.
- Los datos por hora cubren aproximadamente dos años, período insuficiente para abarcar un ciclo completo de mercado.
- No se modelan impuestos ni el costo de oportunidad del efectivo.

## Estructura

```
src/config.py      parámetros de la estrategia, reglas de salida y costos
src/data.py        descarga, lectura de CSV y serie simulada
src/signals.py     indicadores y señal de entrada
src/backtest.py    motor barra a barra
src/metrics.py     métricas y prueba de ventaja
run_backtest.py    punto de entrada
tests/             pruebas del motor
```
