"""Parámetros de la estrategia y de las reglas de salida.

Todos los umbrales viven aquí para que cualquier cambio quede explícito y
versionado. Los valores por defecto son una interpretación propia de apuntes
públicos de terceros; no provienen de material oficial.
"""
from dataclasses import dataclass, replace
from typing import Optional


@dataclass(frozen=True)
class StrategyParams:
    # Promedios móviles (en barras del marco temporal elegido)
    ma_fast: int = 20
    ma_slow: int = 40
    ma_floor1: int = 100
    ma_floor2: int = 200

    # Tendencia: PM20 por encima del PM40 durante `trend_bars` barras seguidas
    trend_bars: int = 10
    require_rising_slow: bool = True

    # Retroceso a la "zona barata": el mínimo toca o se acerca al PM40
    pullback_lookback: int = 5
    touch_pct: float = 0.005      # hasta 0,5 % por encima del PM40 cuenta como toque
    max_break_pct: float = 0.01   # el cierre no puede quedar más de 1 % por debajo del PM40

    # Ruptura: vela verde y sólida que cierra sobre el máximo de las barras previas
    break_bars: int = 2
    min_body_ratio: float = 0.5   # cuerpo >= 50 % del rango de la vela

    # No comprar lejos del PM40
    max_dist_pct: float = 0.02

    # Clasificación de la caída previa (normal / fuerte)
    strong_fall_pct: float = 0.01

    # Filtro opcional de "piso fuerte": precio sobre PM100 y PM200, PM100 > PM200
    require_floor: bool = False


@dataclass(frozen=True)
class ExitRule:
    name: str
    target_pct: Optional[float] = None       # objetivo de ganancia
    stop_pct: Optional[float] = None         # stop fijo bajo el precio de entrada
    stop_at_pullback_low: bool = False       # stop bajo el mínimo del retroceso
    stop_buffer_pct: float = 0.002
    max_hold: Optional[int] = None           # salida por tiempo (barras)
    exit_below_ma: Optional[int] = None      # salida si el cierre cae bajo este PM


@dataclass(frozen=True)
class Costs:
    slippage_pct: float = 0.0002    # 2 puntos básicos por lado
    commission_pct: float = 0.0     # comisión proporcional por lado


# Las reglas de salida NO provienen del método original (no se encontraron
# publicadas). Se prueban tres familias razonables, sin optimizar ninguna.
EXIT_RULES = {
    "1d": [
        ExitRule("objetivo3_stop2", target_pct=0.03, stop_pct=0.02, max_hold=15),
        ExitRule("stop_piso_sale_pm20", stop_at_pullback_low=True, exit_below_ma=20, max_hold=40),
        ExitRule("tiempo_5_barras", stop_pct=0.03, max_hold=5),
    ],
    "1h": [
        ExitRule("objetivo1_stop07", target_pct=0.010, stop_pct=0.007, max_hold=21),
        ExitRule("stop_piso_sale_pm20", stop_at_pullback_low=True, exit_below_ma=20, max_hold=35),
        ExitRule("tiempo_7_barras", stop_pct=0.01, max_hold=7),
    ],
}


def with_floor(p: StrategyParams) -> StrategyParams:
    return replace(p, require_floor=True)
