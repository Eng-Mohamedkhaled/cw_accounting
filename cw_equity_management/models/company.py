# -*- coding: utf-8 -*-
from odoo import api, fields, models


class ResCompany(models.Model):
    _inherit = 'res.company'

    # Shared equity account for all owners in this company
    equity_shared_account_id = fields.Many2one(
        'account.account',
        string='Shared Equity Account',
        domain="[('company_ids', 'in', id), ('account_type', '=', 'equity')]",
        help='Shared equity account for all owners in this company'
    )

    # Shared drawing account for all owners in this company
    drawing_shared_account_id = fields.Many2one(
        'account.account',
        string='Shared Drawing Account',
        domain="[('company_ids', 'in', id), ('account_type', '=', 'equity')]",
        help='Shared drawing account for all owners in this company'
    )