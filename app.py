# finanzmanager/app.py
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parent
# For 'import src....' the parent of "src/" must be on sys.path (i.e. repo root).
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from src.config.settings import get_settings


def _parse_args(argv: list[str]) -> argparse.Namespace:
    p = argparse.ArgumentParser(prog="Private-Finance-Manager")
    p.add_argument("--portable", action="store_true", help="DB/Logs neben der EXE in data/ speichern")
    p.add_argument("--data-dir", type=str, default=None, help="Überschreibt Daten-Verzeichnis")
    p.add_argument("--log-dir", type=str, default=None, help="Überschreibt Log-Verzeichnis")
    return p.parse_args(argv)


def _apply_overrides(args: argparse.Namespace) -> None:
    if args.portable:
        os.environ["FINANZMANAGER_PORTABLE"] = "1"
    if args.data_dir:
        os.environ["FINANZMANAGER_DATA_DIR"] = args.data_dir
    if args.log_dir:
        os.environ["FINANZMANAGER_LOG_DIR"] = args.log_dir


def main(argv: list[str]) -> int:
    args = _parse_args(argv)
    _apply_overrides(args)

    settings = get_settings()
    settings.data_dir.mkdir(parents=True, exist_ok=True)
    settings.log_dir.mkdir(parents=True, exist_ok=True)

    from src.infrastructure.logging_setup import configure_logging
    from src.infrastructure.db.engine import init_engine
    from src.infrastructure.db.migrations.runner import upgrade_db_if_possible
    from src.ui.main_window import run_app

    import tkinter as tk
    from src.security.bootstrap import bootstrap_security_and_db

    configure_logging(settings.log_path())

    root = tk.Tk()
    root.withdraw()

    engine_cfg, on_before_close = bootstrap_security_and_db(root, settings)
    init_engine(engine_cfg.url, creator=engine_cfg.creator)
    upgrade_db_if_possible()

    # i18n bootstrap
    from src.application.services.i18n_service import I18nService
    from src.ui.common.i18n import init_i18n

    init_i18n(I18nService())

    run_app(root=root, on_before_close=on_before_close)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
