from __future__ import annotations

from dataclasses import dataclass, replace
import json
from pathlib import Path

import numpy as np

from .config import ChannelConfig, DetectorConfig, NPRACHConfig, UEConfig, default_threshold
from .detector_mincomb import detect_minimum_combinations
from .nprach_waveform import simulate_received_waveform
from .utils import build_candidate_patterns, dump_json, ensure_dir


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


def save_threshold_cdf_plot(
    result: ThresholdCalibrationResult,
    output_path: Path,
) -> Path:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    ensure_dir(output_path.parent)
    sorted_peaks = np.sort(result.peak_metrics)
    empirical_cdf = np.arange(1, sorted_peaks.size + 1, dtype=float) / float(sorted_peaks.size)

    fig, ax = plt.subplots(figsize=(6.8, 4.2))
    ax.plot(sorted_peaks, empirical_cdf, linewidth=2.0, color="tab:blue", label="Empirical CDF")
    ax.axvline(
        result.calibrated_threshold,
        color="tab:red",
        linestyle="--",
        linewidth=1.4,
        label=f"Threshold = {result.calibrated_threshold:.5f}",
    )
    ax.axhline(
        result.target_percentile,
        color="tab:green",
        linestyle=":",
        linewidth=1.2,
        label=f"Target percentile = {100.0 * result.target_percentile:.3f}%",
    )
    ax.set_title(f"Noise-Only Peak Metric CDF ({result.total_calibration_trials} trials)")
    ax.set_xlabel("Peak metric X_max")
    ax.set_ylabel("Empirical CDF")
    ax.set_ylim(0.0, 1.01)
    ax.grid(True, linestyle=":", linewidth=0.6)
    ax.legend(loc="lower right")
    fig.tight_layout()
    fig.savefig(output_path, dpi=180)
    plt.close(fig)
    return output_path


def save_threshold_calibration(
    result: ThresholdCalibrationResult,
    json_path: Path,
    raw_peak_metrics_path: Path | None = None,
    cdf_plot_path: Path | None = None,
) -> Path:
    ensure_dir(json_path.parent)
    if raw_peak_metrics_path is not None:
        ensure_dir(raw_peak_metrics_path.parent)
        np.save(raw_peak_metrics_path, result.peak_metrics)

    payload = {
        "detector": result.detector,
        "metric_name": result.metric_name,
        "metric_normalized": result.metric_normalized,
        "format": result.format,
        "nrep": result.nrep,
        "num_subcarriers": result.num_subcarriers,
        "num_rx_antennas": result.num_rx_antennas,
        "channel_profile": result.channel_profile,
        "cfo_hz": result.cfo_hz,
        "snr_db_list": result.snr_db_list,
        "target_false_alarm_probability": result.target_false_alarm_probability,
        "target_percentile": result.target_percentile,
        "calibration_trials_per_snr": result.calibration_trials_per_snr,
        "total_calibration_trials": result.total_calibration_trials,
        "seed": result.seed,
        "calibrated_threshold": result.calibrated_threshold,
        "empirical_false_alarm_probability": result.empirical_false_alarm_probability,
        "matlab_default_threshold": result.matlab_default_threshold,
        "peak_metric_quantiles": result.peak_metric_quantiles,
        "raw_peak_metrics_path": str(raw_peak_metrics_path) if raw_peak_metrics_path is not None else None,
        "cdf_plot_path": str(cdf_plot_path) if cdf_plot_path is not None else None,
    }
    dump_json(json_path, payload)
    return json_path


def load_calibrated_threshold(threshold_json_path: Path) -> tuple[float, dict[str, object]]:
    payload = json.loads(threshold_json_path.read_text(encoding="utf-8"))
    threshold = float(payload["calibrated_threshold"])
    return threshold, payload
