{
    'name': 'Owners\' Equity Management',
    'version': '1.0.0',
    'category': 'Accounting',
    'summary': 'Manage Owners\' Equity with Capital Contributions, Withdrawals, and Profit/Loss Allocation',
    'description': '''
        This module provides comprehensive management of Owners' Equity including:
        - Equity ownership tracking per partner and company
        - Capital contributions and withdrawals
        - Profit and loss allocation
        - Retained earnings management
        - Full integration with Odoo's accounting system
    ''',
    'author': 'Senior Odoo Architect',
    'depends': ['account', 'base', 'mail'],
    'data': [
        'security/ir.model.access.csv',
        'security/equity_security.xml',
        'views/partner_views.xml',
        'views/equity_ownership_views.xml',
        'views/equity_ownership_master_views.xml',
        'views/company_views.xml',

        'views/equity_transaction_main_views.xml',
        'views/equity_asset_contribution_views.xml',
        'views/equity_drawing_transaction_views.xml',
        'views/equity_allocation_views.xml',
        'views/equity_drawing_close_views.xml',
        'views/type_store_views.xml',
        # Equity transaction report actions must be loaded before menu
        'reports/report_action.xml',
        # 'reports/equity_transaction_report.xml',
        'reports/equity_transaction_report_pdf.xml',
        'views/menu.xml',
        'data/account_data.xml',
    ],
    'demo': [
    ],
    "assets": {
        'web.assets_backend': [
            # 'cw_equity_management/static/src/equity_transaction_dashboard.js',
            # 'cw_equity_management/static/src/equity_transaction_dashboard.xml',
            'cw_equity_management/static/src/equity_transaction_dashboard_js.js',
            'cw_equity_management/static/src/equity_transaction_dashboard_js.xml',
            'cw_equity_management/static/src/equity_transaction_dashboard.css',
        ],
    },
    'installable': True,
    'auto_install': False,
    'application': True,
    'license': 'LGPL-3',
}
