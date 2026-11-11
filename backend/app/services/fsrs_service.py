"""FSRS adapter built on the pinned ``fsrs==6.3.2`` package.

The engine keeps per-word state. Retrievability is computed at read time;
Difficulty/Stability and the due date are only updated by an explicit review.
One answer attempt is NOT automatically an FSRS review event.
"""
from __future__ import annotations

from datetime import datetime, timezone

from fsrs import Card, Rating, Scheduler

scheduler = Scheduler(enable_fuzzing=False)

RATINGS = {
    "again": Rating.Again,
    "hard": Rating.Hard,
    "good": Rating.Good,
    "easy": Rating.Easy,
}


def _utc_now(now: datetime | None = None) -> datetime:
    now = now or datetime.now(timezone.utc)
    if now.tzinfo is None:
        raise ValueError("Review time must be UTC-aware")
    return now.astimezone(timezone.utc)


def _card_to_state(card: Card) -> dict:
    return {
        "card_json": card.to_json(),
        "card_id": card.card_id,
        "state": int(card.state),
        "step": card.step,
        "difficulty": card.difficulty,
        "stability": card.stability,
        "due_at": card.due,
        "last_reviewed_at": card.last_review,
    }


def new_card_state(now: datetime | None = None) -> dict:
    """Initial FSRS state when a learner starts studying a word."""
    card = Card(due=_utc_now(now))
    return _card_to_state(card)


def schedule_review(
    card_json: str | None, rating: int, now: datetime | None = None
) -> dict:
    if rating not in (1, 2, 3, 4):
        raise ValueError("FSRS rating must be 1..4")
    now = _utc_now(now)
    card = Card.from_json(card_json) if card_json else Card()
    updated, log = scheduler.review_card(card, Rating(rating), review_datetime=now)
    return {
        "state": _card_to_state(updated),
        "log_json": log.to_json(),
        "retrievability": scheduler.get_card_retrievability(
            updated, current_datetime=now
        ),
    }


def current_retrievability(
    card_json: str | None, now: datetime | None = None
) -> float:
    if not card_json:
        return 0.0
    try:
        card = Card.from_json(card_json)
        return float(
            scheduler.get_card_retrievability(
                card, current_datetime=_utc_now(now)
            )
        )
    except Exception:
        return 0.0
