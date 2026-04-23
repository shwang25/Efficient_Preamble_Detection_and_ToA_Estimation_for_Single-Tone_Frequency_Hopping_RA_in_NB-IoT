from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass
import os
from pathlib import Path
import sys

import numpy as np


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
RESULTS = ROOT / "results"
os.environ.setdefault("MPLCONFIGDIR", str((RESULTS / ".matplotlib").resolve()))
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from nprach_repro import ChannelConfig, DetectorConfig, NPRACHConfig, UEConfig, default_threshold
from nprach_repro.config import toa_limit_us
from nprach_repro.nprach_simulation import run_detection_example
from nprach_repro.threshold_calibration import calibrate_empirical_threshold
from nprach_repro.utils import dump_json


@dataclass(frozen=True)
class CfoScenario:
    key: str
    label: str
    cfo_hz: float


@dataclass(frozen=True)
class SweepJob:
    scenario: CfoScenario
    cfg: NPRACHConfig
    snr_db_list: list[float]
    threshold_override: float | None
    threshold_mode: str
    num_transmissions: int
    seed: int


SCENARIOS = (
    CfoScenario(key="awgn_cfo0", label="AWGN, CFO = 0 Hz", cfo_hz=0.0),
    CfoScenario(key="cfo200", label="CFO = 200 Hz", cfo_hz=200.0),
)


def _snr_grid(start_db: float, stop_db: float, step_db: float) -> list[float]:
    if step_db <= 0:
        raise ValueError("--snr-step-db must be positive")
    count = int(np.floor((stop_db - start_db) / step_db)) + 1
    if count <= 0:
        raise ValueError("--snr-stop-db must be greater than or equal to --snr-start-db")
    values = [start_db + (idx * step_db) for idx in range(count)]
    if values[-1] < stop_db - 1e-9:
        values.append(stop_db)
    return [float(round(value, 6)) for value in values]


def _periodicity_for_nrep(nrep: int) -> int:
    return 80 if nrep <= 8 else 320


def _make_nprach_config(fmt: str, nrep: int) -> NPRACHConfig:
    return NPRACHConfig(
        fmt=fmt,
        periodicity_ms=_periodicity_for_nrep(nrep),
        subcarrier_offset=0,
        num_subcarriers=48,
        nrep=nrep,
        start_time_ms=8,
        ninit=7,
    )


def _toa_range_us(fmt: str) -> tuple[float, float]:
    return (0.0, toa_limit_us(fmt))


def _tagged_output_path(base_name: str, suffix: str, output_tag: str) -> Path:
    tag = f"_{output_tag}" if output_tag else ""
    return RESULTS / f"{base_name}{tag}{suffix}"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run a paper-style NPRACH detection sweep for Format 0/1, NRep 8/32, and random ToA."
    )
    parser.add_argument(
        "--trials-per-snr",
        type=int,
        default=100,
        help="Number of signal-present transmissions per SNR point and configuration.",
    )
    parser.add_argument("--seed", type=int, default=21, help="Random seed.")
    parser.add_argument("--snr-start-db", type=float, default=-12.0, help="First SNR point in dB.")
    parser.add_argument("--snr-stop-db", type=float, default=8.0, help="Last SNR point in dB.")
    parser.add_argument("--snr-step-db", type=float, default=1.0, help="Fixed SNR spacing in dB.")
    parser.add_argument(
        "--threshold-mode",
        choices=("default", "calibrated"),
        default="default",
        help="Use the MATLAB-style empirical formula or calibrate a threshold per Format/NRep.",
    )
    parser.add_argument(
        "--calibration-trials-per-snr",
        type=int,
        default=300,
        help="Noise-only calibration trials per SNR when --threshold-mode calibrated.",
    )
    parser.add_argument(
        "--false-alarm-target",
        type=float,
        default=0.001,
        help="Target false alarm probability for calibrated thresholds.",
    )
    parser.add_argument(
        "--output-tag",
        type=str,
        default="paper_sweep",
        help="Optional suffix tag for result filenames.",
    )
    return parser.parse_args()


