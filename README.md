# Efficient Preamble Detection and Time-of-Arrival Estimation for Single-Tone Frequency Hopping Random Access in NB-IoT

This repository provides a compact Python reproduction of the paper:

> **Efficient Preamble Detection and Time-of-Arrival Estimation for Single-Tone Frequency Hopping Random Access in NB-IoT**

## Overview

This project reproduces the main simulation trends of the paper for **NPRACH preamble detection** and **time-of-arrival (ToA) estimation** in NB-IoT.

The current repository focuses on a **reduced-scope, code-oriented reproduction** built around the paper's **minimum-combinations detector**.

The present implementation includes:

- Monte Carlo detection-probability simulation for **NPRACH Format 0 and Format 1**
- Comparison for **NRep = 8** and **NRep = 32**
- **Uniform random ToA** within the paper-style reduced-scope timing windows
- **AWGN, CFO = 0 Hz** as the primary reference case
- **AWGN + CFO = 200 Hz** as a secondary stress case
- Fixed-step SNR sweeps with JSON and figure outputs

This repository is intended for academic study, debugging, and further development rather than full conformance-grade reproduction.

## Scope and Limitations

This is **not** a full system-level reproduction of the paper.

In particular:

- The detector core is limited to the **minimum-combinations** method
- The repository keeps a **reduced-scope simulation structure**
- Correct detection requires:
  - the detected `NInit` to match the transmitted `NInit`, and
  - the ToA error to be within `3.646 us`
- The `CFO = 200 Hz` case is **only an AWGN + CFO stress test**
- Full **EPA1 / ETU1 multipath fading** is **not** modeled in the current Python implementation

Minor differences from the published curves are therefore expected.

## Repository Structure

```text
├── scripts
│   └── run_nprach_paper_sweep.py
├── src
│   └── nprach_repro
│       ├── __init__.py
│       ├── config.py
│       ├── detector_mincomb.py
│       ├── hopping.py
│       ├── nprach_info.py
│       ├── nprach_simulation.py
│       ├── nprach_waveform.py
│       ├── threshold_calibration.py
│       └── utils.py
├── results
│   ├── correction_pass_summary.md
│   ├── correction_threshold_diagnostic.json
│   ├── paper_sweep_detection_correction_pass.json
│   ├── paper_sweep_detection_probability_awgn_cfo0_correction_pass.png
│   └── paper_sweep_detection_probability_cfo200_correction_pass.png
├── Efficient_Preamble_Detection_and_Time-of-Arrival_Estimation_for_Single-Tone_Frequency_Hopping_Random_Access_in_NB-IoT.pdf
├── NPRACHDetectionExample.m
├── hNPRACHDetect.m
├── lteNPRACHInfo.m
├── pyproject.toml
└── README.md
```

### File Description

- `scripts/run_nprach_paper_sweep.py`  
  Main entry point for fixed-step SNR sweeps across Format 0/1, NRep 8/32, random ToA, and CFO scenarios.

- `src/nprach_repro/config.py`  
  Core configuration dataclasses and default detector-threshold definitions.

- `src/nprach_repro/nprach_info.py`  
  NPRACH format/resource parameter handling and derived timing/frequency quantities.

- `src/nprach_repro/hopping.py`  
  Frequency-hopping pattern generation for NPRACH preambles.

- `src/nprach_repro/nprach_waveform.py`  
  NPRACH waveform generation, timing-offset injection, AWGN addition, and CFO application.

- `src/nprach_repro/detector_mincomb.py`  
  Minimum-combinations detector and ToA estimation logic.

- `src/nprach_repro/nprach_simulation.py`  
  Monte Carlo sweep execution and correct-detection accounting.

- `src/nprach_repro/threshold_calibration.py`  
  False-alarm-based empirical threshold calibration utilities.

- `results/*.json`, `results/*.png`, `results/*.md`  
  Example outputs from the current correction pass.

- `*.m`  
  MATLAB reference files retained for algorithm cross-checking.

- `*.pdf`  
  Reference papers kept in the repository for academic context.

## Requirements

This project requires:

- Python `>= 3.10`
- `numpy`
- `matplotlib`

You can install the package locally with:

```bash
pip install -e .
```

or install the minimal dependencies directly:

```bash
pip install numpy matplotlib
```

## How to Run

Run the main sweep script directly:

```bash
python scripts/run_nprach_paper_sweep.py --trials-per-snr 80 --snr-start-db -15 --snr-stop-db 5 --snr-step-db 0.5 --output-tag correction_pass
```

This script will:

- run the Monte Carlo detection sweep,
- save the detection results as JSON,
- generate one figure for **AWGN, CFO = 0 Hz**,
- generate one figure for **AWGN + CFO = 200 Hz**.

The main output files are:

- `results/paper_sweep_detection_correction_pass.json`
- `results/paper_sweep_detection_probability_awgn_cfo0_correction_pass.png`
- `results/paper_sweep_detection_probability_cfo200_correction_pass.png`

If threshold calibration is desired, the same script can be run with:

```bash
python scripts/run_nprach_paper_sweep.py --threshold-mode calibrated --calibration-trials-per-snr 300 --false-alarm-target 0.001 --output-tag calibrated_run
```

## Current Status

The repository currently contains a focused correction pass that:

- removed an extra half-subcarrier bias in waveform generation,
- constrained the detector search window using the simulated ToA upper bound,
- checked whether false-alarm-based threshold calibration materially changes the 99% crossing points.

The detailed discussion of the current reduced-scope results is provided in:

- `results/correction_pass_summary.md`
- `results/correction_threshold_diagnostic.json`

## Notes

- This repository prioritizes **clarity and reproducibility** over full feature coverage.
- The Python code is intentionally kept compact for debugging and academic inspection.
- Numerical gaps relative to the original paper may still remain because the current implementation does not include the full channel and system model.
- The `CFO = 200 Hz` result should not be interpreted as EPA1 or ETU1 unless an actual fading model is added.

## Disclaimer

This repository is an independent academic reproduction of the referenced work.

- All theoretical methods and original ideas belong to the authors of the original paper.
- This code is provided for research, learning, and non-commercial academic use.

## Citation

If you use this repository, please cite the original paper.

## License

No license file is currently included in this repository. Add one explicitly if you plan to distribute the code publicly.
