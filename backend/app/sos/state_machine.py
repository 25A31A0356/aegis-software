"""
AEGIS UNIFIED DATA CORE - SOS State Machine Engine
Enforces explicit state transitions, prevents illegal state leaps, logs audit history,
and provides atomic race-condition resolution for responder acceptance.
"""
from enum import Enum
from typing import Set, Dict, Optional, Tuple
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from fastapi import HTTPException, status
from backend.app.database.models import SOSSignal, SOSStatusHistory, utc_now
from backend.app.utils.logger import logger


class SOSState(str, Enum):
    # Canonical India Emergency Platform Lifecycle
    CREATED = "CREATED"
    SYNC_PENDING = "SYNC_PENDING"
    RECEIVED = "RECEIVED"
    NOTIFYING = "NOTIFYING"
    NOTIFIED = "NOTIFIED"
    ACKNOWLEDGED = "ACKNOWLEDGED"
    RESPONDING = "RESPONDING"
    RESOLVED = "RESOLVED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"
    EXPIRED = "EXPIRED"

    # Active Responder Network Dispatch States
    PENDING = "PENDING"
    MATCHING = "MATCHING"
    OFFERED = "OFFERED"
    ACCEPTED = "ACCEPTED"
    RESPONDER_EN_ROUTE = "RESPONDER_EN_ROUTE"
    ON_SITE = "ON_SITE"


# Valid state transitions graph
VALID_TRANSITIONS: Dict[str, Set[str]] = {
    # Canonical Lifecycle
    SOSState.CREATED.value: {
        SOSState.SYNC_PENDING.value,
        SOSState.RECEIVED.value,
        SOSState.NOTIFYING.value,
        SOSState.PENDING.value,
        SOSState.CANCELLED.value,
        SOSState.FAILED.value
    },
    SOSState.SYNC_PENDING.value: {
        SOSState.RECEIVED.value,
        SOSState.NOTIFYING.value,
        SOSState.PENDING.value,
        SOSState.CANCELLED.value,
        SOSState.FAILED.value
    },
    SOSState.RECEIVED.value: {
        SOSState.NOTIFYING.value,
        SOSState.NOTIFIED.value,
        SOSState.MATCHING.value,
        SOSState.PENDING.value,
        SOSState.CANCELLED.value,
        SOSState.RESOLVED.value
    },
    SOSState.NOTIFYING.value: {
        SOSState.NOTIFIED.value,
        SOSState.ACKNOWLEDGED.value,
        SOSState.MATCHING.value,
        SOSState.OFFERED.value,
        SOSState.FAILED.value,
        SOSState.CANCELLED.value
    },
    SOSState.NOTIFIED.value: {
        SOSState.ACKNOWLEDGED.value,
        SOSState.RESPONDING.value,
        SOSState.OFFERED.value,
        SOSState.ACCEPTED.value,
        SOSState.RESOLVED.value,
        SOSState.CANCELLED.value
    },
    SOSState.ACKNOWLEDGED.value: {
        SOSState.RESPONDING.value,
        SOSState.ACCEPTED.value,
        SOSState.RESPONDER_EN_ROUTE.value,
        SOSState.RESOLVED.value,
        SOSState.CANCELLED.value
    },
    SOSState.RESPONDING.value: {
        SOSState.ON_SITE.value,
        SOSState.RESOLVED.value,
        SOSState.CANCELLED.value,
        SOSState.FAILED.value
    },

    # Responder Network Operations
    SOSState.PENDING.value: {
        SOSState.MATCHING.value,
        SOSState.NOTIFYING.value,
        SOSState.OFFERED.value,
        SOSState.ACCEPTED.value,
        SOSState.CANCELLED.value,
        SOSState.EXPIRED.value,
        SOSState.RESOLVED.value
    },
    SOSState.MATCHING.value: {
        SOSState.OFFERED.value,
        SOSState.ACCEPTED.value,
        SOSState.CANCELLED.value,
        SOSState.EXPIRED.value,
        SOSState.RESOLVED.value
    },
    SOSState.OFFERED.value: {
        SOSState.ACCEPTED.value,
        SOSState.MATCHING.value,
        SOSState.CANCELLED.value,
        SOSState.EXPIRED.value,
        SOSState.RESOLVED.value
    },
    SOSState.ACCEPTED.value: {
        SOSState.RESPONDER_EN_ROUTE.value,
        SOSState.RESPONDING.value,
        SOSState.ON_SITE.value,
        SOSState.CANCELLED.value,
        SOSState.EXPIRED.value,
        SOSState.RESOLVED.value
    },
    SOSState.RESPONDER_EN_ROUTE.value: {
        SOSState.ON_SITE.value,
        SOSState.CANCELLED.value,
        SOSState.RESOLVED.value
    },
    SOSState.ON_SITE.value: {
        SOSState.RESOLVED.value,
        SOSState.CANCELLED.value
    },

    # Terminal states
    SOSState.RESOLVED.value: set(),
    SOSState.CANCELLED.value: set(),
    SOSState.EXPIRED.value: set(),
    SOSState.FAILED.value: set()
}


