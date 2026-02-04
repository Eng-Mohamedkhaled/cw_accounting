# -*- coding: utf-8 -*-
from odoo import models, api
from datetime import datetime


class EquityTransactionReport(models.AbstractModel):
    _name = 'report.cw_equity_management.equity_transaction_report'
    _description = 'Equity Transaction Report'

    @api.model
    def _get_report_values(self, docids, data=None):
        data = data or {}

        date_from = data.get('date_from') or self.env.context.get('date_from')
        date_to = data.get('date_to') or self.env.context.get('date_to')
        partner_id = data.get('partner_id') or self.env.context.get('partner_id')
        company_id = data.get('company_id') or self.env.context.get('company_id') or self.env.company.id

        from odoo import fields
        if not date_from:
            date_from = fields.Date.context_today(self)
        if not date_to:
            date_to = fields.Date.context_today(self)

        # Ensure dates are date objects
        if isinstance(date_from, str):
            date_from = fields.Date.from_string(date_from)
        if isinstance(date_to, str):
            date_to = fields.Date.from_string(date_to)

        # Get current language for translation
        current_lang = self.env.context.get('lang', 'en_US')

        # Build domain for equity transactions
        domain = [
            ('date', '>=', date_from),
            ('date', '<=', date_to),
            ('company_id', '=', company_id),
            ('state', 'in', ['posted', 'draft']),  # Include both posted and draft transactions
        ]

        # Add partner filter if specified
        if partner_id:
            domain.append(('partner_id', '=', int(partner_id)))

        # Get equity transactions within the date range (and optionally filtered by partner)
        transactions = self.env['equity.transaction'].search(domain)

        # Prepare transaction data
        transaction_data = []
        for transaction in transactions:
            transaction_data.append({
                'id': transaction.id,
                'name': transaction.name,
                'transaction_type': transaction.transaction_type,
                'partner_name': transaction.partner_id.name,
                'amount': transaction.amount,
                'date': transaction.date,
                'state': transaction.state,
                'reference': transaction.reference or '',
                'description': transaction.description or '',
            })

        # Get company information
        company = self.env['res.company'].browse(company_id)

        return {
            'transactions': transaction_data,
            'date_from': date_from,
            'date_to': date_to,
            'partner_id': partner_id,
            'res_company': company,
            'company': company,
        }


class EquityTransactionReportPdf(models.AbstractModel):
    _name = 'report.cw_equity_management.equity_transaction_report_pdf'
    _description = 'Equity Transaction Report (PDF Proxy)'

    @api.model
    def _get_report_values(self, docids, data=None):
        # This report uses the same data as the HTML report.
        # We call the original report's data-gathering method.
        result = self.env['report.cw_equity_management.equity_transaction_report']._get_report_values(docids, data)

        # Add company information to the result to ensure it's available in the template
        company_id = data and data.get('company_id') or self.env.context.get('company_id') or self.env.company.id
        company = self.env['res.company'].browse(company_id)

        result.update({
            'res_company': company,
            'company': company,  # Also add as 'company' for compatibility with web.external_layout
        })

        return result