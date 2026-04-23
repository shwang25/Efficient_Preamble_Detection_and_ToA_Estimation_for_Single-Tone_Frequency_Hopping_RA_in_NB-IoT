from __future__ import annotations

import argparse
import os
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
RESULTS = ROOT / "results"
os.environ.setdefault("MPLCONFIGDIR", str((RESULTS / ".matplotlib").resolve()))
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from nprach_repro import ChannelConfig, DetectorConfig, NPRACHConfig, UEConfig
from nprach_repro.threshold_calibration import (
    calibrate_empirical_threshold,
    save_threshold_calibration,
    save_threshold_cdf_plot,
)


def _parse_snr_list(value: str) -> list[float]:
    return [float(item.strip()) for item in value.split(",") if item.strip()]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Calibrate an empirical NPRACH detector threshold from noise-only trials.")
    parser.add_argument(
        "--trials-per-snr",
        type=int,
        default=1000,
        help="Number of noise-only calibration trials per SNR point.",
    )
    parser.add_argument(
        "--false-alarm-target",
        type=float,
        default=0.001,
        help="Target false alarm probability used to select the threshold.",
    )
    parser.add_argument("--seed", type=int, default=11, help="Random seed.")
    parser.add_argument(
        "--snr-db-list",
        type=str,
        default="-5.3,-2.3,0.7,3.7,6.7,9.7",
        help="Comma-separated SNR list used for pooled noise-only calibration.",
    )
    parser.add_argument(
        "--output-json",
        type=Path,
        default=RESULTS / "calibrated_threshold.json",
        help="Output JSON path.",
    )
    parser.add_argument(
        "--output-plot",
        type=Path,
        default=RESULTS / "threshold_cdf.png",
        help="Output CDF plot path.",
    )
    parser.add_argument(
        "--output-peaks",
        type=Path,
        default=None,
        help="Optional output raw peak-metric NPY path.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    snr_db_list = _parse_snr_list(args.snr_db_list)

    ue_cfg = UEConfig()
    nprach_cfg = NPRACHConfig(fmt="0", periodicity_ms=80, subcarrier_offset=0, num_subcarriers=48, nrep=8, start_time_ms=8, ninit=7)
    channel_cfg = ChannelConfig(profile="awgn", cfo_hz=200.0, num_rx_antennas=2, signal_present=False)
    detector_cfg = DetectorConfig()

    result = calibrate_empirical_threshold(
        ue_cfg=ue_cfg,
        cfg=nprach_cfg,
        channel_cfg=channel_cfg,
        detector_cfg=detector_cfg,
        snr_db_list=snr_db_list,
        num_trials_per_snr=args.trials_per_snr,
        target_false_alarm_probability=args.false_alarm_target,
        seed=args.seed,
    )
    plot_path = save_threshold_cdf_plot(result, args.output_plot)
    json_path = save_threshold_calibration(
        result=result,
        json_path=args.output_json,
        raw_peak_metrics_path=args.output_peaks,
        cdf_plot_path=plot_path,
    )

    print(f"json={json_path}")
    print(f"plot={plot_path}")
    if args.output_peaks is not None:
        print(f"peaks={args.output_peaks}")
    print(f"calibrated_threshold={result.calibrated_threshold:.6f}")
    print(f"empirical_false_alarm_probability={result.empirical_false_alarm_probability:.6f}")
    print(f"matlab_default_threshold={result.matlab_default_threshold:.6f}")
    print(f"total_calibration_trials={result.total_calibration_trials}")


if __name__ == "__main__":
    main()