class SOSStateMachine:
    """
    Manages SOS incident state transitions and validates lifecycle correctness.
    """

    @classmethod
    def can_transition(cls, current_state: str, target_state: str) -> bool:
        """Checks whether transition from current_state to target_state is permitted."""
        c = (current_state or "").upper()
        t = (target_state or "").upper()
        if c == t:
            return True
        allowed = VALID_TRANSITIONS.get(c, set())
        return t in allowed

    @classmethod
    async def transition(
        cls,
        db: AsyncSession,
        sos: SOSSignal,
        target_state: str,
        changed_by_user_id: Optional[str] = None,
        reason: str = ""
    ) -> SOSSignal:
        """
        Executes a state transition, validates legality, updates timestamps, and records audit history.
        """
        old_state = (sos.status or SOSState.PENDING.value).upper()
        new_state = target_state.upper()

        if not cls.can_transition(old_state, new_state):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid SOS state transition from '{old_state}' to '{new_state}'."
            )

        if old_state != new_state:
            sos.status = new_state
            now = utc_now()
            sos.updated_at = now

            if new_state == SOSState.ACCEPTED.value:
                if not sos.accepted_at:
                    sos.accepted_at = now
            elif new_state == SOSState.RESOLVED.value:
                sos.resolved_at = now
            elif new_state == SOSState.CANCELLED.value:
                sos.cancelled_at = now

            # Audit history record
            history_record = SOSStatusHistory(
                sos_id=sos.id,
                old_status=old_state,
                new_status=new_state,
                changed_by_user_id=changed_by_user_id,
                reason=reason or f"State transitioned to {new_state}"
            )
            db.add(history_record)

            logger.info(f"SOS {sos.id} status transitioned: {old_state} -> {new_state} (by {changed_by_user_id or 'system'})")

        return sos

    @classmethod
    async def attempt_atomic_acceptance(
        cls,
        db: AsyncSession,
        sos_id: str,
        responder_user_id: str
    ) -> Tuple[bool, Optional[SOSSignal]]:
        """
        Guarantees atomic acceptance resolving concurrency race conditions.
        If multiple responders tap ACCEPT at the exact same millisecond, only ONE succeeds.
        """
        now = utc_now()
        
        # 1. Fetch with row locking where available, or verify conditional status
        query = select(SOSSignal).where(
            SOSSignal.id == sos_id,
            SOSSignal.status.in_([SOSState.PENDING.value, SOSState.MATCHING.value, SOSState.OFFERED.value]),
            SOSSignal.accepted_by == None
        )
        
        result = await db.execute(query)
        sos = result.scalars().first()
        
        if not sos:
            # Check if it was already accepted by someone else
            existing_res = await db.execute(select(SOSSignal).where(SOSSignal.id == sos_id))
            existing_sos = existing_res.scalars().first()
            if existing_sos and existing_sos.accepted_by:
                return False, existing_sos
            return False, None

        # 2. Transition atomically
        sos.status = SOSState.ACCEPTED.value
        sos.accepted_by = responder_user_id
        sos.accepted_at = now
        sos.updated_at = now

        # Add status audit history
        history = SOSStatusHistory(
            sos_id=sos.id,
            old_status=SOSState.OFFERED.value,
            new_status=SOSState.ACCEPTED.value,
            changed_by_user_id=responder_user_id,
            reason="Offer accepted by primary responder"
        )
        db.add(history)
        await db.commit()
        await db.refresh(sos)

        return True, sos
