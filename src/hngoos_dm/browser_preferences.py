"""Validated capture preferences shared with the Chromium native host."""

import re

DEFAULTS = {"capture": False, "auto_start": False, "skip_domains": [],
            "skip_extensions": [], "only_extensions": [], "min_bytes": 0,
            "skip_domains_enabled": True, "skip_extensions_enabled": True,
            "only_extensions_enabled": False, "min_bytes_enabled": False,
            "resume_on_cancel": True, "bypass_insert": True}


def validate_preferences(value):
    if not isinstance(value, dict) or set(value)-DEFAULTS.keys():
        raise ValueError("Invalid browser preferences")
    result = {**DEFAULTS, **value}
    # Existing installations with a non-empty whitelist/size limit retain their behavior.
    for key in ("only_extensions", "min_bytes"):
        if key in value and key+"_enabled" not in value:
            result[key+"_enabled"] = bool(value[key])
    for name in ("capture", "auto_start", "skip_domains_enabled", "skip_extensions_enabled",
                 "only_extensions_enabled", "min_bytes_enabled", "resume_on_cancel", "bypass_insert"):
        if not isinstance(result[name], bool):
            raise TypeError("Capture options must be booleans")
    for name in ("skip_domains", "skip_extensions", "only_extensions"):
        entries = result[name]
        if not isinstance(entries, list) or len(entries) > 100:
            raise ValueError("At most 100 capture exceptions are allowed")
        normalized = []
        for entry in entries:
            if not isinstance(entry, str):
                raise TypeError("Capture exceptions must be strings")
            entry = entry.strip().lower().lstrip(".")
            pattern = r"[a-z0-9](?:[a-z0-9.-]{0,251}[a-z0-9])?" if name == "skip_domains" else r"[a-z0-9]{1,16}"
            if not re.fullmatch(pattern, entry) or ".." in entry:
                raise ValueError("Invalid capture exception")
            normalized.append(entry)
        result[name] = list(dict.fromkeys(normalized))
    if (isinstance(result["min_bytes"], bool) or not isinstance(result["min_bytes"], int)
            or not 0 <= result["min_bytes"] <= 1024**4):
        raise ValueError("Invalid minimum capture size")
    return result
