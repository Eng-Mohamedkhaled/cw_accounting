# -*- coding: utf-8 -*-
from odoo import api, fields, models
import re


class ResCompany(models.Model):
    _inherit = 'res.company'

    _CW_DEFAULT_CODES = {
        "cw_base_code_asset_receivable": "1100",
        "cw_base_code_asset_cash": "1000",
        "cw_base_code_asset_current": "1200",
        "cw_base_code_asset_non_current": "1300",
        "cw_base_code_asset_prepayments": "1400",
        "cw_base_code_asset_fixed": "1500",
        "cw_base_code_liability_payable": "2100",
        "cw_base_code_liability_credit_card": "2200",
        "cw_base_code_liability_current": "2300",
        "cw_base_code_liability_non_current": "2400",
        "cw_base_code_equity": "3000",
        "cw_base_code_equity_unaffected": "3100",
        "cw_base_code_income": "4000",
        "cw_base_code_income_other": "4100",
        "cw_base_code_expense": "5000",
        "cw_base_code_expense_other": "5100",
        "cw_base_code_expense_depreciation": "5200",
        "cw_base_code_expense_direct_cost": "5300",
        "cw_base_code_off_balance": "9000",
    }

    cw_base_code_asset_receivable = fields.Char(string="Asset Receivable", default="1100")
    cw_base_code_asset_cash = fields.Char(string="Asset Cash", default="1000")
    cw_base_code_asset_current = fields.Char(string="Asset Current", default="1200")
    cw_base_code_asset_non_current = fields.Char(string="Asset Non-Current", default="1300")
    cw_base_code_asset_prepayments = fields.Char(string="Asset Prepayments", default="1400")
    cw_base_code_asset_fixed = fields.Char(string="Asset Fixed", default="1500")
    cw_base_code_liability_payable = fields.Char(string="Liability Payable", default="2100")
    cw_base_code_liability_credit_card = fields.Char(string="Liability Credit Card", default="2200")
    cw_base_code_liability_current = fields.Char(string="Liability Current", default="2300")
    cw_base_code_liability_non_current = fields.Char(string="Liability Non-Current", default="2400")
    cw_base_code_equity = fields.Char(string="Equity", default="3000")
    cw_base_code_equity_unaffected = fields.Char(string="Equity Unaffected", default="3100")
    cw_base_code_income = fields.Char(string="Income", default="4000")
    cw_base_code_income_other = fields.Char(string="Income Other", default="4100")
    cw_base_code_expense = fields.Char(string="Expense", default="5000")
    cw_base_code_expense_other = fields.Char(string="Expense Other", default="5100")
    cw_base_code_expense_depreciation = fields.Char(string="Expense Depreciation", default="5200")
    cw_base_code_expense_direct_cost = fields.Char(string="Expense Direct Cost", default="5300")
    cw_base_code_off_balance = fields.Char(string="Off Balance", default="9000")

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

        for account_type, base_code in base_codes.items():
            if not base_code:
                continue

            accounts = Account.search([('account_type', '=', account_type), ('company_id', '=', self.id)])
            accounts = accounts.sorted(lambda a: (a.code or "", a.name or ""))

            for idx, account in enumerate(accounts):
                new_code = self._cw_build_code(base_code, idx)
                if new_code:
                    account.code = new_code

        return True

    def action_reset_cw_account_code_defaults(self):
        self.ensure_one()
        self.write(self._CW_DEFAULT_CODES)
        return True
