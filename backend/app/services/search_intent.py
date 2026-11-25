"""Deterministic first-pass detection for questions needing current sources."""

import re

_CURRENT_MARKER = re.compile(
    r"\b(?:latest|newest|recent(?:ly)?|current(?:ly)?|today|tonight|yesterday|"
    r"right now|as of|breaking|up[- ]to[- ]date|this (?:morning|afternoon|evening|week|month|year)|"
    r"last (?:week|month|year)|aaj|abhi|filhaal|is waqt|haal hi mein|taaza|"
    r"kal (?:ka|ki|ke)|pichhle (?:hafte|mahine|saal))\b",
    re.IGNORECASE,
)
_LIVE_SUBJECT = re.compile(
    r"\b(?:news|headlines|weather|forecast|stock prices?|share prices?|exchange rates?|"
    r"pricing|prices?|who won|scores? of|match results?|updates? about|updates? on|"
    r"announcements? about|announcements? from|what(?:'s| is) new|khabar(?:en)?|mausam|"
    r"qeemat(?:en)?|kimat|kis ne jeeta|nateeja)\b",
    re.IGNORECASE,
)
_VERSION_QUESTION = re.compile(r"\b(?:version|release)\b", re.IGNORECASE)
_VERSION_CONTROL = re.compile(r"\bversion control\b", re.IGNORECASE)


def needs_web_search(message: str) -> bool:
    """Return true only when wording indicates current or changing information."""
    if _CURRENT_MARKER.search(message) or _LIVE_SUBJECT.search(message):
        return True
    return bool(_VERSION_QUESTION.search(message) and not _VERSION_CONTROL.search(message))
