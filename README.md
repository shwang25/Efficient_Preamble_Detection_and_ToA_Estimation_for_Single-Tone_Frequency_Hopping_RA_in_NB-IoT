# Efficient Preamble Detection and ToA Estimation for Single-Tone Frequency Hopping RA in NB-IoT

This repository provides a compact Python reproduction of the paper:

> **Efficient Preamble Detection and Time-of-Arrival Estimation for Single-Tone Frequency Hopping Random Access in NB-IoT**

## Overview

This project reproduces the main simulation trends for **NPRACH preamble detection** and **time-of-arrival (ToA) estimation** in NB-IoT.

The current repository focuses on:

- the **minimum-combinations** detector,
- **Format 0** and **Format 1**,
- **NRep = 8** and **NRep = 32**,
- **uniform random ToA**,
- **AWGN, CFO = 0 Hz** as the main reference case,
- **AWGN + CFO = 200 Hz** as a secondary stress case.

This is a **reduced-scope academic reproduction**, not a full system-level implementation of the paper.

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
|-- pyproject.toml
`-- README.md
```

### File Description

- `scripts/run_nprach_paper_sweep.py`  
  Main script for fixed-step SNR sweeps and figure generation.

- `src/nprach_repro/`  
  Core implementation of waveform generation, hopping, detector, simulation, and threshold calibration.

- `results/`  
  Saved JSON results, figures, and brief correction-pass notes.

## Requirements

Install the minimal dependencies with:

```bash
pip install numpy matplotlib
```

or install the package locally with:

```bash
pip install -e .
```

## How to Run

Run the main sweep script:

```bash
python scripts/run_nprach_paper_sweep.py --trials-per-snr 80 --snr-start-db -15 --snr-stop-db 5 --snr-step-db 0.5 --output-tag correction_pass
```

This generates:

- `results/paper_sweep_detection_correction_pass.json`
- `results/paper_sweep_detection_probability_awgn_cfo0_correction_pass.png`
- `results/paper_sweep_detection_probability_cfo200_correction_pass.png`

## Notes

- Correct detection requires correct `NInit` and ToA error `<= 3.646 us`.
- The `CFO = 200 Hz` result is **only an AWGN + CFO stress case**.
- **EPA1 / ETU1 multipath fading** is not modeled in the current version.
- Minor numerical differences from the original paper are therefore expected.

## Disclaimer

This repository is an independent academic reproduction of the referenced work.  
All theoretical methods and original ideas belong to the authors of the original paper.

## License

This project is released under the MIT License.
