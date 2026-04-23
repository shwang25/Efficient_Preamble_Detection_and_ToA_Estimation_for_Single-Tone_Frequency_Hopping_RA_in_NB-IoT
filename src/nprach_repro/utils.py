from __future__ import annotations

from dataclasses import asdict, dataclass, is_dataclass, replace
import json
from pathlib import Path
from typing import Any

import numpy as np

from .config import NPRACHConfig, UEConfig
from .nprach_info import get_nprach_info, wrap_to_max_scs


@dataclass(frozen=True)
class CandidatePattern:
    ninit: int
    frequency_location: np.ndarray
    local_frequency_location: np.ndarray
    delta1: np.ndarray


def build_candidate_patterns(ue_cfg: UEConfig, base_cfg: NPRACHConfig) -> list[CandidatePattern]:
    patterns: list[CandidatePattern] = []
    for ninit in range(base_cfg.num_subcarriers):
        cfg = replace(base_cfg, ninit=ninit)
        info = get_nprach_info(ue_cfg, cfg)
        delta1 = wrap_to_max_scs(np.diff(info.frequency_location), info.max_scs)
        patterns.append(
            CandidatePattern(
                ninit=ninit,
                frequency_location=info.frequency_location.astype(int),
                local_frequency_location=info.frequency_location_local.astype(int),
                delta1=delta1.astype(int),
            )
        )
    return patterns


def ensure_dir(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    return path


def _to_jsonable(value: Any) -> Any:
    if is_dataclass(value):
        return {key: _to_jsonable(item) for key, item in asdict(value).items()}
    if isinstance(value, np.ndarray):
        return value.tolist()
    if isinstance(value, (np.floating, np.integer)):
        return value.item()
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, dict):
        return {str(key): _to_jsonable(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_to_jsonable(item) for item in value]
    return value


def dump_json(path: Path, payload: Any) -> None:
    ensure_dir(path.parent)
    path.write_text(json.dumps(_to_jsonable(payload), indent=2), encoding="utf-8")
