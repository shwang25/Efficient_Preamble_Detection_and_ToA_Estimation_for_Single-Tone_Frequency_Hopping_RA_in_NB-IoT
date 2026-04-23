from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

import numpy as np

from .config import DetectorConfig, NPRACHConfig, UEConfig, default_threshold
from .nprach_info import get_nprach_info
from .utils import CandidatePattern, build_candidate_patterns


@dataclass(frozen=True)
class DetectionInfo:
    detection_threshold: float
    threshold_source: str
    detection_peaks: np.ndarray


@dataclass(frozen=True)
class DetectionResult:
    detected_ninit: int | None
    timing_offset_samples: float | None
    timing_offset_seconds: float | None
    peak_metric: float
    peak_bin: int | None
    detection_info: DetectionInfo
    best_spectrum: np.ndarray | None
    search_window_bins: int

    @property
    def detected(self) -> bool:
        return self.detected_ninit is not None


def compute_search_window_bins(
    info,
    detector_cfg: DetectorConfig,
) -> int:
    tolerated_samples = int(np.ceil(detector_cfg.time_error_tolerance_s * info.sampling_rate_hz))
    max_offset_samples = info.cp_samples
    if detector_cfg.max_timing_offset_us is not None:
        max_offset_samples = min(
            info.cp_samples,
            int(np.floor(detector_cfg.max_timing_offset_us * 1e-6 * info.sampling_rate_hz)),
        )
    window = int(min(detector_cfg.fft_size, ((max_offset_samples + tolerated_samples) * detector_cfg.fft_size) / info.nfft))
    return max(1, min(detector_cfg.fft_size, window))


def quadratic_peak_offset(left: float, center: float, right: float) -> float:
    denominator = (2.0 * center) - left - right
    if abs(denominator) < 1e-12:
        return 0.0
    return 0.5 * (right - left) / denominator


def _column_rms(symbols: np.ndarray) -> np.ndarray:
    return np.sqrt(np.mean(np.abs(symbols) ** 2, axis=0, keepdims=True))


def _precompute_symbol_group_tones(
    waveform: np.ndarray,
    info,
    base_cfg: NPRACHConfig,
) -> np.ndarray:
    num_rx_antennas = waveform.shape[1]
    max_contiguous_symbol_groups = info.max_contiguous_preambles * info.preamble.p
    tone_grid = np.zeros(
        (info.num_symbol_groups, base_cfg.num_subcarriers, num_rx_antennas),
        dtype=np.complex128,
    )
    for rx_idx in range(num_rx_antennas):
        gap_count = 0
        for sg_idx in range(info.num_symbol_groups):
            if sg_idx >= max_contiguous_symbol_groups and (sg_idx % max_contiguous_symbol_groups) == 0:
                gap_count += 1
            sg_start = info.start_samples + (gap_count * info.gap_samples) + (sg_idx * info.sg_length_samples)
            sg_stop = sg_start + info.sg_length_samples
            rx_group = waveform[sg_start:sg_stop, rx_idx]
            rx_group_no_cp = rx_group[info.cp_samples:]
            symbols = rx_group_no_cp.reshape((info.nfft, info.preamble.num_symbols), order="F")
            symbols = symbols / (_column_rms(symbols) + np.finfo(float).eps)
            symbol_fft = np.fft.fftshift(np.fft.fft(symbols, axis=0), axes=0)
            active_scs = symbol_fft[info.first_active_sc : info.first_active_sc + base_cfg.num_subcarriers, :]
            tone_grid[sg_idx, :, rx_idx] = np.sum(active_scs, axis=1) / info.norm_y
    return tone_grid


def _build_minimum_vector(y: np.ndarray, delta1: np.ndarray, max_scs: int) -> np.ndarray:
    z_values = y[:-1] * np.conj(y[1:])
    v = np.zeros((2 * max_scs) + 1, dtype=np.complex128)
    for idx, hop in enumerate(delta1):
        v[max_scs + hop] += z_values[idx]
    return v


def _reference_vector(delta1: Sequence[int], max_scs: int) -> np.ndarray:
    v_ref = np.zeros((2 * max_scs) + 1, dtype=float)
    for hop in delta1:
        v_ref[max_scs + int(hop)] += 1.0
    return v_ref


def _ensure_2d_waveform(waveform: np.ndarray) -> np.ndarray:
    waveform = np.asarray(waveform, dtype=np.complex128)
    if waveform.ndim == 1:
        return waveform[:, None]
    if waveform.ndim != 2:
        raise ValueError("Waveform must be a 1-D or 2-D complex array")
    return waveform


