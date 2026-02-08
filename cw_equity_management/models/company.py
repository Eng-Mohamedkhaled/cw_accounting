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

    def _ensure_equity_accounts_exist(self):
        """
        Ensures that the required equity accounts exist for the company.
        Creates them if they don't exist.
        """
        for company in self:
            # Check if shared equity account exists, create if not
            if not company.equity_shared_account_id:
                equity_account = self.env['account.account'].search([
                    ('name', '=', 'Capital'),
                    ('company_ids', 'in', company.id),
                    ('account_type', '=', 'equity')
                ], limit=1)
                
                if not equity_account:
                    # Find the equity account type
                    equity_account_type = self.env['account.account.type'].search([('name', '=', 'Equity')], limit=1)
                    if not equity_account_type:
                        # If equity account type doesn't exist, create a generic one or use a default
                        equity_account_type = self.env['account.account.type'].search([('type', '=', 'equity')], limit=1)
                    
                    equity_account = self.env['account.account'].create({
                        'name': 'Capital',
                        'code': self.env['ir.sequence'].next_by_code('account.account') or 'CAP001',
                        'account_type': 'equity',
                        'company_ids': [(4, company.id)],
                        'reconcile': False,
                    })
                
                company.equity_shared_account_id = equity_account.id
            
            # Check if shared drawing account exists, create if not
            if not company.drawing_shared_account_id:
                drawing_account = self.env['account.account'].search([
                    ('name', '=', 'Drawing'),
                    ('company_ids', 'in', company.id),
                    ('account_type', '=', 'equity')
                ], limit=1)
                
                if not drawing_account:
                    # Find the equity account type
                    equity_account_type = self.env['account.account.type'].search([('name', '=', 'Equity')], limit=1)
                    if not equity_account_type:
                        # If equity account type doesn't exist, create a generic one or use a default
                        equity_account_type = self.env['account.account.type'].search([('type', '=', 'equity')], limit=1)
                    
                    drawing_account = self.env['account.account'].create({
                        'name': 'Drawing',
                        'code': self.env['ir.sequence'].next_by_code('account.account') or 'DRW001',
                        'account_type': 'equity',
                        'company_ids': [(4, company.id)],
                        'reconcile': False,
                    })
                
                company.drawing_shared_account_id = drawing_account.id