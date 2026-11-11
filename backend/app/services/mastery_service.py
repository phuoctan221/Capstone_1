"""Configurable Multi-skill Mastery model for the three MVP skills.

Each skill (meaning, spelling, context) is an independent 0..100 score. The
default rule is provisional because the Project Plan does not mandate an exact
formula; it is intentionally configurable via ``Settings``:

* correct answer: +correct_gain
* correct with a hint: gain * hint_factor
* fast correct answer: +fast_bonus (response_time_ms <= fast_ms)
* wrong answer: -wrong_penalty
* clamp to [0, 100]
* learned: any skill > 0; mastered: all three >= threshold

Only the skill that was practised is updated; the other two are untouched.
"""
from __future__ import annotations

from dataclasses import dataclass

SKILLS = ("meaning", "spelling", "context")
SKILLS_SET = frozenset(SKILLS)
DEFAULT_MASTERY = {skill: 0.0 for skill in SKILLS}
MASTERY_THRESHOLD = 80.0


@dataclass(frozen=True)
class MasteryConfig:
    correct_gain: float = 10.0
    wrong_penalty: float = 5.0
    hint_factor: float = 0.5
    fast_bonus: float = 2.0
    fast_ms: int = 4000
    threshold: float = MASTERY_THRESHOLD


def _settings_config() -> MasteryConfig:
    # Imported lazily so this module stays pure and unit-testable.
    try:
        from app.core.config import settings

        return MasteryConfig(
            correct_gain=settings.MASTERY_CORRECT_GAIN,
            wrong_penalty=settings.MASTERY_WRONG_PENALTY,
            hint_factor=settings.MASTERY_HINT_FACTOR,
            fast_bonus=settings.MASTERY_FAST_BONUS,
            fast_ms=settings.MASTERY_FAST_MS,
            threshold=settings.MASTERY_THRESHOLD,
        )
    except Exception:
        return MasteryConfig()


def _clamp(value: float) -> float:
    return max(0.0, min(100.0, float(value)))


def update_skill(
    scores: dict,
    skill: str,
    correct: bool,
    response_time_ms: int = 0,
    hint_used: bool = False,
    config: MasteryConfig | None = None,
) -> dict:
    """Return a new score dict with only ``skill`` changed."""
    if skill not in SKILLS_SET:
        raise ValueError("Unknown mastery skill")
    cfg = config or _settings_config()
    updated = {name: float(scores.get(name, 0) or 0) for name in SKILLS}

    if correct:
        delta = cfg.correct_gain
        if hint_used:
            delta *= cfg.hint_factor
        elif response_time_ms and response_time_ms <= cfg.fast_ms:
            delta += cfg.fast_bonus
    else:
        delta = -cfg.wrong_penalty

    updated[skill] = _clamp(updated[skill] + delta)
    return updated


def is_learned(scores: dict) -> bool:
    return any(float(scores.get(skill, 0) or 0) > 0 for skill in SKILLS)


def is_mastered(scores: dict, threshold: float | None = None) -> bool:
    limit = _settings_config().threshold if threshold is None else threshold
    return all(float(scores.get(skill, 0) or 0) >= limit for skill in SKILLS)


def skill_learned(scores: dict, skill: str) -> bool:
    return float(scores.get(skill, 0) or 0) > 0


def skill_mastered(scores: dict, skill: str, threshold: float | None = None) -> bool:
    limit = _settings_config().threshold if threshold is None else threshold
    return float(scores.get(skill, 0) or 0) >= limit
