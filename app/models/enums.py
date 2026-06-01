from enum import Enum


class UserStatus(str, Enum):
    ACTIVE = "active"
    BLOCKED = "blocked"


class PurchaseStatus(str, Enum):
    PENDING = "pending"
    COMPLETED = "completed"
    FAILED = "failed"
    REFUNDED = "refunded"


class TopUpStatus(str, Enum):
    PENDING = "pending"
    APPLIED = "applied"
    CANCELED = "canceled"


class RefundStatus(str, Enum):
    PENDING = "pending"
    APPLIED = "applied"
    REJECTED = "rejected"
