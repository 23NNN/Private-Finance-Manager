# ui/main_window.py
from __future__ import annotations

import logging
import threading
import traceback
import tkinter as tk
from queue import Queue, Empty
from tkinter import ttk, filedialog, messagebox

import customtkinter as ctk

from src.ui.common.import_report_dialog import ImportReportDialog
from src.ui.common.dataset_dialog import DatasetDialog
from src.ui.common.error_dialog import show_error, show_warning
from src.ui.common.scroll_area import ScrollArea
from src.ui.common.i18n import tr, trf, get_i18n
from src.ui.common.ctk_theme import apply_for_mode

ftrf = trf  # alias used in this module

from src.config.settings import get_settings
from src.infrastructure.db.healthcheck import run_healthcheck, format_report

from src.application.services.account_service import AccountService
from src.application.services.employer_service import EmployerService
from src.application.services.expense_service import ExpenseService
from src.application.services.export_service import ExportService
from src.application.services.backup_service import BackupService
from src.application.services.security_service import SecurityService
from src.ui.security.mode_dialog import SecurityModeDialog
from src.ui.security.lock_overlay import LockOverlay
from src.application.services.import_service import ImportService
from src.application.services.income_service import IncomeService
from src.application.services.loan_service import LoanService
from src.application.services.overview_service import OverviewService
from src.application.services.reference_data_service import ReferenceDataService

from src.ui.overview.view import OverviewView
from src.ui.overview.presenter import OverviewPresenter
from src.ui.income.view import IncomeView
from src.ui.income.presenter import IncomePresenter
from src.ui.expenses.view import ExpensesView
from src.ui.expenses.presenter import ExpensesPresenter
from src.ui.accounts.view import AccountsView
from src.ui.accounts.presenter import AccountsPresenter

logger = logging.getLogger(__name__)


