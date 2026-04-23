from __future__ import annotations

from dataclasses import dataclass, replace

import numpy as np

from .config import ChannelConfig, DetectorConfig, NPRACHConfig, UEConfig, default_threshold
from .detector_mincomb import detect_minimum_combinations
from .nprach_waveform import simulate_received_waveform
from .utils import build_candidate_patterns


@dataclass(frozen=True)
class ThresholdCalibrationResult:
    detector: str
    metric_name: str
    metric_normalized: bool
    format: str
    nrep: int
    num_subcarriers: int
    num_rx_antennas: int
    channel_profile: str
    cfo_hz: float
    snr_db_list: list[float]
    target_false_alarm_probability: float
    target_percentile: float
    calibration_trials_per_snr: int
    total_calibration_trials: int
    seed: int
    calibrated_threshold: float
    empirical_false_alarm_probability: float
    matlab_default_threshold: float
    peak_metric_quantiles: dict[str, float]
    peak_metrics: np.ndarray


def _quantile_map(values: np.ndarray) -> dict[str, float]:
    quantiles = {
        "p50": 0.50,
        "p90": 0.90,
        "p95": 0.95,
        "p99": 0.99,
        "p99_9": 0.999,
    }
    return {label: float(np.quantile(values, q)) for label, q in quantiles.items()}


def _conservative_threshold_from_peaks(
    peak_metrics: np.ndarray,
    target_false_alarm_probability: float,
) -> tuple[float, float]:
    if peak_metrics.size == 0:
        raise ValueError("At least one peak metric is required for calibration")
    sorted_peaks = np.sort(np.asarray(peak_metrics, dtype=float))
    allowed_false_alarms = int(np.floor(target_false_alarm_probability * sorted_peaks.size))
    if allowed_false_alarms <= 0:
        threshold = float(np.nextafter(sorted_peaks[-1], np.inf))
    else:
        threshold = float(sorted_peaks[-allowed_false_alarms])
    empirical_false_alarm_probability = float(np.mean(sorted_peaks >= threshold))
    return threshold, empirical_false_alarm_probability


def calibrate_empirical_threshold(
    ue_cfg: UEConfig,
    cfg: NPRACHConfig,
    channel_cfg: ChannelConfig,
    detector_cfg: DetectorConfig,
    snr_db_list: list[float],
    num_trials_per_snr: int = 1000,
    target_false_alarm_probability: float = 0.001,
    seed: int = 0,
) -> ThresholdCalibrationResult:
    if num_trials_per_snr <= 0:
        raise ValueError("num_trials_per_snr must be positive")
    if not 0.0 < target_false_alarm_probability < 1.0:
        raise ValueError("target_false_alarm_probability must be between 0 and 1")

    rng = np.random.default_rng(seed)
    candidate_patterns = build_candidate_patterns(ue_cfg, cfg)
    peak_metrics = np.empty(len(snr_db_list) * num_trials_per_snr, dtype=float)
    peak_index = 0
    thresholdless_detector_cfg = replace(detector_cfg, threshold=float("inf"))

    for snr_db in snr_db_list:
        noise_channel_cfg = replace(channel_cfg, snr_db=float(snr_db), signal_present=False)
        for _ in range(num_trials_per_snr):
            generated = simulate_received_waveform(ue_cfg, cfg, noise_channel_cfg, rng)
            detection = detect_minimum_combinations(
                waveform=generated.rx_waveform,
                ue_cfg=ue_cfg,
                base_cfg=cfg,
                detector_cfg=thresholdless_detector_cfg,
                threshold=float("inf"),
                candidate_patterns=candidate_patterns,
            )
            peak_metrics[peak_index] = detection.peak_metric
            peak_index += 1

    calibrated_threshold, empirical_false_alarm_probability = _conservative_threshold_from_peaks(
        peak_metrics=peak_metrics,
        target_false_alarm_probability=target_false_alarm_probability,
    )

    return ThresholdCalibrationResult(
        detector="minimum_combinations",
        metric_name="peak_metric",
        metric_normalized=True,
        format=cfg.fmt,
        nrep=cfg.nrep,
        num_subcarriers=cfg.num_subcarriers,
        num_rx_antennas=channel_cfg.num_rx_antennas,
        channel_profile=channel_cfg.profile,
        cfo_hz=channel_cfg.cfo_hz,
        snr_db_list=[float(value) for value in snr_db_list],
        target_false_alarm_probability=float(target_false_alarm_probability),
        target_percentile=float(1.0 - target_false_alarm_probability),
        calibration_trials_per_snr=int(num_trials_per_snr),
        total_calibration_trials=int(peak_metrics.size),
        seed=int(seed),
        calibrated_threshold=calibrated_threshold,
        empirical_false_alarm_probability=empirical_false_alarm_probability,
        matlab_default_threshold=float(default_threshold(cfg)),
        peak_metric_quantiles=_quantile_map(peak_metrics),
        peak_metrics=peak_metrics,
    )
