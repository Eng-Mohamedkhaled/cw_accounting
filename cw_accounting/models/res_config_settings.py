# -*- coding: utf-8 -*-
from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    cw_base_code_asset_receivable = fields.Char(related='company_id.cw_base_code_asset_receivable', readonly=False)
    cw_base_code_asset_cash = fields.Char(related='company_id.cw_base_code_asset_cash', readonly=False)
    cw_base_code_asset_current = fields.Char(related='company_id.cw_base_code_asset_current', readonly=False)
    cw_base_code_asset_non_current = fields.Char(related='company_id.cw_base_code_asset_non_current', readonly=False)
    cw_base_code_asset_prepayments = fields.Char(related='company_id.cw_base_code_asset_prepayments', readonly=False)
    cw_base_code_asset_fixed = fields.Char(related='company_id.cw_base_code_asset_fixed', readonly=False)
    cw_base_code_liability_payable = fields.Char(related='company_id.cw_base_code_liability_payable', readonly=False)
    cw_base_code_liability_credit_card = fields.Char(related='company_id.cw_base_code_liability_credit_card', readonly=False)
    cw_base_code_liability_current = fields.Char(related='company_id.cw_base_code_liability_current', readonly=False)
    cw_base_code_liability_non_current = fields.Char(related='company_id.cw_base_code_liability_non_current', readonly=False)
    cw_base_code_equity = fields.Char(related='company_id.cw_base_code_equity', readonly=False)
    cw_base_code_equity_unaffected = fields.Char(related='company_id.cw_base_code_equity_unaffected', readonly=False)
    cw_base_code_income = fields.Char(related='company_id.cw_base_code_income', readonly=False)
    cw_base_code_income_other = fields.Char(related='company_id.cw_base_code_income_other', readonly=False)
    cw_base_code_expense = fields.Char(related='company_id.cw_base_code_expense', readonly=False)
    cw_base_code_expense_other = fields.Char(related='company_id.cw_base_code_expense_other', readonly=False)
    cw_base_code_expense_depreciation = fields.Char(related='company_id.cw_base_code_expense_depreciation', readonly=False)
    cw_base_code_expense_direct_cost = fields.Char(related='company_id.cw_base_code_expense_direct_cost', readonly=False)
    cw_base_code_off_balance = fields.Char(related='company_id.cw_base_code_off_balance', readonly=False)

    def action_apply_account_codes(self):
        self.ensure_one()
        return self.company_id.action_apply_cw_account_codes()

    def action_reset_account_code_defaults(self):
        self.ensure_one()
        return self.company_id.action_reset_cw_account_code_defaults()
