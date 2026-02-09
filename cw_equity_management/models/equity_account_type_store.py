from odoo import models, fields


#we add what we want to res company
class ResCompany(models.Model):
    _inherit = 'res.company'

    allowed_account_type_ids = fields.Many2many(
        'account.account.type',
        string='Allowed Account Types'
    )


# we use it in res.config.settings
class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    allowed_account_type_ids = fields.Many2many(
        'account.account.type',
        related='company_id.allowed_account_type_ids',
        readonly=False
    )


# Custom settings model for equity management
class EquityManagementConfigSettings(models.TransientModel):
    _name = 'equity.management.config.settings'
    _description = 'Equity Management Configuration Settings'
    _inherit = 'res.config.settings'

    allowed_account_type_ids = fields.Many2many(
        'account.account.type',
        related='company_id.allowed_account_type_ids',
        readonly=False,
        string="Allowed Account Types"
    )