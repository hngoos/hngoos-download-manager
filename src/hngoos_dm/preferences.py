"""Native preference controls and an explicit, non-destructive reset boundary."""

import json
import time
import tkinter as tk
from pathlib import Path
from tkinter import ttk

from .browser_preferences import DEFAULTS as BROWSER_DEFAULTS
from .network import validate_proxy


def defaults():
    return {"theme": "dark", "language": "en", "download_directory": str(Path.home()/"Downloads"),
            "startup_enabled": True, "remove_missing": False, "remove_completed": False, "retry_failed": True,
            "auto_check_updates": True, "auto_install_updates": False, "auto_defender": False,
            "safety_provider": "defender", "high_security": False, "auto_category": False, "auto_extract": False,
            "close_to_tray": True, "transfer_mode": "maximum", "bandwidth_mode": "maximum",
            "proxy": {"mode": "direct", "url": ""}, "browser_preferences": {**BROWSER_DEFAULTS, "capture": True},
            "browser_preferences_revision": str(time.time_ns())}


def initialize(store, *, register_startup=False):
    """Fill missing defaults, preserving saved choices and isolating OS writes.

    Only normal packaged launches register with the OS. Development and tests
    use the same preference model without changing system configuration.
    """
    values = defaults()
    if store.setting("startup_enabled") is None and register_startup:
        from .startup import set_enabled
        try:
            set_enabled(values["startup_enabled"])
        except (OSError, ValueError):
            values["startup_enabled"] = False
    with store.connect() as db:
        db.executemany("INSERT OR IGNORE INTO settings VALUES(?,?)",
                       [(key, json.dumps(value)) for key, value in values.items()])


def reset(store, *, register_startup=True):
    values = defaults()
    if register_startup:
        from .startup import set_enabled
        set_enabled(values["startup_enabled"])  # Keep preferences intact if OS registration fails.
    with store.connect() as db:
        db.executemany("INSERT INTO settings VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",
                       [(key, json.dumps(value)) for key, value in values.items()])
    return values


def build_automation_settings(app, parent, group):
    def flag(key, text):
        variable = tk.BooleanVar(value=app.store.setting(key, defaults()[key]))
        def changed():
            app.store.set_setting(key, variable.get())
            if key == "auto_check_updates":
                if not variable.get():
                    install, _ = app.preference_flags["auto_install_updates"]
                    install.set(False)
                    app.store.set_setting("auto_install_updates", False)
                sync_update_controls()
        button = ttk.Checkbutton(parent, text=text, variable=variable, command=changed)
        button.pack(anchor="w", pady=4)
        app.preference_flags[key] = variable, button
        return button
    if group == "download":
        flag("retry_failed", "Tự động thử lại lượt tải bị lỗi mạng")
        return
    flag("auto_check_updates", "Kiểm tra cập nhật tự động")
    flag("auto_install_updates", "Cài đặt bản cập nhật tự động")
    def sync_update_controls():
        app.preference_flags["auto_install_updates"][1].configure(
            state="normal" if app.preference_flags["auto_check_updates"][0].get() else "disabled")
    sync_update_controls()


def build_network_settings(app, parent):
    from .rounded import ChoiceRow, RoundedEntry
    ttk.Label(parent, text="Mạng", font=("Segoe UI", 16, "bold")).pack(anchor="w", pady=(0, 10))
    policy = validate_proxy(app.store.setting("proxy", defaults()["proxy"]))
    mode, url = tk.StringVar(value=policy["mode"]), tk.StringVar(value=policy["url"])
    app.proxy_mode, app.proxy_url = mode, url
    def changed():
        if mode.get() == "manual":
            row.pack(fill="x", pady=8)
        else:
            row.pack_forget()
        try:
            policy = validate_proxy({"mode": mode.get(), "url": url.get()})
        except ValueError:
            return
        if policy != app.store.setting("proxy"):
            app.store.set_setting("proxy", policy)
    app.proxy_choices = ChoiceRow(parent, mode, [("Hệ thống", "system"), ("Không proxy", "direct"),
                             ("Thủ công", "manual")], changed, app)
    app.proxy_choices.pack(fill="x", pady=8)
    row = app.proxy_address_row = ttk.Frame(parent)
    ttk.Label(row, text="Địa chỉ proxy").pack(side="left", padx=(0, 8))
    entry = RoundedEntry(row, textvariable=url)
    entry.pack(side="left", fill="x", expand=True)
    app.save_proxy_preferences = changed
    mode.trace_add("write", lambda *_: changed())
    url.trace_add("write", lambda *_: changed())
    changed()