class MainWindow:
    def __init__(self, root: ctk.CTk, *, on_before_close=None) -> None:
        self.root = root
        self._on_before_close = on_before_close
        self.root.title(tr("app.title"))
        sw = self.root.winfo_screenwidth()
        sh = self.root.winfo_screenheight()
        w = min(1180, max(700, sw - 80))
        h = min(740, max(520, sh - 140))
        w = min(w, max(520, sw - 40))
        h = min(h, max(420, sh - 80))
        self.root.geometry(f"{w}x{h}")

        self.settings = get_settings()

        self._queue: "Queue[tuple[str, object]]" = Queue()
        self._worker_running = False

        self.account_svc = AccountService()
        self.employer_svc = EmployerService()
        self.ref_svc = ReferenceDataService()
        self.income_svc = IncomeService()
        self.expense_svc = ExpenseService()
        self.loan_svc = LoanService()
        self.overview_svc = OverviewService()
        self.import_svc = ImportService()
        self.export_svc = ExportService()
        self.backup_svc = BackupService(self.settings)
        self.security_svc = SecurityService()

        self.status = tk.StringVar(value=tr("status.ready"))

        self._install_exception_hooks()
        self._build_menu()
        self._build_ui()

        self.root.after(200, self._poll_queue)
        self.root.after(500, self._apply_loan_interest)

    # -------------------- Exceptions / Error UI --------------------
    def _install_exception_hooks(self) -> None:
        def tk_callback_exception(exc, val, tb):
            details = "".join(traceback.format_exception(exc, val, tb))
            logger.exception("Tk callback crashed: %s", val)
            show_error(
                self.root,
                tr("error.unexpected.title"),
                tr("error.unexpected.message"),
                details=details,
                db_path=self.settings.db_path(),
                log_path=self.settings.log_path(),
            )

        self.root.report_callback_exception = tk_callback_exception  # type: ignore[attr-defined]

    # -------------------- Menu/UI --------------------
    def _build_menu(self) -> None:
        m = tk.Menu(self.root)
        self.root.config(menu=m)

        file_menu = tk.Menu(m, tearoff=False)
        m.add_cascade(label=tr("menu.file"), menu=file_menu)

        security_menu = tk.Menu(m, tearoff=False)
        m.add_cascade(label=tr("menu.security"), menu=security_menu)
        security_menu.add_command(label=tr("menu.security.lock"), command=self._lock_app)
        security_menu.add_separator()
        security_menu.add_command(label=tr("menu.security.mode"), command=self.open_security_mode)
        security_menu.add_command(label=tr("menu.security.pin"), command=self.change_pin)

        lang_menu = tk.Menu(m, tearoff=False)
        m.add_cascade(label=tr("menu.languages"), menu=lang_menu)

        self._lang_var = tk.StringVar(value=(get_i18n().get_language() if get_i18n() else "en"))

        def _set_lang(code: str) -> None:
            svc = get_i18n()
            if svc is None:
                return
            try:
                svc.set_language(code)
            except Exception:
                return
            messagebox.showinfo(tr("lang.restart.title"), tr("lang.restart.msg"), parent=self.root)
            self._restart_app()

        lang_menu.add_radiobutton(label=tr("lang.de"), variable=self._lang_var, value="de", command=lambda: _set_lang("de"))
        lang_menu.add_radiobutton(label=tr("lang.en"), variable=self._lang_var, value="en", command=lambda: _set_lang("en"))
        lang_menu.add_radiobutton(label=tr("lang.fr"), variable=self._lang_var, value="fr", command=lambda: _set_lang("fr"))
        lang_menu.add_radiobutton(label=tr("lang.es"), variable=self._lang_var, value="es", command=lambda: _set_lang("es"))
        lang_menu.add_radiobutton(label=tr("lang.it"), variable=self._lang_var, value="it", command=lambda: _set_lang("it"))

        # Appearance submenu
        appearance_menu = tk.Menu(m, tearoff=False)
        m.add_cascade(label=tr("menu.appearance"), menu=appearance_menu)
        self._appearance_var = tk.StringVar(value=ctk.get_appearance_mode().lower())
        appearance_menu.add_radiobutton(
            label=tr("appearance.dark"), variable=self._appearance_var,
            value="dark", command=lambda: self._set_appearance_mode("dark"),
        )
        appearance_menu.add_radiobutton(
            label=tr("appearance.light"), variable=self._appearance_var,
            value="light", command=lambda: self._set_appearance_mode("light"),
        )
        appearance_menu.add_radiobutton(
            label=tr("appearance.system"), variable=self._appearance_var,
            value="system", command=lambda: self._set_appearance_mode("system"),
        )

        file_menu.add_command(label=tr("menu.import.excel"), command=self.import_excel)
        file_menu.add_command(label=tr("menu.import.csv"), command=self.import_csv)
        file_menu.add_separator()
        file_menu.add_command(label=tr("menu.export.csv"), command=self.export_csv)
        file_menu.add_command(label=tr("menu.template.csv"), command=self.download_csv_template)
        file_menu.add_command(label=tr("menu.template.excel"), command=self.download_excel_template)
        file_menu.add_separator()
        file_menu.add_command(label=tr("menu.backup"), command=self._do_backup)
        file_menu.add_separator()
        file_menu.add_command(label=tr("menu.db.check"), command=self.check_database)
        file_menu.add_command(label=tr("menu.info"), command=self.show_info)
        file_menu.add_command(label=tr("menu.exit"), command=self._close_app)

    def _build_ui(self) -> None:
        container = ctk.CTkFrame(self.root, corner_radius=0)
        container.pack(fill="both", expand=True)

        self.nb = ctk.CTkTabview(container, corner_radius=4)
        self.nb.pack(fill="both", expand=True, padx=4, pady=(4, 0))

        def _wrap_tab(title: str, view_cls):
            self.nb.add(title)
            tab = self.nb.tab(title)
            area = ScrollArea(tab)
            area.pack(fill="both", expand=True)
            view = view_cls(area.content)
            view.pack(fill="both", expand=True)
            return view

        self.overview_view = _wrap_tab(tr("tab.overview"), OverviewView)
        self.income_view = _wrap_tab(tr("tab.income"), IncomeView)
        self.expenses_view = _wrap_tab(tr("tab.expenses"), ExpensesView)
        self.accounts_view = _wrap_tab(tr("tab.accounts"), AccountsView)

        self.overview_presenter = OverviewPresenter(self.overview_view, self.overview_svc)

        self.income_presenter = IncomePresenter(
            self.income_view, self.income_svc, self.ref_svc, self.employer_svc
        )

        self.expenses_presenter = ExpensesPresenter(self.expenses_view, self.expense_svc, self.loan_svc, self.ref_svc)
        self.accounts_presenter = AccountsPresenter(self.accounts_view, self.account_svc, self.ref_svc)

        status_bar = ctk.CTkFrame(container, corner_radius=0, height=28)
        status_bar.pack(fill="x", side="bottom", pady=(0, 0))
        status_bar.pack_propagate(False)
        ttk.Label(status_bar, textvariable=self.status).pack(side="left", padx=8, pady=4)

    # -------------------- Appearance --------------------
    def _set_appearance_mode(self, mode: str) -> None:
        ctk.set_appearance_mode(mode)
        apply_for_mode(self.root, mode)
        try:
            from src.infrastructure.unit_of_work import UnitOfWork
            from src.infrastructure.repositories.app_settings import AppSettingRepository
            with UnitOfWork() as uow:
                AppSettingRepository(uow.session).set("ui.appearance_mode", mode)
                uow.commit()
        except Exception:
            logger.exception("Failed to persist appearance mode.")

    def _ds_labels(self, datasets: list[str]) -> list[str]:
        return [tr(f"dataset.{ds}") for ds in datasets]

    def _restart_app(self) -> None:
        try:
            self._close_app(restart=True)
        except Exception:
            pass

    # -------------------- Healthcheck --------------------
    def check_database(self) -> None:
        try:
            issues = run_healthcheck(auto_fix=True)
            summary, report = format_report(issues)
            if not issues:
                show_warning(
                    self.root,
                    tr("menu.db_check"),
                    tr("db.no_issues_found"),
                    details=report,
                    db_path=self.settings.db_path(),
                    log_path=self.settings.log_path(),
                )
                return

            fatal = any(i.severity == "FATAL" for i in issues)
            if fatal:
                show_error(
                    self.root,
                    tr("db.incompatible.title"),
                    ftrf("db.incompatible.message", summary=summary),
                    details=report,
                    db_path=self.settings.db_path(),
                    log_path=self.settings.log_path(),
                )
            else:
                show_warning(
                    self.root,
                    tr("menu.db_check"),
                    ftrf("db.warnings_found.message", summary=summary),
                    details=report,
                    db_path=self.settings.db_path(),
                    log_path=self.settings.log_path(),
                )
        except Exception as e:
            logger.exception("Healthcheck failed.")
            show_error(
                self.root,
                tr("common.error"),
                str(e),
                details=traceback.format_exc(),
                db_path=self.settings.db_path(),
                log_path=self.settings.log_path(),
            )

    # -------------------- Refresh --------------------
    def refresh_all(self) -> None:
        try:
            self.overview_presenter.refresh()
            self.income_presenter.refresh()
            self.expenses_presenter.refresh()
            self.accounts_presenter.refresh()
        except Exception:
            logger.exception("Refresh failed.")
            show_error(
                self.root,
                tr("common.error"),
                tr("common.refresh_failed"),
                details=traceback.format_exc(),
                db_path=self.settings.db_path(),
                log_path=self.settings.log_path(),
            )

    # -------------------- Worker helpers --------------------
    def _set_io_enabled(self, enabled: bool) -> None:
        _ = enabled

    def _run_in_worker(self, label: str, func, *args):
        if self._worker_running:
            show_warning(self.root, tr("common.busy"), tr("common.operation_in_progress"), db_path=self.settings.db_path(), log_path=self.settings.log_path())
            return

        self._worker_running = True
        self._set_io_enabled(False)
        self.status.set(label)

        def run():
            try:
                res = func(*args)
                self._queue.put(("ok", res))
            except Exception as e:
                logger.exception("Worker job failed.")
                self._queue.put(("err", {"message": str(e), "details": traceback.format_exc()}))

        threading.Thread(target=run, daemon=True).start()

    def _poll_queue(self) -> None:
        try:
            kind, payload = self._queue.get_nowait()
        except Empty:
            self.root.after(200, self._poll_queue)
            return

        self._worker_running = False
        self._set_io_enabled(True)

        if kind == "ok":
            self.status.set(tr("status.done"))
            if isinstance(payload, dict) and payload.get("issues"):
                issues = payload.get("issues") or []
                ImportReportDialog(self.root, issues).wait_window()
                summary = {k: v for k, v in payload.items() if k != "issues"}
                show_warning(
                    self.root,
                    tr("import.done.title"),
                    ftrf("import.done.message_with_issues", summary=summary, issues=len(issues)),
                    db_path=self.settings.db_path(),
                    log_path=self.settings.log_path(),
                )
            else:
                show_warning(
                    self.root,
                    tr("status.done"),
                    str(payload),
                    db_path=self.settings.db_path(),
                    log_path=self.settings.log_path(),
                )
            self.refresh_all()
        else:
            self.status.set(tr("status.failed"))
            if isinstance(payload, dict):
                show_error(
                    self.root,
                    tr("common.error"),
                    payload.get("message", tr("error.unknown.title")),
                    details=payload.get("details", ""),
                    db_path=self.settings.db_path(),
                    log_path=self.settings.log_path(),
                )
            else:
                show_error(
                    self.root,
                    tr("common.error"),
                    str(payload),
                    db_path=self.settings.db_path(),
                    log_path=self.settings.log_path(),
                )

        self.root.after(200, self._poll_queue)

    def _apply_loan_interest(self) -> None:
        try:
            n = self.loan_svc.apply_pending_interest_events()
            if n > 0:
                logger.info("Auto-generated %d interest event(s) for active loans.", n)
        except Exception:
            logger.exception("apply_pending_interest_events failed (non-fatal).")

    # -------------------- Backup --------------------
    def _do_backup(self) -> None:
        suggested = self.backup_svc.suggest_backup_name()
        path = filedialog.asksaveasfilename(
            parent=self.root,
            title=tr("menu.backup"),
            initialfile=suggested,
            defaultextension=".db",
            filetypes=[("SQLite DB", "*.db"), ("All files", "*.*")],
        )
        if not path:
            return
        try:
            result = self.backup_svc.backup_database(path)
            messagebox.showinfo(tr("backup.success.title"), trf("backup.success.msg", path=result.backup_path), parent=self.root)
        except Exception as exc:
            show_error(self.root, tr("common.error"), str(exc))

    # -------------------- Menu actions --------------------
    def show_info(self) -> None:
        s = self.settings
        msg = (
            "Private Finance Manager\\n\\n"
            + tr("app.local_storage_notice")
            + tr("app.autosave_notice")
            + trf("app.paths.message", db=s.db_path(), logs=s.log_path())
        )
        show_warning(self.root, tr("app.info.title"), msg, db_path=s.db_path(), log_path=s.log_path())

    def import_excel(self) -> None:
        path = filedialog.askopenfilename(
            title=tr("import.excel.pick_template"),
            filetypes=[("Excel", "*.xlsx *.xlsm"), (tr("common.filetype.all_files"), "*.*")],
        )
        if not path:
            return
        self._run_in_worker(ftrf("import.excel.selected", path=path), self.import_svc.import_excel, path)

    def import_csv(self) -> None:
        ds = DatasetDialog(self.root, tr("import.csv.title"), self.import_svc.CSV_DATASETS,
                           labels=self._ds_labels(self.import_svc.CSV_DATASETS)).show()
        if not ds:
            return
        path = filedialog.askopenfilename(
            title=ftrf("import.csv.pick_dataset", ds=ds),
            filetypes=[("CSV", "*.csv"), (tr("common.filetype.all_files"), "*.*")],
        )
        if not path:
            return
        self._run_in_worker(trf("io.import.worker_label", ds=ds, path=path), self.import_svc.import_csv, path, ds)

    def export_csv(self) -> None:
        ds = DatasetDialog(self.root, tr("export.csv.title"), self.export_svc.DATASETS,
                           labels=self._ds_labels(self.export_svc.DATASETS)).show()
        if not ds:
            return

        period = None
        if ds in ("income_fixed", "income_hourly", "expense_variable"):
            period = self.overview_view.get_period()

        path = filedialog.asksaveasfilename(
            title=ftrf("export.csv.pick_dataset", ds=ds),
            defaultextension=".csv",
            filetypes=[("CSV", "*.csv")],
            initialfile=f"{ds}.csv",
        )
        if not path:
            return

        self._run_in_worker(trf("io.export.worker_label", ds=ds, path=path), self.export_svc.export_csv, path, ds, period)

    def download_csv_template(self) -> None:
        ds = DatasetDialog(self.root, tr("menu.template.csv"), self.export_svc.DATASETS,
                           labels=self._ds_labels(self.export_svc.DATASETS)).show()
        if not ds:
            return
        path = filedialog.asksaveasfilename(
            title=tr("menu.template.csv"),
            defaultextension=".csv",
            filetypes=[("CSV", "*.csv"), (tr("common.filetype.all_files"), "*.*")],
            initialfile=f"{ds}_template.csv",
        )
        if not path:
            return
        try:
            self.export_svc.write_csv_template(path, ds, include_examples=True)
            messagebox.showinfo(tr("template.saved.title"), trf("template.saved.msg", path=path), parent=self.root)
        except Exception as exc:
            show_error(self.root, tr("common.error"), str(exc),
                       db_path=self.settings.db_path(), log_path=self.settings.log_path())

    def download_excel_template(self) -> None:
        path = filedialog.asksaveasfilename(
            title=tr("menu.template.excel"),
            defaultextension=".xlsx",
            filetypes=[("Excel", "*.xlsx"), (tr("common.filetype.all_files"), "*.*")],
            initialfile="import_template.xlsx",
        )
        if not path:
            return
        try:
            self.export_svc.write_excel_template(path)
            messagebox.showinfo(tr("template.saved.title"), trf("template.saved.msg", path=path), parent=self.root)
        except Exception as exc:
            show_error(self.root, tr("common.error"), str(exc),
                       db_path=self.settings.db_path(), log_path=self.settings.log_path())

    def _close_app(self, restart: bool = False) -> None:
        """Closes the app (incl. security/DB shutdown hook)."""
        try:
            if callable(self._on_before_close):
                self._on_before_close()
        finally:
            try:
                self.root.destroy()
            except Exception:
                pass

        if restart:
            import os
            import sys
            os.execv(sys.executable, [sys.executable] + sys.argv)

    def _lock_app(self) -> None:
        from src.security.manager import SecurityManager
        sec_path = SecurityManager(self.settings).security_path()
        cfg = None
        try:
            from src.security.security_config import load_security_config
            cfg = load_security_config(sec_path)
        except Exception:
            pass

        if cfg is None or not cfg.has_pin():
            messagebox.showinfo(tr("lock.unavailable.title"), tr("lock.unavailable.msg"), parent=self.root)
            return

        LockOverlay(self.root, sec_path)

    def open_security_mode(self) -> None:
        try:
            current = self.security_svc.get_status().mode
            dlg = SecurityModeDialog(self.root, current_mode=current)
            self.root.wait_window(dlg)
            if not dlg.result:
                return

            new_mode = dlg.result
            if new_mode == current:
                return

            current_pin = None
            new_pin = None

            if current == tr("pin.title"):
                from tkinter import simpledialog
                pin = simpledialog.askstring(tr("pin.required.title"), tr("pin.prompt.current"), show="•", parent=self.root)
                if pin is None:
                    return
                current_pin = pin.strip()

            if new_mode == tr("pin.title"):
                from tkinter import simpledialog
                p1 = simpledialog.askstring(tr("pin.new.title"), tr("pin.prompt.new"), show="•", parent=self.root)
                if p1 is None:
                    return
                p1 = p1.strip()
                if len(p1) < 4:
                    messagebox.showwarning(tr("common.invalid"), tr("pin.error.min_length"), parent=self.root)
                    return
                p2 = simpledialog.askstring(tr("pin.new.title"), tr("pin.prompt.confirm"), show="•", parent=self.root)
                if p2 is None:
                    return
                if p1 != p2:
                    messagebox.showwarning(tr("common.invalid"), tr("pin.error.mismatch"), parent=self.root)
                    return
                new_pin = p1

            if new_mode == "NONE":
                if not messagebox.askyesno(
                    tr("common.warning"),
                    tr("security.none_warning.message"),
                    parent=self.root,
                ):
                    return

            self.security_svc.set_mode(new_mode=new_mode, current_pin=current_pin, new_pin=new_pin)
            messagebox.showinfo(tr("menu.security"), tr("security.mode_changed_restart.message"), parent=self.root)
            self._close_app()
        except Exception as e:
            messagebox.showerror(tr("common.error"), ftrf("security.mode_change_failed.message", error=e), parent=self.root)

    def change_pin(self) -> None:
        try:
            mode = self.security_svc.get_status().mode
            from tkinter import simpledialog
            if mode != tr("pin.title"):
                messagebox.showinfo(tr("common.notice"), tr("pin.change_unavailable.message"), parent=self.root)
                return

            old_pin = simpledialog.askstring(tr("pin.change.title"), tr("pin.label.current"), show="•", parent=self.root)
            if old_pin is None:
                return
            old_pin = old_pin.strip()

            p1 = simpledialog.askstring(tr("pin.change.title"), tr("pin.label.new"), show="•", parent=self.root)
            if p1 is None:
                return
            p1 = p1.strip()
            if len(p1) < 4:
                messagebox.showwarning(tr("common.invalid"), tr("pin.error.min_length"), parent=self.root)
                return
            p2 = simpledialog.askstring(tr("pin.change.title"), tr("pin.label.confirm"), show="•", parent=self.root)
            if p2 is None:
                return
            if p1 != p2:
                messagebox.showwarning(tr("common.invalid"), tr("pin.error.mismatch"), parent=self.root)
                return

            self.security_svc.change_pin(old_pin=old_pin, new_pin=p1)
            messagebox.showinfo(tr("menu.security"), tr("pin.changed_restart.message"), parent=self.root)
            self._close_app()
        except Exception as e:
            messagebox.showerror(tr("common.error"), ftrf("pin.change_failed.message", error=e), parent=self.root)


