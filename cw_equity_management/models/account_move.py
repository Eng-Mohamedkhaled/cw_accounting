# -*- coding: utf-8 -*-
from odoo import fields, models


class AccountMove(models.Model):
    _inherit = 'account.move'
    
    # Link to equity transaction for tracking purposes
    equity_transaction_id = fields.Many2one(
        'equity.transaction',
        string='Equity Transaction',
        help='Link to the equity transaction that generated this journal entry'
    )
    
    # Link to equity allocation for tracking purposes
    equity_allocation_id = fields.Many2one(
        'equity.allocation',
        string='Equity Allocation',
        help='Link to the equity allocation that generated this journal entry'
    )

    # Link to equity drawing close transaction
    drawing_close_id = fields.Many2one(
        'equity.drawing.close',
        string='Drawing Close Transaction',
        copy=False,
        help='Link to the drawing close transaction that generated this journal entry'
    )