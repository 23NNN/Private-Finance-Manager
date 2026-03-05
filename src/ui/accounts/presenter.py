# src/ui/accounts/presenter.py
from __future__ import annotations

import logging
import traceback
from tkinter import messagebox

from src.application.dto.accounts import AccountDTO
from src.application.services.account_service import AccountService
from src.config.settings import get_settings
from src.ui.common.dialogs import FieldSpec, FormDialog
from src.ui.common.error_dialog import show_error, show_warning
from src.ui.common.i18n import tr

logger = logging.getLogger(__name__)


def _bind_row_double_click(tree, fn) -> None:
    """Binds double-click on a row (not on the header).

    - add="+" so that sort-reset and other bindings are preserved
    - Header double-click is ignored (no unintended editing)
    """

    def _h(e):
        try:
            if tree.identify_region(e.x, e.y) == "heading":
                return
        except Exception:
            return
        fn()

    tree.bind("<Double-1>", _h, add="+")


class AccountsPresenter:
    def __init__(self, view, account_service: AccountService, *_unused):
        self._view = view
        self._svc = account_service
        self._settings = get_settings()
        self._sort_state: dict[tuple[int, str], bool] = {}

        self._view.bind_refresh(self.refresh)
        if hasattr(self._view, "bind_filter_change"):
            self._view.bind_filter_change(self.refresh)

        self._view.add_btn.configure(command=self.add_account)
        self._view.edit_btn.configure(command=self.edit_account)
        self._view.delete_btn.configure(command=self.delete_account)

        _bind_row_double_click(self._view.tree, lambda: self.edit_account())
        self._view.tree.bind("<Delete>", lambda _e: self.delete_account())

    # -------------------- helpers --------------------
    def _root(self):
        return self._view.winfo_toplevel()

    def _err(self, title: str, msg: str) -> None:
        show_error(
            self._root(),
            title,
            msg,
            details=traceback.format_exc(),
            db_path=self._settings.db_path(),
            log_path=self._settings.log_path(),
        )

    def _warn(self, title: str, msg: str) -> None:
        show_warning(
            self._root(),
            title,
            msg,
            db_path=self._settings.db_path(),
            log_path=self._settings.log_path(),
        )

    @staticmethod
    def _selected_id(tree) -> int | None:
        sel = tree.selection()
        if not sel:
            return None
        try:
            return int(sel[0])
        except Exception:
            return None

    def _get_filters(self) -> dict[str, str]:
        if hasattr(self._view, "get_filters"):
            return self._view.get_filters()
        return {"account": "", "bank": ""}

    @staticmethod
    def _matches(text: str | None, needle: str) -> bool:
        if not needle:
            return True
        return needle.lower() in (text or "").lower()

    # -------------------- sorting --------------------
    def _attach_sorting(self) -> None:
        """Sorting is handled centrally in src.ui.common.controls."""
        return

    def _sort_tree(self, tree, col: str) -> None:
        key = (id(tree), col)
        reverse = self._sort_state.get(key, False)
        yes = tr("common.yes").casefold()

        def to_key(val: str):
            v = (val or "").strip()
            if col in {"role_income", "role_debit"}:
                return 1 if v.casefold() == yes else 0
            return v.casefold()

        items = [(tree.set(iid, col), iid) for iid in tree.get_children("")]
        items.sort(key=lambda x: to_key(x[0]), reverse=reverse)

        for idx, (_val, iid) in enumerate(items):
            tree.move(iid, "", idx)

        self._sort_state[key] = not reverse

    # -------------------- core --------------------
    def refresh(self) -> None:
        try:
            rows = self._svc.list_accounts()
            f = self._get_filters()
            acc_q = (f.get("account") or "").strip()
            bank_q = (f.get("bank") or "").strip()

            filtered = []
            for a in rows:
                if not (self._matches(a.account_name, acc_q) or self._matches(a.label, acc_q)):
                    continue
                if not self._matches(a.bank_name, bank_q):
                    continue
                filtered.append(a)

            yes = tr("common.yes")
            no = tr("common.no")

            self._view.tree.delete(*self._view.tree.get_children())
            for a in filtered:
                self._view.tree.insert(
                    "",
                    "end",
                    iid=str(a.id),
                    values=(
                        a.label,
                        a.account_name,
                        a.bank_name or "",
                        a.iban or "",
                        yes if a.role_income else no,
                        yes if a.role_debit else no,
                    ),
                )
        except Exception:
            logger.exception("accounts.refresh_failed")
            self._err(tr("common.error"), tr("accounts.error.load_failed"))

    # -------------------- CRUD --------------------
    def add_account(self) -> None:
        fields = [
            FieldSpec("label", tr("accounts.field.label"), "entry", required=True, width=30),
            FieldSpec("account_name", tr("accounts.field.account_name"), "entry", required=True, width=40),
            FieldSpec("bank_name", tr("accounts.field.bank_name"), "entry", required=False, width=40),
            FieldSpec("iban", tr("accounts.field.iban"), "entry", required=False, width=40),
            FieldSpec("role_income", tr("accounts.field.role_income"), "check", required=False),
            FieldSpec("role_debit", tr("accounts.field.role_debit"), "check", required=False),
            FieldSpec("notes", tr("accounts.field.notes"), "text", required=False, width=60),
        ]
        dlg = FormDialog(self._view, tr("accounts.dialog.add_title"), fields, initial={"role_income": True, "role_debit": True})
        data = dlg.show()
        if not data:
            return

        try:
            dto = AccountDTO(
                id=None,
                label=str(data["label"]).strip(),
                account_name=str(data["account_name"]).strip(),
                bank_name=str(data.get("bank_name") or "").strip() or None,
                iban=str(data.get("iban") or "").strip() or None,
                role_income=bool(data.get("role_income")),
                role_debit=bool(data.get("role_debit")),
                notes=str(data.get("notes") or "").strip() or None,
            )
            self._svc.upsert_account(dto)
            self.refresh()
        except Exception:
            logger.exception("accounts.add_failed")
            self._err(tr("common.error"), tr("accounts.error.save_failed"))

    def edit_account(self) -> None:
        aid = self._selected_id(self._view.tree)
        if not aid:
            self._warn(tr("common.notice"), tr("accounts.warn.select_account"))
            return
        try:
            all_rows = self._svc.list_accounts()
            obj = next((x for x in all_rows if x.id == aid), None)
            if not obj:
                self._err(tr("common.error"), tr("accounts.error.not_found"))
                return

            fields = [
                FieldSpec("label", tr("accounts.field.label"), "entry", required=True, width=30),
                FieldSpec("account_name", tr("accounts.field.account_name"), "entry", required=True, width=40),
                FieldSpec("bank_name", tr("accounts.field.bank_name"), "entry", required=False, width=40),
                FieldSpec("iban", tr("accounts.field.iban"), "entry", required=False, width=40),
                FieldSpec("role_income", tr("accounts.field.role_income"), "check", required=False),
                FieldSpec("role_debit", tr("accounts.field.role_debit"), "check", required=False),
                FieldSpec("notes", tr("accounts.field.notes"), "text", required=False, width=60),
            ]
            initial = {
                "label": obj.label,
                "account_name": obj.account_name,
                "bank_name": obj.bank_name or "",
                "iban": obj.iban or "",
                "role_income": obj.role_income,
                "role_debit": obj.role_debit,
                "notes": obj.notes or "",
            }
            dlg = FormDialog(self._view, tr("accounts.dialog.edit_title"), fields, initial=initial)
            data = dlg.show()
            if not data:
                return

            dto = AccountDTO(
                id=aid,
                label=str(data["label"]).strip(),
                account_name=str(data["account_name"]).strip(),
                bank_name=str(data.get("bank_name") or "").strip() or None,
                iban=str(data.get("iban") or "").strip() or None,
                role_income=bool(data.get("role_income")),
                role_debit=bool(data.get("role_debit")),
                notes=str(data.get("notes") or "").strip() or None,
            )
            self._svc.upsert_account(dto)
            self.refresh()
        except Exception:
            logger.exception("accounts.edit_failed")
            self._err(tr("common.error"), tr("accounts.error.save_failed"))

    def delete_account(self) -> None:
        aid = self._selected_id(self._view.tree)
        if not aid:
            self._warn(tr("common.notice"), tr("accounts.warn.select_account"))
            return
        if not messagebox.askyesno(tr("accounts.confirm.delete_title"), tr("accounts.confirm.delete_msg")):
            return
        try:
            self._svc.delete_account(aid)
            self.refresh()
        except Exception:
            logger.exception("accounts.delete_failed")
            self._err(tr("common.error"), tr("accounts.error.delete_failed"))
