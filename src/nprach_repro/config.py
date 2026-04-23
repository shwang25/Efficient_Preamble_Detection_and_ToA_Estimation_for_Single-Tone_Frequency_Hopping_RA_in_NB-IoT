from __future__ import annotations

from dataclasses import dataclass
from math import log2


TS_RATE_HZ = 30_720_000.0
NB_IOT_SAMPLING_RATE_HZ = 1_920_000.0
TIME_ERROR_TOLERANCE_S = 3.646e-6


@dataclass(frozen=True)
class PreambleFormatParameters:
    fmt: str
    g: int
    p: int
    num_symbols: int
    t_cp_ts: int
    t_seq_ts: int


PREAMBLE_PARAMETER_TABLE = {
    "0": PreambleFormatParameters("0", 4, 4, 5, 2048, 5 * 8192),
    "1": PreambleFormatParameters("1", 4, 4, 5, 8192, 5 * 8192),
}


@dataclass(frozen=True)
class UEConfig:
    cell_id: int = 0
    nb_ul_subcarrier_spacing: str = "15kHz"


@dataclass(frozen=True)
class NPRACHConfig:
    fmt: str = "0"
    periodicity_ms: int = 80
    subcarrier_offset: int = 0
    num_subcarriers: int = 48
    nrep: int = 8
    start_time_ms: int = 8
    ninit: int = 0


@dataclass(frozen=True)
class DetectorConfig:
    fft_size: int = 256
    threshold: float | None = None
    time_error_tolerance_s: float = TIME_ERROR_TOLERANCE_S


@dataclass(frozen=True)
class ChannelConfig:
    profile: str = "awgn"
    snr_db: float = 0.0
    cfo_hz: float = 200.0
    num_rx_antennas: int = 2
    signal_present: bool = True
    timing_offset_us: float | None = None


def toa_limit_us(fmt: str) -> float:
    if fmt == "0":
        return 66.67
    if fmt == "1":
        return 259.0
    raise ValueError(f"Unsupported NPRACH format: {fmt}")


def parse_subcarrier_spacing_hz(value: str) -> float:
    value = value.strip().lower()
    if value == "15khz":
        return 15_000.0
    if value == "3.75khz":
        return 3_750.0
    raise ValueError(f"Unsupported uplink subcarrier spacing: {value}")


def default_threshold(cfg: NPRACHConfig) -> float:
    if cfg.fmt == "2":
        return 0.017 - 0.002 * log2(cfg.nrep)
    return 0.025 - 0.003 * log2(cfg.nrep)
