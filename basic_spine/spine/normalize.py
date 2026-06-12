"""ID/name normalization for matching lender MIS lines to reported disbursements.

This is the most important code in the prototype: the reported side stores the
lender's application id, the MIS side often keys on the LAN instead, and ids
are written inconsistently (prefixes, separators, invisible Unicode). Every
key on both sides goes through these functions before comparison.
"""

import hashlib
import re

ZERO_WIDTH = dict.fromkeys(map(ord, "\u200b\u200c\u200d\ufeff\u00a0"), None)


def strip_invisibles(s: str) -> str:
    return (s or "").translate(ZERO_WIDTH)


def norm_id(s, *, strip_l_prefix=False):
    """Canonical compact id: kill invisibles, uppercase, remove separators."""
    if s is None:
        return ""
    s = strip_invisibles(str(s)).strip().upper()
    s = re.sub(r"[\s\\/_\-]", "", s)  # spaces, backslash, slash, underscore, hyphen
    if strip_l_prefix and s.startswith("L"):  # AU writes LAN as L9001..., app as HFT-...
        s = s[1:]
    s = re.sub(r"^HFT", "", s)  # AU app-no prefix seen in emails
    return s


def norm_name(s):
    s = strip_invisibles(str(s or "")).upper()
    s = re.sub(r"[^A-Z ]", "", s)
    return re.sub(r"\s+", " ", s).strip()


def fingerprint(lan, app, amt, ddate, name):
    raw = "|".join([norm_id(lan), norm_id(app), str(amt or ""), str(ddate or ""), norm_name(name)])
    return hashlib.sha1(raw.encode()).hexdigest()
