# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
import logging
import re

_logger = logging.getLogger(__name__)

class CWAccountReport(models.Model):
    _name = 'cw.account.report'
    _description = 'CW Account Report Model'
    
    name="accounts codes"
    company_id = fields.Many2one(
        'res.company',
        required=True,
        default=lambda self: self.env.company,
    )

    # Default base codes per account type. Users can override per company.
    base_code_asset_receivable = fields.Char(string="Asset Receivable", default="1100")
    base_code_asset_cash = fields.Char(string="Asset Cash", default="1000")
    base_code_asset_current = fields.Char(string="Asset Current", default="1200")
    base_code_asset_non_current = fields.Char(string="Asset Non-Current", default="1300")
    base_code_asset_prepayments = fields.Char(string="Asset Prepayments", default="1400")
    base_code_asset_fixed = fields.Char(string="Asset Fixed", default="1500")
    base_code_liability_payable = fields.Char(string="Liability Payable", default="2100")
    base_code_liability_credit_card = fields.Char(string="Liability Credit Card", default="2200")
    base_code_liability_current = fields.Char(string="Liability Current", default="2300")
    base_code_liability_non_current = fields.Char(string="Liability Non-Current", default="2400")
    base_code_equity = fields.Char(string="Equity", default="3000")
    base_code_equity_unaffected = fields.Char(string="Equity Unaffected", default="3100")
    base_code_income = fields.Char(string="Income", default="4000")
    base_code_income_other = fields.Char(string="Income Other", default="4100")
    base_code_expense = fields.Char(string="Expense", default="5000")
    base_code_expense_other = fields.Char(string="Expense Other", default="5100")
    base_code_expense_depreciation = fields.Char(string="Expense Depreciation", default="5200")
    base_code_expense_direct_cost = fields.Char(string="Expense Direct Cost", default="5300")
    base_code_off_balance = fields.Char(string="Off Balance", default="9000")

    _sql_constraints = [
        ('cw_account_report_company_unique', 'unique(company_id)', 'Only one record per company is allowed.'),
    ]

    def _get_base_codes(self):
        self.ensure_one()
        return {
            "asset_receivable": self.base_code_asset_receivable,
            "asset_cash": self.base_code_asset_cash,
            "asset_current": self.base_code_asset_current,
            "asset_non_current": self.base_code_asset_non_current,
            "asset_prepayments": self.base_code_asset_prepayments,
            "asset_fixed": self.base_code_asset_fixed,
            "liability_payable": self.base_code_liability_payable,
            "liability_credit_card": self.base_code_liability_credit_card,
            "liability_current": self.base_code_liability_current,
            "liability_non_current": self.base_code_liability_non_current,
            "equity": self.base_code_equity,
            "equity_unaffected": self.base_code_equity_unaffected,
            "income": self.base_code_income,
            "income_other": self.base_code_income_other,
            "expense": self.base_code_expense,
            "expense_other": self.base_code_expense_other,
            "expense_depreciation": self.base_code_expense_depreciation,
            "expense_direct_cost": self.base_code_expense_direct_cost,
            "off_balance": self.base_code_off_balance,
        }

    def _build_code(self, prefix, idx):
        """
        Build a code from a string prefix.
        - If prefix is all digits: increment with zero-padding.
        - If prefix ends with digits: increment the numeric suffix with zero-padding.
        - Otherwise: append a simple counter to avoid duplicates.
        """
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

    def apply_account_codes(self):
        """
        Update all account codes based on the base codes per account type.
        Codes are assigned sequentially starting from each base code.
        """
        self.ensure_one()
        base_codes = self._get_base_codes()

        Account = self.env['account.account'].with_company(self.company_id)
        for account_type, base_code in base_codes.items():
            if not base_code:
                continue

            accounts = Account.search([('account_type', '=', account_type), ('company_id', '=', self.company_id.id)])
            accounts = accounts.sorted(lambda a: (a.code or "", a.name or ""))

            for idx, account in enumerate(accounts):
                new_code = self._build_code(base_code, idx)
                if new_code:
                    account.code = new_code

        return True

    def read_accounts(self):
        """
        Public method to read accounts by type and print them in an organized way.
        This can be called from the UI.
        """
        # Get all accounts
        all_accounts = self.env['account.account'].search([])

        # Group accounts by type
        accounts_by_type = {}
        for account in all_accounts:
            account_type = account.account_type
            if account_type not in accounts_by_type:
                accounts_by_type[account_type] = []
            accounts_by_type[account_type].append(account)

        # Print organized information
        print("=" * 50)
        print("ACCOUNTS ORGANIZED BY TYPE:")
        print("=" * 50)

        for account_type, accounts in accounts_by_type.items():
            print(f"\nTYPE: {account_type}")
            print("-" * 30)
            for account in accounts:
                print(f"  - Name: {account.name}, Code: {account.code}")
                if account.name == "cash":
                    account.write({'code': '12312888'})  # Properly update the code
        print("\n" + "=" * 50)

        # Just print to console, no UI return needed for now
        return True
