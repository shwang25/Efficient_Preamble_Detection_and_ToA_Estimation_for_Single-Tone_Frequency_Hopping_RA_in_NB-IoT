from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from .config import ChannelConfig, NPRACHConfig, UEConfig
from .nprach_info import NPRACHInfo, get_nprach_info


@dataclass(frozen=True)
class GeneratedWaveform:
    tx_waveform: np.ndarray
    rx_waveform: np.ndarray
    info: NPRACHInfo
    true_offset_samples: int
    true_offset_seconds: float
    timing_offset_us: float


def _tone_symbol(info: NPRACHInfo, absolute_tone_index: int) -> np.ndarray:
    n = np.arange(info.nfft, dtype=float)
    relative_bin = absolute_tone_index - (info.nfft / 2)
    # Match the implicit LTE-style OFDM/IFFT normalization assumed by the
    # MATLAB noise formula. Without this 1/Nfft factor, the detector's
    # per-symbol RMS normalization leaves the useful signal unchanged but
    # makes the added noise effectively too weak by about Nfft.
    return np.exp(1j * 2.0 * np.pi * relative_bin * n / info.nfft) / info.nfft


def _symbol_group_waveform(info: NPRACHInfo, absolute_tone_index: int) -> np.ndarray:
    symbol = _tone_symbol(info, absolute_tone_index)
    data = np.tile(symbol, info.preamble.num_symbols)
    cp = data[-info.cp_samples :]
    return np.concatenate([cp, data])


def generate_nprach_waveform(
    ue_cfg: UEConfig,
    cfg: NPRACHConfig,
) -> tuple[np.ndarray, NPRACHInfo]:
    info = get_nprach_info(ue_cfg, cfg)
    max_contiguous_symbol_groups = info.max_contiguous_preambles * info.preamble.p
    gap_count = (info.num_symbol_groups - 1) // max_contiguous_symbol_groups
    total_length = (
        info.start_samples
        + (info.num_symbol_groups * info.sg_length_samples)
        + (gap_count * info.gap_samples)
    )
    waveform = np.zeros(total_length, dtype=np.complex128)

    inserted_gaps = 0
    for sg_idx in range(info.num_symbol_groups):
        if sg_idx >= max_contiguous_symbol_groups and (sg_idx % max_contiguous_symbol_groups) == 0:
            inserted_gaps += 1
        tone_local = int(info.frequency_location_local[sg_idx])
        tone_abs = info.first_active_sc + tone_local
        sg_waveform = _symbol_group_waveform(info, tone_abs)
        start = info.start_samples + (inserted_gaps * info.gap_samples) + (sg_idx * info.sg_length_samples)
        stop = start + info.sg_length_samples
        waveform[start:stop] += sg_waveform

    t = np.arange(total_length, dtype=float) / info.sampling_rate_hz
    waveform = waveform * np.exp(1j * np.pi * info.subcarrier_spacing_hz * t)
    return waveform, info


def _default_timing_offset_us(info: NPRACHInfo) -> float:
    cp_us = 1e6 * info.cp_samples / info.sampling_rate_hz
    return 0.5 * cp_us


def _select_timing_offset_us(
    info: NPRACHInfo,
    channel_cfg: ChannelConfig,
    rng: np.random.Generator,
) -> float:
    if channel_cfg.timing_offset_us is not None:
        return float(channel_cfg.timing_offset_us)
    if channel_cfg.timing_offset_range_us is not None:
        low_us, high_us = channel_cfg.timing_offset_range_us
        if high_us < low_us:
            raise ValueError("timing_offset_range_us must be ordered as (low, high)")
        return float(rng.uniform(float(low_us), float(high_us)))
    return _default_timing_offset_us(info)


def _apply_optional_flat_fading(
    waveform: np.ndarray,
    channel_cfg: ChannelConfig,
    rng: np.random.Generator,
) -> np.ndarray:
    rx = np.tile(waveform[:, None], (1, channel_cfg.num_rx_antennas))
    profile = channel_cfg.profile.strip().lower()
    if profile in {"flat", "rayleigh", "epa1_like", "epa1"}:
        coeffs = (
            rng.normal(size=channel_cfg.num_rx_antennas) + 1j * rng.normal(size=channel_cfg.num_rx_antennas)
        ) / np.sqrt(2.0)
        rx = rx * coeffs[None, :]
    elif profile != "awgn":
        raise ValueError(f"Unsupported channel profile: {channel_cfg.profile}")
    return rx


def simulate_received_waveform(
    ue_cfg: UEConfig,
    cfg: NPRACHConfig,
    channel_cfg: ChannelConfig,
    rng: np.random.Generator,
) -> GeneratedWaveform:
    if channel_cfg.signal_present:
        tx_waveform, info = generate_nprach_waveform(ue_cfg, cfg)
        timing_offset_us = _select_timing_offset_us(info, channel_cfg, rng)
        true_offset_samples = int(np.floor(timing_offset_us * 1e-6 * info.sampling_rate_hz))
        delayed_tx = np.concatenate([np.zeros(true_offset_samples, dtype=np.complex128), tx_waveform])
        rx_waveform = _apply_optional_flat_fading(delayed_tx, channel_cfg, rng)
    else:
        info = get_nprach_info(ue_cfg, cfg)
        timing_offset_us = 0.0
        true_offset_samples = 0
        noise_only_len = int(round(cfg.periodicity_ms * info.sampling_rate_hz / 1000.0))
        delayed_tx = np.zeros(noise_only_len, dtype=np.complex128)
        rx_waveform = np.zeros((noise_only_len, channel_cfg.num_rx_antennas), dtype=np.complex128)

    snr = 10.0 ** (channel_cfg.snr_db / 10.0)
    noise_scale = 1.0 / np.sqrt(2.0 * info.nfft * snr)
    noise = noise_scale * (
        rng.normal(size=rx_waveform.shape) + 1j * rng.normal(size=rx_waveform.shape)
    )
    rx_waveform = rx_waveform + noise

    t = np.arange(rx_waveform.shape[0], dtype=float) / info.sampling_rate_hz
    rx_waveform = rx_waveform * np.exp(1j * 2.0 * np.pi * channel_cfg.cfo_hz * t)[:, None]
    return GeneratedWaveform(
        tx_waveform=delayed_tx,
        rx_waveform=rx_waveform,
        info=info,
        true_offset_samples=true_offset_samples,
        true_offset_seconds=true_offset_samples / info.sampling_rate_hz,
        timing_offset_us=timing_offset_us,
    )
