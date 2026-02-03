# -*- coding: utf-8 -*-
{
    'name': "CW - Accounting",
    'summary': "Inherits from custom_account_move_line to extend accounting functionalities.",
    'description': """
        This module depends on custom_account_move_line to build upon its features.
    """,
    'author': "Code Wave Agency",
    'website': "https://code-wave-agency.com",
    'category': 'Accounting',
    'version': '1.0',
    'depends': ['custom_account_move_line','account'],
    'data': [
        'security/ir.model.access.csv',
        'views/account_move_views.xml',
        'views/account_report_view.xml',
    ],
    "license": "LGPL-3",
    'installable': True,
    'application': False,
    'auto_install': False,
}
