from __future__ import annotations

from dataclasses import replace
from functools import lru_cache

import numpy as np

from .config import NPRACHConfig, UEConfig


@lru_cache(maxsize=None)
def lte_prbs_bits(c_init: int, length: int) -> np.ndarray:
    """LTE gold sequence with Nc = 1600, matching ltePRBS(cinit, len)."""
    nc = 1600
    seq_len = nc + length + 31
    x1 = np.zeros(seq_len, dtype=np.int8)
    x2 = np.zeros(seq_len, dtype=np.int8)
    x1[0] = 1
    for idx in range(31):
        x2[idx] = (c_init >> idx) & 1
    for n in range(nc + length):
        x1[n + 31] = (x1[n + 3] + x1[n]) & 1
        x2[n + 31] = (x2[n + 3] + x2[n + 2] + x2[n + 1] + x2[n]) & 1
    return (x1[nc : nc + length] + x2[nc : nc + length]) & 1


@lru_cache(maxsize=None)
def function_f(cell_id: int, nra_sc: int, max_t: int) -> np.ndarray:
    t_values = np.arange(max_t + 1, dtype=int)
    prbs_indices = (10 * t_values[None, :]) + np.arange(1, 10, dtype=int)[:, None]
    prbs = lte_prbs_bits(cell_id, int(prbs_indices.max()) + 1)

    current = np.zeros(max_t + 2, dtype=int)
    for t_idx in range(max_t + 1):
        indices = prbs_indices[:, t_idx]
        weights = 2 ** (indices - indices[0])
        s_val = int(np.sum(prbs[indices] * weights) % (nra_sc - 1))
        current[t_idx + 1] = (current[t_idx] + s_val + 1) % nra_sc
    return current[1:]


def generate_frequency_locations(ue_cfg: UEConfig, cfg: NPRACHConfig) -> np.ndarray:
    if cfg.fmt not in {"0", "1"}:
        raise ValueError(f"Unsupported NPRACH format for reproduction: {cfg.fmt}")

    nra_sc = 12
    nstart = cfg.subcarrier_offset + (cfg.ninit // nra_sc) * nra_sc
    n_tilde0 = cfg.ninit % nra_sc
    num_symbol_groups = 4 * cfg.nrep
    f_values = function_f(ue_cfg.cell_id, nra_sc, num_symbol_groups // 2)

    n_tilde = np.zeros(num_symbol_groups, dtype=int)
    n_tilde[0] = n_tilde0
    for ii in range(2, num_symbol_groups + 1):
        ii_mod = (ii - 1) % 4
        prev = n_tilde[ii - 2]
        if ii_mod == 0:
            n_tilde[ii - 1] = (n_tilde0 + f_values[(ii - 1) // 4]) % nra_sc
        elif ii_mod in {1, 3} and prev % 2 == 0:
            n_tilde[ii - 1] = prev + 1
        elif ii_mod in {1, 3} and prev % 2 == 1:
            n_tilde[ii - 1] = prev - 1
        elif ii_mod == 2 and prev < 6:
            n_tilde[ii - 1] = prev + 6
        else:
            n_tilde[ii - 1] = prev - 6
    return nstart + n_tilde


def wrap_to_max_scs(delta: np.ndarray, max_scs: int) -> np.ndarray:
    wrapped = np.asarray(delta, dtype=int).copy()
    mask = np.abs(wrapped) > max_scs
    wrapped[mask] = -np.sign(wrapped[mask]) * (2 * max_scs - np.abs(wrapped[mask]))
    return wrapped


def with_ninit(cfg: NPRACHConfig, ninit: int) -> NPRACHConfig:
    return replace(cfg, ninit=ninit)
