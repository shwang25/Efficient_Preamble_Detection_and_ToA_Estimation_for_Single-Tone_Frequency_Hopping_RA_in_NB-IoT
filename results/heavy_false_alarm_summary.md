# Heavy False Alarm Validation

## Setup

The heavy validation reused the current reduced-scope minimum-combinations detector without changing detector logic. The final retained result uses the empirically calibrated threshold and the same no-signal AWGN setup:

- Format: `0`
- Repetitions: `8`
- Receive antennas: `2`
- CFO: `200 Hz`
- SNR grid: `[-5.3, -2.3, 0.7, 3.7, 6.7, 9.7] dB`
- Trials per SNR: `2000`
- Total no-signal trials: `12000`
- Random seed: `3`

## Empirically Calibrated Threshold

- Threshold source: `custom`
- Threshold value: `0.015127526816207215`
- Calibration file used: `results/calibrated_threshold.json`
- Calibration target: `0.001`
- Calibration trials: `6000`

Observed false alarms:

| SNR (dB) | False alarms | Trials | Probability |
|---:|---:|---:|---:|
| -5.3 | 2 | 2000 | 0.0010 |
| -2.3 | 2 | 2000 | 0.0010 |
| 0.7 | 0 | 2000 | 0.0000 |
| 3.7 | 0 | 2000 | 0.0000 |
| 6.7 | 1 | 2000 | 0.0005 |
| 9.7 | 2 | 2000 | 0.0010 |

Pooled false alarm probability:

- `7 / 12000 = 0.000583`

Artifacts:

- `results/false_alarm_result_calibrated.json`
- `results/false_alarm_probability_vs_snr_calibrated.png`

## Interpretation

The empirically calibrated threshold behaves near the intended `0.1%` target, but the pooled validation result is slightly below target at `0.0583%`. This is reasonable for the current sample size and the fact that the threshold was estimated from only `6000` calibration trials. A larger calibration sample would make the threshold estimate more stable, but this run is already meaningfully stronger than the earlier `1000`-trials-per-SNR check.
