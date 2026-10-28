from enum import Enum


class MediaType(str, Enum):
    TEXT = "text"
    IMAGE = "image"
    AUDIO = "audio"


class Privacy(str, Enum):
    ONLY_ME = "ONLY_ME"
    GROUP = "GROUP"
    SELECTED = "SELECTED"
    SHARED = "SHARED"
    PUBLIC = "PUBLIC"
    PRIVATE_LOCKER = "PRIVATE_LOCKER"


class GroupRole(str, Enum):
    OWNER = "OWNER"
    ADMIN = "ADMIN"
    CONTRIBUTOR = "CONTRIBUTOR"
    MEMBER = "MEMBER"
    GUEST = "GUEST"


class InvitationStatus(str, Enum):
    PENDING = "PENDING"
    ACCEPTED = "ACCEPTED"
    REJECTED = "REJECTED"
    EXPIRED = "EXPIRED"
    REVOKED = "REVOKED"


class Sentiment(str, Enum):
    POSITIVE = "positive"
    NEUTRAL = "neutral"
    NEGATIVE = "negative"
    MIXED = "mixed"
    UNKNOWN = "unknown"
