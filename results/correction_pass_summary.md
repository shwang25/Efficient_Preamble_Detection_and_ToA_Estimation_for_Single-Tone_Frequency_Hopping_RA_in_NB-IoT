# Correction Pass Summary

## What changed

- Removed an extra half-subcarrier bias in `src/nprach_repro/nprach_waveform.py`, so the waveform and detector now use a consistent single half-subcarrier shift.
- Limited the detector search window with the simulated ToA upper bound in `src/nprach_repro/config.py`, `src/nprach_repro/detector_mincomb.py`, and `scripts/run_nprach_paper_sweep.py`. This keeps Format 1 aligned with the reduced-scope paper-style ToA interval instead of searching the full CP span.
- Rechecked false-alarm calibration at `<= 0.1%` and saved a lightweight diagnostic in `results/correction_threshold_diagnostic.json`.

## Did AWGN move closer to the paper?

Yes, materially closer than the previous reduced-scope baseline, but still not fully at the paper scale.

- New AWGN 99% points from `results/paper_sweep_detection_correction_pass.json`:
  - F0, NRep=8: about `-3.63 dB`
  - F1, NRep=8: about `-1.63 dB`
  - F0, NRep=32: about `-8.40 dB`
  - F1, NRep=32: about `-8.90 dB`
- This is better than the earlier reduced-scope curves that were roughly:
  - NRep=8: F0 `~0 dB`, F1 `~3 dB`
  - NRep=32: F0 `~-5.25 dB`, F1 `~-4.0 dB`

## Did Format 0 and Format 1 become more similar?

Mostly yes.

- `NRep=32` is now close: F0 and F1 differ by about `0.5 dB`, which is much better than before.
- `NRep=8` still shows a noticeable gap of about `2 dB`, so Format 1 is improved but not fully paper-like yet.

## Did threshold calibration matter?

Not materially in this correction pass.

- The calibrated thresholds stayed close to the MATLAB defaults.
- In the saved lightweight diagnostic, the estimated AWGN 99% crossing did not move for any of the four Format/NRep cases at the diagnostic resolution.
- Conclusion: threshold choice is not the main remaining source of mismatch here.

## What remains reduced-scope

- The detector is still the same minimum-combinations core.
- The correctness rule is unchanged: detected `NInit` must match and ToA error must be `<= 3.646 us`.
- The waveform/channel model is still simplified and does not implement full EPA1/ETU1 fading.
- This is still a reduced-scope reproduction, not a full paper reimplementation.

## CFO = 200 Hz case

- `results/paper_sweep_detection_probability_cfo200_correction_pass.png` is still only an AWGN + CFO stress case.
- It must not be interpreted as EPA1 or ETU1 unless actual fading is modeled.
