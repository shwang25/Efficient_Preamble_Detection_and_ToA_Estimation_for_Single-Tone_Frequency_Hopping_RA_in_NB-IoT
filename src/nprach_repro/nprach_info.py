from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from .config import (
    NB_IOT_SAMPLING_RATE_HZ,
    PREAMBLE_PARAMETER_TABLE,
    TS_RATE_HZ,
    NPRACHConfig,
    PreambleFormatParameters,
    UEConfig,
    parse_subcarrier_spacing_hz,
)
from .hopping import generate_frequency_locations, wrap_to_max_scs


VALID_PERIODICITY_MS = {40, 80, 160, 320, 640, 1280, 2560}
VALID_SUBCARRIER_OFFSET = {0, 2, 12, 18, 24, 34, 36}
VALID_NUM_SUBCARRIERS = {12, 24, 36, 48}
VALID_NREP = {1, 2, 4, 8, 16, 32, 64, 128}
VALID_START_TIME_MS = {8, 16, 32, 64, 128, 256, 512, 1024}


@dataclass(frozen=True)
class NPRACHInfo:
    subcarrier_spacing_hz: float
    nfft: int
    sampling_rate_hz: float
    k: int
    nulsc: int
    preamble: PreambleFormatParameters
    frequency_location: np.ndarray
    frequency_location_local: np.ndarray
    num_symbol_groups: int
    symbol_samples: int
    cp_samples: int
    sg_length_samples: int
    start_samples: int
    first_active_sc: int
    total_active_sc: int
    norm_y: int
    max_scs: int
    max_contiguous_preambles: int
    gap_samples: int


def validate_nprach_config(ue_cfg: UEConfig, cfg: NPRACHConfig) -> None:
    if cfg.fmt not in PREAMBLE_PARAMETER_TABLE:
        raise ValueError(f"Only NPRACH formats 0 and 1 are supported, got {cfg.fmt}")
    if cfg.periodicity_ms not in VALID_PERIODICITY_MS:
        raise ValueError(f"Invalid periodicity: {cfg.periodicity_ms}")
    if cfg.subcarrier_offset not in VALID_SUBCARRIER_OFFSET:
        raise ValueError(f"Invalid subcarrier offset: {cfg.subcarrier_offset}")
    if cfg.num_subcarriers not in VALID_NUM_SUBCARRIERS:
        raise ValueError(f"Invalid number of subcarriers: {cfg.num_subcarriers}")
    if cfg.nrep not in VALID_NREP:
        raise ValueError(f"Invalid NRep: {cfg.nrep}")
    if cfg.start_time_ms not in VALID_START_TIME_MS:
        raise ValueError(f"Invalid start time: {cfg.start_time_ms}")
    if not 0 <= cfg.ninit < cfg.num_subcarriers:
        raise ValueError(f"NInit must be in [0, {cfg.num_subcarriers - 1}]")

    ul_spacing_hz = parse_subcarrier_spacing_hz(ue_cfg.nb_ul_subcarrier_spacing)
    k = int(round(ul_spacing_hz / 3_750.0))
    nulsc = int(round(12 * 15_000.0 / ul_spacing_hz))
    if cfg.subcarrier_offset + cfg.num_subcarriers > (k * nulsc):
        raise ValueError("Configured NPRACH resource exceeds the available narrowband uplink grid")


def get_nprach_info(ue_cfg: UEConfig, cfg: NPRACHConfig) -> NPRACHInfo:
    validate_nprach_config(ue_cfg, cfg)

    preamble = PREAMBLE_PARAMETER_TABLE[cfg.fmt]
    ul_spacing_hz = parse_subcarrier_spacing_hz(ue_cfg.nb_ul_subcarrier_spacing)
    subcarrier_spacing_hz = 3_750.0
    sampling_rate_hz = NB_IOT_SAMPLING_RATE_HZ
    nfft = int(round(sampling_rate_hz / subcarrier_spacing_hz))
    k = int(round(ul_spacing_hz / subcarrier_spacing_hz))
    nulsc = int(round(12 * 15_000.0 / ul_spacing_hz))

    frequency_location = generate_frequency_locations(ue_cfg, cfg)
    frequency_location_local = frequency_location - cfg.subcarrier_offset

    cp_samples = int(round(preamble.t_cp_ts * sampling_rate_hz / TS_RATE_HZ))
    symbol_samples = int(round((preamble.t_seq_ts / preamble.num_symbols) * sampling_rate_hz / TS_RATE_HZ))
    sg_length_samples = int(round((preamble.t_cp_ts + preamble.t_seq_ts) * sampling_rate_hz / TS_RATE_HZ))
    num_symbol_groups = preamble.p * cfg.nrep
    start_samples = int(round(cfg.start_time_ms * sampling_rate_hz / 1000.0))
    total_active_sc = k * nulsc
    first_active_sc = int((nfft / 2) - (total_active_sc / 2) + cfg.subcarrier_offset)
    norm_y = preamble.num_symbols * nfft

    contiguous_preambles = 64
    num_gaps = (cfg.nrep - 1) // contiguous_preambles
    nprach_length_ms = cfg.start_time_ms + cfg.nrep * (
        preamble.p * (preamble.t_cp_ts + preamble.t_seq_ts)
    ) / 30_720.0 + (num_gaps * 40.0)
    if nprach_length_ms > cfg.periodicity_ms:
        raise ValueError("Configured NPRACH transmission length exceeds periodicity")

    return NPRACHInfo(
        subcarrier_spacing_hz=subcarrier_spacing_hz,
        nfft=nfft,
        sampling_rate_hz=sampling_rate_hz,
        k=k,
        nulsc=nulsc,
        preamble=preamble,
        frequency_location=frequency_location.astype(int),
        frequency_location_local=frequency_location_local.astype(int),
        num_symbol_groups=num_symbol_groups,
        symbol_samples=symbol_samples,
        cp_samples=cp_samples,
        sg_length_samples=sg_length_samples,
        start_samples=start_samples,
        first_active_sc=first_active_sc,
        total_active_sc=total_active_sc,
        norm_y=norm_y,
        max_scs=6,
        max_contiguous_preambles=contiguous_preambles,
        gap_samples=int(round(40.0 * sampling_rate_hz / 1000.0)),
    )
