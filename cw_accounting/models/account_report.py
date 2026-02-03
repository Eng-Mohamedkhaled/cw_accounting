# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
import logging

_logger = logging.getLogger(__name__)

class CWAccountReport(models.Model):
    _name = 'cw.account.report'
    _description = 'CW Account Report Model'

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