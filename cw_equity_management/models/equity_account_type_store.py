from odoo import models, fields


#we add what we want to res company
class ResCompany(models.Model):
    _inherit = 'res.company'

    # Selection field to control which method to use
    liquidity_configuration_method = fields.Selection([
        ('account_type', 'Configure by Account Type'),
        ('specific_account', 'Configure by Specific Accounts'),
    ], string='Liquidity Configuration Method', default='account_type',
       help="Choose how to configure liquidity: by account types or by specific accounts.")
    
    # Fields for account type method
    liquid_asset_types = fields.Many2many(
        'account.account.type',
        'res_company_liquid_asset_type_rel',
        'company_id', 'account_type_id',
        string='Liquid Asset Types',
        domain=[('type', 'in', ['asset_receivable', 'asset_cash', 'asset_current'])],
        help="Select which asset account types should be considered as liquid assets for withdrawal calculations. These typically include cash, receivables, and other highly liquid assets."
    )
    
    liability_types = fields.Many2many(
        'account.account.type',
        'res_company_liability_type_rel',
        'company_id', 'account_type_id',
        string='Liability Types',
        domain=[('type', 'in', ['liability_payable', 'liability_current'])],
        help="Select which liability account types should be included in liquidity calculations. These may be subtracted from liquid assets to determine net available funds."
    )
    
    # Fields for account method
    liquid_asset_accounts = fields.Many2many(
        'account.account',
        'res_company_liquid_asset_account_rel',
        'company_id', 'account_id',
        string='Specific Liquid Asset Accounts',
        domain="[('company_id', '=', current_company_id), ('account_type', 'in', ['asset_cash', 'asset_current', 'asset_receivable'])]",
        help="Select specific accounts that should be considered as liquid assets for withdrawal calculations."
    )
    
    liability_accounts = fields.Many2many(
        'account.account',
        'res_company_liability_account_rel',
        'company_id', 'account_id',
        string='Specific Liability Accounts',
        domain="[('company_id', '=', current_company_id), ('account_type', 'in', ['liability_payable', 'liability_current'])]",
        help="Select specific liability accounts to include in liquidity calculations."
    )
    


# we use it in res.config.settings
class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    liquidity_configuration_method = fields.Selection(
        related='company_id.liquidity_configuration_method',
        readonly=False,
        help="Choose how to configure liquidity: by account types or by specific accounts."
    )
    
    liquid_asset_types = fields.Many2many(
        'account.account.type',
        related='company_id.liquid_asset_types',
        readonly=False,
        help="Select which asset account types should be considered as liquid assets for withdrawal calculations. These typically include cash, receivables, and other highly liquid assets."
    )
    
    liability_types = fields.Many2many(
        'account.account.type',
        related='company_id.liability_types',
        readonly=False,
        help="Select which liability account types should be included in liquidity calculations. These may be subtracted from liquid assets to determine net available funds."
    )
    
    liquid_asset_accounts = fields.Many2many(
        'account.account',
        related='company_id.liquid_asset_accounts',
        readonly=False,
        help="Select specific accounts that should be considered as liquid assets for withdrawal calculations."
    )
    
    liability_accounts = fields.Many2many(
        'account.account',
        related='company_id.liability_accounts',
        readonly=False,
        help="Select specific liability accounts to include in liquidity calculations."
    )
    


# Custom settings model for equity management
class EquityManagementConfigSettings(models.TransientModel):
    _name = 'equity.management.config.settings'
    _description = 'Equity Management Configuration Settings'
    _inherit = 'res.config.settings'

    liquidity_configuration_method = fields.Selection(
        related='company_id.liquidity_configuration_method',
        readonly=False,
        string="Liquidity Configuration Method",
        help="Choose how to configure liquidity: by account types or by specific accounts."
    )
    
    liquid_asset_types = fields.Many2many(
        'account.account.type',
        related='company_id.liquid_asset_types',
        readonly=False,
        string="Liquid Asset Types",
        help="Select which asset account types should be considered as liquid assets for withdrawal calculations. These typically include cash, receivables, and other highly liquid assets."
    )
    
    liability_types = fields.Many2many(
        'account.account.type',
        related='company_id.liability_types',
        readonly=False,
        string="Liability Types",
        help="Select which liability account types should be included in liquidity calculations. These may be subtracted from liquid assets to determine net available funds."
    )
    
    liquid_asset_accounts = fields.Many2many(
        'account.account',
        related='company_id.liquid_asset_accounts',
        readonly=False,
        string="Specific Liquid Asset Accounts",
        help="Select specific accounts that should be considered as liquid assets for withdrawal calculations."
    )
    
    liability_accounts = fields.Many2many(
        'account.account',
        related='company_id.liability_accounts',
        readonly=False,
        string="Specific Liability Accounts",
        help="Select specific liability accounts to include in liquidity calculations."
    )
    
