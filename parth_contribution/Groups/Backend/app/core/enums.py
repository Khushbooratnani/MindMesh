from enum import Enum


class MediaType(str, Enum):
    TEXT = "text"
    IMAGE = "image"
    AUDIO = "audio"


class Privacy(str, Enum):
    ONLY_ME = "ONLY_ME"
    GROUP = "GROUP"
    SELECTED = "SELECTED"
    PRIVATE_LOCKER = "PRIVATE_LOCKER"


class Sentiment(str, Enum):
    POSITIVE = "positive"
    NEUTRAL = "neutral"
    NEGATIVE = "negative"
    MIXED = "mixed"
    UNKNOWN = "unknown"
