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
from nprach_repro.nprach_simulation import run_false_alarm_experiment, save_json_result, save_probability_plot
from nprach_repro.threshold_calibration import load_calibrated_threshold


def _resolve_threshold_args(args: argparse.Namespace) -> tuple[float | None, dict[str, object]]:
    if args.threshold is not None and args.threshold_json is not None:
        raise SystemExit("Use either --threshold or --threshold-json, not both.")
    if args.threshold_json is not None:
        threshold_path = args.threshold_json.resolve()
        threshold_value, payload = load_calibrated_threshold(threshold_path)
        return threshold_value, {
            "threshold_input_mode": "calibrated_file",
            "threshold_file": str(threshold_path),
            "threshold_target_false_alarm_probability": payload.get("target_false_alarm_probability"),
            "threshold_calibration_trials": payload.get("total_calibration_trials"),
        }
    if args.threshold is not None:
        return float(args.threshold), {
            "threshold_input_mode": "numeric",
            "threshold_numeric_value": float(args.threshold),
        }
    return None, {"threshold_input_mode": "matlab_default"}


def _tagged_output_path(base_name: str, suffix: str) -> Path:
    return RESULTS / f"{base_name}{suffix}"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run a moderate NPRACH false-alarm experiment.")
    parser.add_argument("--trials-per-snr", type=int, default=1000, help="Number of noise-only trials per SNR point.")
    parser.add_argument("--seed", type=int, default=3, help="Random seed.")
    parser.add_argument("--threshold", type=float, default=None, help="Numeric detector threshold override.")
    parser.add_argument("--threshold-json", type=Path, default=None, help="Path to calibrated_threshold.json.")
    parser.add_argument("--output-tag", type=str, default="", help="Optional suffix tag for result filenames, e.g. default or calibrated.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    ue_cfg = UEConfig()
    nprach_cfg = NPRACHConfig(fmt="0", periodicity_ms=80, subcarrier_offset=0, num_subcarriers=48, nrep=8, start_time_ms=8, ninit=7)
    channel_cfg = ChannelConfig(profile="awgn", cfo_hz=200.0, num_rx_antennas=2, signal_present=False)
    threshold_value, threshold_metadata = _resolve_threshold_args(args)
    detector_cfg = DetectorConfig(threshold=threshold_value)
    snr_db_list = [-5.3, -2.3, 0.7, 3.7, 6.7, 9.7]
    output_suffix = f"_{args.output_tag}" if args.output_tag else ""

    result = run_false_alarm_experiment(
        ue_cfg=ue_cfg,
        cfg=nprach_cfg,
        channel_cfg=channel_cfg,
        detector_cfg=detector_cfg,
        snr_db_list=snr_db_list,
        num_trials=args.trials_per_snr,
        seed=args.seed,
        threshold_metadata=threshold_metadata,
    )
    json_path = save_json_result(_tagged_output_path(f"false_alarm_result{output_suffix}", ".json"), result)
    plot_path = save_probability_plot(
        x_values=snr_db_list,
        y_values=[point.false_alarm_probability for point in result.points],
        output_path=_tagged_output_path(f"false_alarm_probability_vs_snr{output_suffix}", ".png"),
        title=f"NPRACH False Alarm Probability ({args.trials_per_snr} trials/SNR, {threshold_metadata['threshold_input_mode']})",
        y_label="False Alarm Probability",
    )
    print(f"json={json_path}")
    print(f"plot={plot_path}")
    for point in result.points:
        print(
            f"snr={point.snr_db:+4.1f} dB, "
            f"false_alarms={point.false_alarm_count}/{point.num_trials}, "
            f"p_false_alarm={point.false_alarm_probability:.3f}"
        )
    print(f"total_false_alarms={result.total_false_alarm_count}/{result.total_trials}")
    print(f"threshold={result.threshold:.6f} ({result.threshold_source})")


if __name__ == "__main__":
    main()
