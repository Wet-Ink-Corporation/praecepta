"""TaskIQ error hierarchy for structured error handling.

Provides a base exception class and specific subtypes for common
TaskIQ failure modes, enabling distinct catch clauses and dead-letter
queue classification (transient vs permanent).
"""

from __future__ import annotations


class TaskIQError(Exception):
    """Base exception for all TaskIQ infrastructure errors.

    Subclasses distinguish transient errors (retryable) from
    permanent errors (should go to dead-letter queue).
    """

    #: Whether this error type is considered transient (retryable).
    transient: bool = False


class TaskIQBrokerError(TaskIQError):
    """Raised when broker startup/shutdown or connection fails.

    Typically transient — the broker may recover on retry.
    """

    transient: bool = True


class TaskIQSerializationError(TaskIQError):
    """Raised when task arguments cannot be serialized/deserialized.

    Permanent — retrying won't fix a serialization mismatch.
    """

    transient: bool = False


class TaskIQResultError(TaskIQError):
    """Raised when storing or retrieving task results fails.

    Typically transient — result backend may recover.
    """

    transient: bool = True