def detect_minimum_combinations(
    waveform: np.ndarray,
    ue_cfg: UEConfig,
    base_cfg: NPRACHConfig,
    detector_cfg: DetectorConfig,
    threshold: float | None = None,
    candidate_patterns: list[CandidatePattern] | None = None,
) -> DetectionResult:
    waveform = _ensure_2d_waveform(waveform)
    candidate_patterns = candidate_patterns or build_candidate_patterns(ue_cfg, base_cfg)
    info = get_nprach_info(ue_cfg, base_cfg)
    threshold_source = "custom" if threshold is not None else "matlab_default"
    threshold = float(default_threshold(base_cfg) if threshold is None else threshold)
    search_window = compute_search_window_bins(info, detector_cfg)

    num_rx_antennas = waveform.shape[1]
    max_contiguous_symbol_groups = info.max_contiguous_preambles * info.preamble.p
    num_gaps = (base_cfg.nrep - 1) // info.max_contiguous_preambles
    num_samples_needed = (
        info.start_samples
        + (info.num_symbol_groups * info.sg_length_samples)
        + (num_gaps * info.gap_samples)
    )
    if waveform.shape[0] < num_samples_needed:
        pad_rows = num_samples_needed - waveform.shape[0]
        waveform = np.vstack([waveform, np.zeros((pad_rows, num_rx_antennas), dtype=np.complex128)])

    t = np.arange(waveform.shape[0], dtype=float) / info.sampling_rate_hz
    waveform = waveform * np.exp(-1j * np.pi * info.subcarrier_spacing_hz * t)[:, None]
    tone_grid = _precompute_symbol_group_tones(waveform, info, base_cfg)

    candidate_metrics = np.zeros(base_cfg.num_subcarriers, dtype=float)
    spectra: list[np.ndarray] = []
    for pattern in candidate_patterns:
        combined_spectrum = np.zeros(detector_cfg.fft_size, dtype=float)
        max_u2_sum = 0.0
        for rx_idx in range(num_rx_antennas):
            sg_indices = np.arange(info.num_symbol_groups, dtype=int)
            y = tone_grid[sg_indices, pattern.local_frequency_location, rx_idx]
            v = _build_minimum_vector(y, pattern.delta1, info.max_scs)
            u = np.fft.fft(v, detector_cfg.fft_size)
            u2 = np.abs(u) ** 2
            max_u2_sum += float(np.max(u2))
            combined_spectrum += u2

        v_ref = _reference_vector(pattern.delta1, info.max_scs)
        u2_ref = np.abs(np.fft.fft(v_ref, detector_cfg.fft_size)) ** 2
        norm_e = np.sqrt(max_u2_sum * float(np.max(u2_ref)) * num_rx_antennas)
        combined_spectrum = combined_spectrum / (norm_e + np.finfo(float).eps)
        spectra.append(combined_spectrum)
        candidate_metrics[pattern.ninit] = float(np.sqrt(np.max(combined_spectrum[:search_window])))

    best_idx = int(np.argmax(candidate_metrics))
    best_spectrum = spectra[best_idx]
    peak_bin = int(np.argmax(best_spectrum[:search_window]))
    peak_metric = float(candidate_metrics[best_idx])
    detected = peak_metric >= threshold

    timing_offset_samples = None
    timing_offset_seconds = None
    detected_ninit = None
    if detected:
        epsilon = 0.0
        if 0 < peak_bin < (detector_cfg.fft_size - 1):
            epsilon = quadratic_peak_offset(
                float(best_spectrum[peak_bin - 1]),
                peak_metric,
                float(best_spectrum[peak_bin + 1]),
            )
        timing_offset_samples = (peak_bin + epsilon) * info.nfft / detector_cfg.fft_size
        timing_offset_seconds = timing_offset_samples / info.sampling_rate_hz
        detected_ninit = best_idx

    return DetectionResult(
        detected_ninit=detected_ninit,
        timing_offset_samples=timing_offset_samples,
        timing_offset_seconds=timing_offset_seconds,
        peak_metric=peak_metric,
        peak_bin=peak_bin if detected else None,
        detection_info=DetectionInfo(
            detection_threshold=threshold,
            threshold_source=threshold_source,
            detection_peaks=candidate_metrics,
        ),
        best_spectrum=best_spectrum,
        search_window_bins=search_window,
    )