def _resolve_thresholds(
    ue_cfg: UEConfig,
    configs: list[NPRACHConfig],
    snr_db_list: list[float],
    args: argparse.Namespace,
) -> dict[tuple[str, int], dict[str, object]]:
    def calibration_summary(calibration) -> dict[str, object]:
        summary = asdict(calibration)
        summary.pop("peak_metrics", None)
        return summary

    thresholds: dict[tuple[str, int], dict[str, object]] = {}
    for cfg in configs:
        key = (cfg.fmt, cfg.nrep)
        if key in thresholds:
            continue
        if args.threshold_mode == "default":
            thresholds[key] = {
                "threshold": default_threshold(cfg),
                "threshold_source": "matlab_default",
                "calibration": None,
            }
            continue

        calibration = calibrate_empirical_threshold(
            ue_cfg=ue_cfg,
            cfg=cfg,
            channel_cfg=ChannelConfig(profile="awgn", cfo_hz=0.0, num_rx_antennas=2, signal_present=False),
            detector_cfg=DetectorConfig(max_timing_offset_us=_toa_range_us(cfg.fmt)[1]),
            snr_db_list=snr_db_list,
            num_trials_per_snr=args.calibration_trials_per_snr,
            target_false_alarm_probability=args.false_alarm_target,
            seed=args.seed + (1000 * int(cfg.fmt)) + cfg.nrep,
        )
        thresholds[key] = {
            "threshold": calibration.calibrated_threshold,
            "threshold_source": "calibrated_noise_only",
            "calibration": calibration_summary(calibration),
        }
    return thresholds


def _run_one_job(job: SweepJob) -> dict[str, object]:
    ue_cfg = UEConfig()
    detector_cfg = DetectorConfig(
        threshold=job.threshold_override,
        max_timing_offset_us=_toa_range_us(job.cfg.fmt)[1],
    )
    channel_cfg = ChannelConfig(
        profile="awgn",
        cfo_hz=job.scenario.cfo_hz,
        num_rx_antennas=2,
        signal_present=True,
        timing_offset_range_us=_toa_range_us(job.cfg.fmt),
    )
    result = run_detection_example(
        ue_cfg=ue_cfg,
        cfg=job.cfg,
        channel_cfg=channel_cfg,
        detector_cfg=detector_cfg,
        snr_db_list=job.snr_db_list,
        num_transmissions=job.num_transmissions,
        seed=job.seed,
        threshold_metadata={
            "threshold_input_mode": job.threshold_mode,
            "timing_offset_mode": "uniform_random",
            "timing_offset_range_us": list(_toa_range_us(job.cfg.fmt)),
        },
    )
    return {
        "scenario": asdict(job.scenario),
        "format": job.cfg.fmt,
        "nrep": job.cfg.nrep,
        "periodicity_ms": job.cfg.periodicity_ms,
        "toa_range_us": list(_toa_range_us(job.cfg.fmt)),
        "threshold": result.threshold,
        "threshold_source": result.threshold_source,
        "points": [asdict(point) for point in result.points],
    }


def _run_jobs(jobs: list[SweepJob], workers: int) -> list[dict[str, object]]:
    return [_run_one_job(job) for job in jobs]


def _run_sweep(args: argparse.Namespace) -> dict[str, object]:
    snr_db_list = _snr_grid(args.snr_start_db, args.snr_stop_db, args.snr_step_db)
    ue_cfg = UEConfig()
    configs = [_make_nprach_config(fmt, nrep) for nrep in (8, 32) for fmt in ("0", "1")]
    thresholds = _resolve_thresholds(ue_cfg, configs, snr_db_list, args)

    jobs: list[SweepJob] = []
    for scenario in SCENARIOS:
        for cfg in configs:
            threshold_entry = thresholds[(cfg.fmt, cfg.nrep)]
            threshold_override = None if args.threshold_mode == "default" else float(threshold_entry["threshold"])
            jobs.append(
                SweepJob(
                    scenario=scenario,
                    cfg=cfg,
                    snr_db_list=snr_db_list,
                    threshold_override=threshold_override,
                    threshold_mode=args.threshold_mode,
                    num_transmissions=args.trials_per_snr,
                    seed=args.seed + (100 * int(cfg.fmt)) + cfg.nrep + int(scenario.cfo_hz),
                )
            )

    results = _run_jobs(jobs, workers=1)
    scenario_order = {scenario.key: idx for idx, scenario in enumerate(SCENARIOS)}
    results.sort(key=lambda item: (scenario_order[item["scenario"]["key"]], item["nrep"], item["format"]))

    return {
        "description": "Paper-style NPRACH sweep with Format 0/1, NRep 8/32, fixed-step SNR, and uniform random ToA.",
        "snr_db_list": snr_db_list,
        "snr_start_db": args.snr_start_db,
        "snr_stop_db": args.snr_stop_db,
        "snr_step_db": args.snr_step_db,
        "trials_per_snr": args.trials_per_snr,
        "seed": args.seed,
        "threshold_mode": args.threshold_mode,
        "cfo_scenarios": [asdict(scenario) for scenario in SCENARIOS],
        "notes": {
            "channel_model": "CFO-only AWGN waveform. EPA1/ETU1 multipath fading is not modeled in this sweep.",
            "awgn_cfo": "0 Hz",
            "epa1_etu1_cfo_proxy": "200 Hz",
            "correct_detection": "Detected NInit must match the transmitted NInit and ToA error must be within 3.646 us.",
            "snr_grid": "A single fixed-step SNR grid is used for every Format/NRep/CFO curve.",
            "search_window": "The detector search window is limited by the simulated ToA upper bound for each format, instead of always using the full CP span.",
        },
        "thresholds": {f"format{fmt}_nrep{nrep}": value for (fmt, nrep), value in thresholds.items()},
        "results": results,
    }