def run_app(*, root: ctk.CTk | None = None, on_before_close=None) -> None:
    if root is None:
        root = ctk.CTk()
    else:
        try:
            root.deiconify()
        except Exception:
            pass

    # Apply base TTK theme + dark/light overlay
    try:
        style = ttk.Style(root)
        style.theme_use("clam")
    except Exception:
        pass
    apply_for_mode(root, ctk.get_appearance_mode())

    settings = get_settings()

    # Healthcheck before UI setup (prevents "mysterious" tab crashes)
    try:
        issues = run_healthcheck(auto_fix=True)
        if issues:
            summary, report = format_report(issues)
            fatal = any(i.severity == "FATAL" for i in issues)
            if fatal:
                show_error(
                    root,
                    tr("db.incompatible.title"),
                    ftrf("db.incompatible.message", summary=summary),
                    details=report,
                    db_path=settings.db_path(),
                    log_path=settings.log_path(),
                )
                root.destroy()
                return
            show_warning(
                root,
                tr("menu.db_check"),
                ftrf("db.warnings_found.message", summary=summary),
                details=report,
                db_path=settings.db_path(),
                log_path=settings.log_path(),
            )
    except Exception:
        show_error(
            root,
            tr("common.error"),
            tr("db.check_failed.message"),
            details=traceback.format_exc(),
            db_path=settings.db_path(),
            log_path=settings.log_path(),
        )
    w = MainWindow(root, on_before_close=on_before_close)

    try:
        root.protocol("WM_DELETE_WINDOW", w._close_app)
    except Exception:
        pass

    root.mainloop()
