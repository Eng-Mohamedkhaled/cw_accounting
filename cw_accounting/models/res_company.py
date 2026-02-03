# -*- coding: utf-8 -*-
from odoo import api, fields, models
import re


class ResCompany(models.Model):
    _inherit = 'res.company'

    _CW_DEFAULT_CODES = {
        "cw_base_code_asset_cash": "101000",
        "cw_base_code_asset_receivable": "102000",
        "cw_base_code_asset_current": "103000",
        "cw_base_code_asset_non_current": "110000",
        "cw_base_code_asset_prepayments": "104000",
        "cw_base_code_asset_fixed": "105000",
        "cw_base_code_liability_payable": "201000",
        "cw_base_code_liability_credit_card": "202000",
        "cw_base_code_liability_current": "203000",
        "cw_base_code_liability_non_current": "204000",
        "cw_base_code_equity": "320000",
        "cw_base_code_equity_unaffected": "310000",
        "cw_base_code_income": "400000",
        "cw_base_code_income_other": "410000",
        "cw_base_code_expense": "500000",
        "cw_base_code_expense_other": "510000",
        "cw_base_code_expense_depreciation": "520000",
        "cw_base_code_expense_direct_cost": "530000",
        "cw_base_code_off_balance": "900000",
    }

    cw_base_code_asset_cash = fields.Char(string="Asset Cash", default="101000")
    cw_base_code_asset_receivable = fields.Char(string="Asset Receivable", default="102000")
    cw_base_code_asset_current = fields.Char(string="Asset Current", default="103000")
    cw_base_code_asset_non_current = fields.Char(string="Asset Non-Current", default="110000")
    cw_base_code_asset_prepayments = fields.Char(string="Asset Prepayments", default="104000")
    cw_base_code_asset_fixed = fields.Char(string="Asset Fixed", default="105000")
    cw_base_code_liability_payable = fields.Char(string="Liability Payable", default="201000")
    cw_base_code_liability_credit_card = fields.Char(string="Liability Credit Card", default="202000")
    cw_base_code_liability_current = fields.Char(string="Liability Current", default="203000")
    cw_base_code_liability_non_current = fields.Char(string="Liability Non-Current", default="204000")
    cw_base_code_equity = fields.Char(string="Equity", default="320000")
    cw_base_code_equity_unaffected = fields.Char(string="Equity Unaffected", default="310000")
    cw_base_code_income = fields.Char(string="Income", default="400000")
    cw_base_code_income_other = fields.Char(string="Income Other", default="410000")
    cw_base_code_expense = fields.Char(string="Expense", default="500000")
    cw_base_code_expense_other = fields.Char(string="Expense Other", default="510000")
    cw_base_code_expense_depreciation = fields.Char(string="Expense Depreciation", default="520000")
    cw_base_code_expense_direct_cost = fields.Char(string="Expense Direct Cost", default="530000")
    cw_base_code_off_balance = fields.Char(string="Off Balance", default="900000")

    def _cw_build_code(self, prefix, idx):
        prefix = (prefix or "").strip()
        if not prefix:
            return False

        if prefix.isdigit():
            width = len(prefix)
            return f"{int(prefix) + idx:0{width}d}"

        match = re.match(r"^(.*?)(\d+)$", prefix)
        if match:
            head, digits = match.groups()
            width = len(digits)
            return f"{head}{int(digits) + idx:0{width}d}"

        return f"{prefix}{idx + 1}"

    def _cw_base_codes(self):
        self.ensure_one()
        return {
            "asset_receivable": self.cw_base_code_asset_receivable,
            "asset_cash": self.cw_base_code_asset_cash,
            "asset_current": self.cw_base_code_asset_current,
            "asset_non_current": self.cw_base_code_asset_non_current,
            "asset_prepayments": self.cw_base_code_asset_prepayments,
            "asset_fixed": self.cw_base_code_asset_fixed,
            "liability_payable": self.cw_base_code_liability_payable,
            "liability_credit_card": self.cw_base_code_liability_credit_card,
            "liability_current": self.cw_base_code_liability_current,
            "liability_non_current": self.cw_base_code_liability_non_current,
            "equity": self.cw_base_code_equity,
            "equity_unaffected": self.cw_base_code_equity_unaffected,
            "income": self.cw_base_code_income,
            "income_other": self.cw_base_code_income_other,
            "expense": self.cw_base_code_expense,
            "expense_other": self.cw_base_code_expense_other,
            "expense_depreciation": self.cw_base_code_expense_depreciation,
            "expense_direct_cost": self.cw_base_code_expense_direct_cost,
            "off_balance": self.cw_base_code_off_balance,
        }

    def action_apply_cw_account_codes(self):
        self.ensure_one()
        base_codes = self._cw_base_codes()
        Account = self.env['account.account'].with_company(self)

        # print(f"CW Account Codes: applying prefixes for company={self.name} (id={self.id})")

        for account_type, base_code in base_codes.items():
            if not base_code:
                # print(f"CW Account Codes: skip account_type={account_type} (empty prefix)")
                continue

            accounts = Account.search([('account_type', '=', account_type), ('company_ids', 'in', self.id)])
            accounts = accounts.sorted(lambda a: (a.code or "", a.name or ""))

            # print(
            #     f"CW Account Codes: account_type={account_type} "
            #     f"prefix={base_code} accounts_found={len(accounts)}"
            # )

            for idx, account in enumerate(accounts):
                new_code = self._cw_build_code(base_code, idx)
                if new_code:
                    # old_code = account.code or ""
                    # print(
                    #     f"CW Account Codes: {account.display_name} "
                    #     f"(id={account.id}) {old_code} -> {new_code}"
                    # )
                    account.code = new_code

        return True

    def action_reset_cw_account_code_defaults(self):
        self.ensure_one()
        self.write(self._CW_DEFAULT_CODES)
        return True
