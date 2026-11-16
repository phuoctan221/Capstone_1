"""Run a unit of work in a MongoDB transaction when supported.

Atlas replica sets support multi-document transactions. A local standalone
``mongod`` does not; in that case we fall back to a best-effort non-transaction
path so development still works. Production must use a replica set/Atlas.
"""
from __future__ import annotations

import logging

from pymongo.errors import ConfigurationError, OperationFailure

logger = logging.getLogger("uvicorn.error")

_UNSUPPORTED_CODES = {20, 251, 303}
_UNSUPPORTED_HINTS = (
    "transaction numbers are only allowed",
    "does not support transactions",
    "replica set",
    "mongos",
)


def _is_unsupported(exc: Exception) -> bool:
    if isinstance(exc, OperationFailure) and exc.code in _UNSUPPORTED_CODES:
        return True
    text = str(exc).lower()
    return any(hint in text for hint in _UNSUPPORTED_HINTS)


async def run_in_transaction(db, work):
    """``work`` receives a session or ``None`` and must be idempotent."""
    try:
        async with await db.client.start_session() as session:
            async with session.start_transaction():
                return await work(session)
    except (OperationFailure, ConfigurationError) as exc:
        if _is_unsupported(exc):
            logger.warning(
                "Transactions unavailable on this MongoDB deployment; "
                "falling back to non-transactional writes. Use a replica set in production."
            )
            return await work(None)
        raise
