# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
import logging

_logger = logging.getLogger(__name__)

class AccountMove(models.Model):
    _inherit = 'account.move'

    # === Journal Entry fields === #
    duplicate_entry_id = fields.Many2one(
        'account.move',
        store=False,
        check_company=True,
        string='Duplicate Entry',
        help="Auto-complete from a previous journal entry.",
        domain="[('company_id', '=', company_id), ('move_type', '=', 'entry'), ('id', '!=', id)]",
    )

    @api.onchange('duplicate_entry_id')
    def _onchange_duplicate_entry(self):
        if self.duplicate_entry_id:
            # Clear existing lines first
            self.line_ids = [(5, 0, 0)]  # Remove all lines
            
            # Copy journal entry lines
            for line in self.duplicate_entry_id.line_ids:
                copied_vals = line.copy_data({
                    'debit': line.debit,
                    'credit': line.credit,
                    'name': line.name,
                    'account_id': line.account_id.id,
                    'partner_id': line.partner_id.id,
                    'analytic_distribution': line.analytic_distribution,
                    'tax_ids': [(6, 0, line.tax_ids.ids)],
                    'tax_tag_ids': [(6, 0, line.tax_tag_ids.ids)],
                    'currency_id': line.currency_id.id,
                    'amount_currency': line.amount_currency,
                })[0]
                
                # Create new line record
                new_line = self.env['account.move.line'].new(copied_vals)
                self.line_ids += new_line

            # Copy other relevant fields
            self.ref = self.duplicate_entry_id.ref
            self.narration = self.duplicate_entry_id.narration
            self.journal_id = self.duplicate_entry_id.journal_id
            self.fiscal_position_id = self.duplicate_entry_id.fiscal_position_id
            self.date = self.duplicate_entry_id.date  # Optionally copy date too

            # Reset the field to prevent reuse
            self.duplicate_entry_id = False