def _snr_at_target(points: list[dict[str, object]], target: float = 0.99) -> float | None:
    ordered = sorted(points, key=lambda point: point["snr_db"])
    for prev, cur in zip(ordered, ordered[1:]):
        p0 = prev["detection_probability"]
        p1 = cur["detection_probability"]
        if p0 >= target:
            return float(prev["snr_db"])
        if p0 < target <= p1 and p1 > p0:
            ratio = (target - p0) / (p1 - p0)
            return float(prev["snr_db"] + ratio * (cur["snr_db"] - prev["snr_db"]))
    if ordered and ordered[-1]["detection_probability"] >= target:
        return float(ordered[-1]["snr_db"])
    return None


def _add_curve(
    ax,
    item: dict[str, object],
    marker_style: str,
    color: str,
) -> None:
    snr_values = [point["snr_db"] for point in item["points"]]
    probabilities = [point["detection_probability"] for point in item["points"]]
    target_snr = _snr_at_target(item["points"])
    label = f"F{item['format']}"
    label += f" ({target_snr:.2f} dB @99%)" if target_snr is not None else " (> grid @99%)"
    ax.plot(
        snr_values,
        probabilities,
        marker_style,
        color=color,
        linewidth=1.8,
        markersize=4.4,
        label=label,
    )


def _save_scenario_plot(payload: dict[str, object], scenario: CfoScenario, output_path: Path) -> Path:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    RESULTS.mkdir(parents=True, exist_ok=True)
    fig, axes = plt.subplots(1, 2, figsize=(10.8, 4.2), sharey=True)
    styles = {
        "0": ("o-", "tab:blue"),
        "1": ("^-", "tab:orange"),
    }

    for col_idx, nrep in enumerate((8, 32)):
        ax = axes[col_idx]
        for item in payload["results"]:
            if item["scenario"]["key"] != scenario.key or item["nrep"] != nrep:
                continue
            marker_style, color = styles[item["format"]]
            _add_curve(ax, item, marker_style, color)
        ax.axhline(0.99, color="0.35", linestyle="--", linewidth=1.0, label="99% target")
        ax.set_title(f"NRep = {nrep}")
        ax.set_xlabel("SNR (dB)")
        ax.set_ylim(0.0, 1.05)
        ax.grid(True, linestyle=":", linewidth=0.6)
        ax.legend(loc="lower right", fontsize=8)
        if col_idx == 0:
            ax.set_ylabel("Correct Detection Probability")

    fig.suptitle(
        f"NPRACH Detection With Random ToA, {scenario.label} "
        f"({payload['trials_per_snr']} trials/SNR, {payload['snr_step_db']:.1f} dB step)"
    )
    fig.tight_layout()
    fig.savefig(output_path, dpi=180)
    plt.close(fig)
    return output_path


def main() -> None:
    args = parse_args()
    payload = _run_sweep(args)
    json_path = _tagged_output_path("paper_sweep_detection", ".json", args.output_tag)
    plot_paths = [
        _tagged_output_path(f"paper_sweep_detection_probability_{scenario.key}", ".png", args.output_tag)
        for scenario in SCENARIOS
    ]
    dump_json(json_path, payload)
    for scenario, plot_path in zip(SCENARIOS, plot_paths):
        _save_scenario_plot(payload, scenario, plot_path)

    print(f"json={json_path}")
    for plot_path in plot_paths:
        print(f"plot={plot_path}")
    for item in payload["results"]:
        probs = ", ".join(f"{point['detection_probability']:.3f}" for point in item["points"])
        snr99 = _snr_at_target(item["points"])
        snr99_text = "not reached" if snr99 is None else f"{snr99:.2f} dB"
        print(
            f"{item['scenario']['key']} format={item['format']} nrep={item['nrep']} "
            f"toa={item['toa_range_us']} us threshold={item['threshold']:.6f} "
            f"snr99={snr99_text}: [{probs}]"
        )


if __name__ == "__main__":
    main()
