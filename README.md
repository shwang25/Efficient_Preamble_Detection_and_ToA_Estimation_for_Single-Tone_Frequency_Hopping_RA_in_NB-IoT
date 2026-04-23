# Efficient Preamble Detection and ToA Estimation for Single-Tone Frequency Hopping RA in NB-IoT

This repository provides a compact Python reproduction of the paper:

> **Efficient Preamble Detection and Time-of-Arrival Estimation for Single-Tone Frequency Hopping Random Access in NB-IoT**

## Overview

This project reproduces the main simulation trends of the paper for **NPRACH preamble detection** and **time-of-arrival (ToA) estimation** in NB-IoT.

The current repository focuses on a **reduced-scope, code-oriented reproduction** built around the paper's **minimum-combinations detector**.

The present implementation includes:

- Monte Carlo simulation of **correct detection probability versus SNR**
- NPRACH **Format 0** and **Format 1**
- **NRep = 8** and **NRep = 32**
- **Uniform random ToA** within paper-style reduced-scope timing ranges
- **AWGN, CFO = 0 Hz** as the primary reference case
- **AWGN + CFO = 200 Hz** as a secondary stress case
- Fixed-step SNR sweeps with JSON and figure outputs

This repository is intended for academic study, debugging, and further development rather than full conformance-grade reproduction.

## Scope

This is **not** a full system-level reproduction of the paper.

The current code intentionally keeps a narrow scope:

- the detector core is limited to the **minimum-combinations** method,
- the simulation uses a **reduced-scope waveform and channel model**,
- correct detection requires:
  - correct `NInit`, and
  - ToA estimation error `<= 3.646 us`,
- the `CFO = 200 Hz` case is **only an AWGN + CFO stress test**,
- full **EPA1 / ETU1 multipath fading** is **not** modeled in the present implementation.

Minor differences from the published curves are therefore expected.

## Repository Structure

```text
.
|-- results
|   |-- correction_pass_summary.md
|   |-- correction_threshold_diagnostic.json
|   |-- paper_sweep_detection_correction_pass.json
|   |-- paper_sweep_detection_probability_awgn_cfo0_correction_pass.png
|   `-- paper_sweep_detection_probability_cfo200_correction_pass.png
|-- scripts
|   `-- run_nprach_paper_sweep.py
|-- src
|   `-- nprach_repro
|       |-- __init__.py
|       |-- config.py
|       |-- detector_mincomb.py
|       |-- hopping.py
|       |-- nprach_info.py
|       |-- nprach_simulation.py
|       |-- nprach_waveform.py
|       |-- threshold_calibration.py
|       `-- utils.py
|-- pyproject.toml
`-- README.md
```

### File Description

- `scripts/run_nprach_paper_sweep.py`  
  Main entry point for fixed-step SNR sweeps across Format 0/1, NRep 8/32, random ToA, and CFO scenarios.

- `src/nprach_repro/config.py`  
  Core configuration dataclasses, ToA limits, and detector-threshold definitions.

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
  Saved outputs from the current correction pass.

## Requirements

This project requires:

- Python `>= 3.10`
- `numpy`
- `matplotlib`

Install the package locally with:

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

The script will:

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

## Current Results

The repository currently includes a focused correction pass with:

- a corrected waveform-side half-subcarrier treatment,
- a detector search window constrained by the simulated ToA upper bound,
- a lightweight threshold-calibration diagnostic.

The supporting result files are:

- `results/correction_pass_summary.md`
- `results/correction_threshold_diagnostic.json`

## Notes

- This repository prioritizes **clarity and reproducibility** over full feature coverage.
- The code is intentionally compact for debugging and academic inspection.
- Numerical gaps relative to the original paper may still remain because the full channel and system model are not implemented.
- The `CFO = 200 Hz` result must not be interpreted as EPA1 or ETU1 unless an actual fading model is added.

## Disclaimer

This repository is an independent academic reproduction of the referenced work.

- All theoretical methods and original ideas belong to the authors of the original paper.
- This code is provided for research, learning, and non-commercial academic use.

## Citation

If you use this repository, please cite the original paper.

## License

No license file is currently included in this repository. Add one explicitly if you plan to distribute the code publicly.
