from __future__ import annotations

from dataclasses import dataclass, replace

import numpy as np

from .config import ChannelConfig, DetectorConfig, NPRACHConfig, TIME_ERROR_TOLERANCE_S, UEConfig
from .detector_mincomb import DetectionResult, detect_minimum_combinations
from .nprach_waveform import GeneratedWaveform, simulate_received_waveform
from .utils import build_candidate_patterns


@dataclass(frozen=True)
class DetectionSweepPoint:
    snr_db: float
    num_transmissions: int
    correct_detection_count: int
    detection_probability: float


@dataclass(frozen=True)
class DetectionSweepResult:
    snr_db_list: list[float]
    points: list[DetectionSweepPoint]
    threshold: float
    threshold_source: str
    num_transmissions: int
    channel_profile: str
    cfo_hz: float
    configuration: dict[str, object]


def _is_correct_detection(
    detection: DetectionResult,
    generated: GeneratedWaveform,
    transmitted_ninit: int | None,
    tolerance_s: float = TIME_ERROR_TOLERANCE_S,
) -> bool:
    if transmitted_ninit is None or not detection.detected:
        return False
    if detection.detected_ninit != transmitted_ninit:
        return False
    if detection.timing_offset_seconds is None:
        return False
    return abs(detection.timing_offset_seconds - generated.true_offset_seconds) <= tolerance_s


def run_detection_example(
    ue_cfg: UEConfig,
    cfg: NPRACHConfig,
    channel_cfg: ChannelConfig,
    detector_cfg: DetectorConfig,
    snr_db_list: list[float],
    num_transmissions: int = 10,
    seed: int = 0,
    threshold_metadata: dict[str, object] | None = None,
) -> DetectionSweepResult:
    rng = np.random.default_rng(seed)
    points: list[DetectionSweepPoint] = []
    candidate_patterns = build_candidate_patterns(ue_cfg, cfg)
    threshold = None
    threshold_source = None
    for snr_db in snr_db_list:
        detected_count = 0
        snr_channel = replace(channel_cfg, snr_db=snr_db, signal_present=True)
        for _ in range(num_transmissions):
            generated = simulate_received_waveform(ue_cfg, cfg, snr_channel, rng)
            detection = detect_minimum_combinations(
                waveform=generated.rx_waveform,
                ue_cfg=ue_cfg,
                base_cfg=cfg,
                detector_cfg=detector_cfg,
                threshold=detector_cfg.threshold,
                candidate_patterns=candidate_patterns,
            )
            detected_count += int(_is_correct_detection(detection, generated, cfg.ninit))
            threshold = detection.detection_info.detection_threshold
            threshold_source = detection.detection_info.threshold_source
        points.append(
            DetectionSweepPoint(
                snr_db=float(snr_db),
                num_transmissions=num_transmissions,
                correct_detection_count=detected_count,
                detection_probability=detected_count / float(num_transmissions),
            )
        )
    return DetectionSweepResult(
        snr_db_list=[float(value) for value in snr_db_list],
        points=points,
        threshold=float(threshold if threshold is not None else 0.0),
        threshold_source=str(threshold_source or "unknown"),
        num_transmissions=num_transmissions,
        channel_profile=channel_cfg.profile,
        cfo_hz=channel_cfg.cfo_hz,
        configuration={
            "format": cfg.fmt,
            "periodicity_ms": cfg.periodicity_ms,
            "subcarrier_offset": cfg.subcarrier_offset,
            "num_subcarriers": cfg.num_subcarriers,
            "nrep": cfg.nrep,
            "start_time_ms": cfg.start_time_ms,
            "ninit": cfg.ninit,
            "num_rx_antennas": channel_cfg.num_rx_antennas,
            "detector": "minimum_combinations",
            "threshold_mode": str(threshold_source or "unknown"),
            **(threshold_metadata or {}),
        },
    )
