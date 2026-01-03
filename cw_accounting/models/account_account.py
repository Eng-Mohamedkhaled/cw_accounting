# -*- coding: utf-8 -*-
from odoo import api, fields, models, _, Command
import logging

_logger = logging.getLogger(__name__)

class AccountAccount(models.Model):
    _inherit = 'account.account'

    @api.onchange('account_type')
    def _onchange_account_type_generate_code(self):
        if self.account_type:
            max_numeric_code = 0
            # Search for all accounts of the current type within the current company context.
            # 'self.search' automatically filters by the current company.
            existing_accounts = self.search([('account_type', '=', self.account_type)])

            for acc in existing_accounts:
                if acc.code and acc.code.isdigit():
                    max_numeric_code = max(max_numeric_code, int(acc.code))
            
            # Use the highest found numeric code as a starting point.
            # If no numeric codes exist, start from '0' so _search_new_account_code increments to '1'.
            start_code = str(max_numeric_code) if max_numeric_code > 0 else '0'
            
            # Use the native Odoo helper to find the next available code.
            # Pass an empty cache to allow the method to return the start_code if it's available.
            new_code = self._search_new_account_code(start_code, cache={})
            self.code = new_code
        else:
            self.code = False # Clear code if account type is cleared


    @api.model
    def create(self, vals_list):
        return super(AccountAccount, self).create(vals_list)