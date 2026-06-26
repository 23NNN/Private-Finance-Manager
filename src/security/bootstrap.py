# src/security/bootstrap.py
from __future__ import annotations

from pathlib import Path
from tkinter import messagebox, simpledialog

from src.config.settings import Settings
from src.infrastructure.db.engine import dispose_engine
from src.security.manager import DbEngineConfig, SecurityManager
from src.security.security_config import (
    SecurityConfig,
    load_security_config,
    save_security_config,
    verify_pin,
    make_pin_config,
)


def _security_file(settings: Settings) -> Path:
    return (settings.data_dir / "security.json").resolve()


def _choose_mode(root) -> str:
    msg = (
        "Choose security mode\n\n"
        "1) Device protection (Windows)\n"
        "2) PIN\n"
        "3) None\n\n"
        "Do you want to enable device protection?\n"
        "Yes = Device protection\n"
        "No = more options"
    )
    if messagebox.askyesno("Security", msg, parent=root):
        return "DEVICE"

    msg2 = "Do you want to use a PIN instead?\n\nYes = PIN\nNo = None"
    if messagebox.askyesno("Security", msg2, parent=root):
        return "PIN"
    return "NONE"


def _setup_first_time(root, settings: Settings) -> SecurityConfig:
    mode = _choose_mode(root)
    if mode == "NONE":
        cfg = SecurityConfig(mode="NONE")
        save_security_config(_security_file(settings), cfg)
        return cfg

    if mode == "DEVICE":
        cfg = SecurityConfig(mode="DEVICE")
        cfg = cfg.ensure_device_key()
        save_security_config(_security_file(settings), cfg)
        return cfg

    while True:
        pin1 = simpledialog.askstring("Set PIN", "Please enter a new PIN:", show="•", parent=root)
        if pin1 is None:
            raise SystemExit(0)
        pin1 = pin1.strip()
        if len(pin1) < 4:
            messagebox.showwarning("Invalid", "The PIN must be at least 4 characters.", parent=root)
            continue
        pin2 = simpledialog.askstring("Confirm PIN", "Please enter the PIN again:", show="•", parent=root)
        if pin2 is None:
            raise SystemExit(0)
        if pin1 != pin2:
            messagebox.showwarning("Invalid", "The PINs do not match.", parent=root)
            continue
        cfg = make_pin_config(pin1)
        save_security_config(_security_file(settings), cfg)
        return cfg


def _unlock_pin(root, sec_path: Path, cfg: SecurityConfig) -> str:
    """Show the same LockOverlay used for in-app lock — consistent PIN UI at startup.

    Called before i18n is initialised, so text strings are passed explicitly.
    Root is shown temporarily, then re-hidden after the overlay closes.
    """
    from src.ui.security.lock_overlay import LockOverlay

    root.geometry("480x340")
    root.deiconify()
    root.update()

    overlay = LockOverlay(
        root,
        sec_path,
        title="Privater Finanzmanager",
        subtitle="Bitte PIN eingeben  /  Please enter PIN",
        btn_ok="OK",
        msg_wrong_pin="Falscher PIN. Noch {remaining} Versuch(e) / attempt(s) remaining.",
    )
    root.wait_window(overlay)
    root.withdraw()

    if overlay.verified_pin is None:
        raise SystemExit(1)
    return overlay.verified_pin


def bootstrap_security_and_db(root, settings: Settings) -> tuple[DbEngineConfig, callable]:
    """Returns (engine_config, on_before_close callback)."""
    mgr = SecurityManager(settings)
    cfg = load_security_config(mgr.security_path())
    if cfg is None:
        cfg = _setup_first_time(root, settings)

    pin: str | None = None
    if cfg.mode_norm() == "PIN":
        pin = _unlock_pin(root, mgr.security_path(), cfg)

    # Pre-check: Is SQLCipher driver available?
    sqlcipher_available = mgr.is_sqlcipher_available()

    try:
        # Migrate if possible (no-op if not needed)
        mgr.migrate_legacy_if_needed(cfg, pin=pin, sqlcipher_available=sqlcipher_available)
    except Exception as e:
        # Friendly message instead of stacktrace for the common "file is not a database"
        messagebox.showerror(
            "Database problem",
            "The existing database could not be read.\n\n"
            "Possible causes:\n"
            "- Database file is corrupted\n"
            "- Database is already SQLCipher-encrypted but SQLCipher is missing\n\n"
            "Details:\n"
            f"{e}",
            parent=root,
        )
        raise SystemExit(2)

    try:
        engine_cfg = mgr.make_engine_config(cfg, pin=pin, sqlcipher_available=sqlcipher_available)
    except ImportError as e:
        # Fallback to DPAPI (not crash-safe) if DB is NOT already SQLCipher.
        if cfg.mode_norm() in {"PIN", "DEVICE"} and mgr.db_is_probably_sqlcipher():
            messagebox.showerror(
                "SQLCipher missing",
                "The database is already encrypted in SQLCipher format, "
                "but the SQLCipher driver is not installed.\n\n"
                "Please install e.g. 'pysqlcipher3' (recommended for Windows) or 'sqlcipher3' and restart.",
                parent=root,
            )
            raise SystemExit(2) from e

        if cfg.mode_norm() == "NONE":
            messagebox.showwarning(
                "SQLCipher missing",
                f"{e}\n\nThe app starts without SQLCipher (mode: None).",
                parent=root,
            )
            engine_cfg = DbEngineConfig(url=f"sqlite:///{mgr.db_path().as_posix()}", creator=None)

            def on_before_close() -> None:
                dispose_engine()

            return engine_cfg, on_before_close

        messagebox.showwarning(
            "SQLCipher missing",
            "SQLCipher DBAPI not found. Install e.g. 'pysqlcipher3' (recommended for Windows) or 'sqlcipher3'.\n\n"
            "Fallback active (DPAPI encryption, not crash-safe).\n"
            "Install 'pysqlcipher3' (Windows) to enable crash-safe mode.",
            parent=root,
        )
        engine_cfg, on_before_close = mgr.make_dpapi_fallback_engine(cfg, pin=pin)
        return engine_cfg, on_before_close

    def on_before_close() -> None:
        dispose_engine()
        # SQLCipher keeps file encrypted in-place; no extra persist needed.

    return engine_cfg, on_before_close
