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
        transaction_type = data.get('transaction_type') or self.env.context.get('transaction_type')
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

        # Add transaction type filter if specified
        if transaction_type and transaction_type != 'all':
            domain.append(('transaction_type', '=', transaction_type))

        # Get equity transactions within the date range (and optionally filtered by partner and transaction type)
        transactions = self.env['equity.transaction'].search(domain)

        # Prepare transaction data
        transaction_data = []
        # Get actual journal entries from equity and drawing accounts
        actual_entries = []

        # Get company's shared equity and drawing accounts
        company_record = self.env['res.company'].browse(company_id)
        equity_account = company_record.equity_shared_account_id
        drawing_account = company_record.drawing_shared_account_id

        account_ids = []
        if equity_account:
            account_ids.append(equity_account.id)
        if drawing_account:
            account_ids.append(drawing_account.id)

        if account_ids:
            # Query account move lines for the equity/drawing accounts within the date range
            query = """
                SELECT aml.id, aml.date, aml.name, aml.debit, aml.credit, aml.balance,
                       aml.partner_id, aml.ref, rp.name as partner_name,
                       am.name as move_name, am.state as move_state,
                       aa.name as account_name, aa.id as account_id,
                       am.id as move_id
                FROM account_move_line aml
                JOIN account_move am ON aml.move_id = am.id
                JOIN res_partner rp ON aml.partner_id = rp.id
                JOIN account_account aa ON aml.account_id = aa.id
                WHERE aml.account_id IN %s
                  AND aml.date >= %s
                  AND aml.date <= %s
                  AND aml.company_id = %s
                  AND am.state = 'posted'
            """

            # Add partner filter if specified
            params = [tuple(account_ids), date_from, date_to, company_id]
            if partner_id:
                query += " AND aml.partner_id = %s"
                params.append(partner_id)

            # Add transaction type filter if specified
            if transaction_type and transaction_type != 'all':
                if transaction_type == 'contribution' and equity_account:
                    query += " AND aml.account_id = %s"
                    params.append(equity_account.id)
                elif transaction_type == 'withdrawal' and drawing_account:
                    query += " AND aml.account_id = %s"
                    params.append(drawing_account.id)

            query += " ORDER BY aml.date, aml.id"

            self.env.cr.execute(query, params)
            results = self.env.cr.dictfetchall()

            for result in results:
                # Determine transaction type based on account
                transaction_type_result = 'other'
                if equity_account and result['account_id'] == equity_account.id:
                    transaction_type_result = 'contribution'
                elif drawing_account and result['account_id'] == drawing_account.id:
                    transaction_type_result = 'withdrawal'

                # Determine amount based on debit/credit
                raw_amount = result['debit'] - result['credit']

                # Adjust sign based on account type for proper interpretation
                # For equity account: debits are reductions (negative), credits are increases (positive)
                # For drawing account: debits are increases in drawings (negative impact on equity), credits are reductions (positive impact)
                if result['account_id'] == equity_account.id:
                    # Equity account: credits increase equity (positive), debits decrease equity (negative)
                    adjusted_sign = raw_amount  # Keep original sign
                elif result['account_id'] == drawing_account.id:
                    # Drawing account: debits increase drawings (negative impact on equity), credits decrease drawings (positive impact)
                    # So we invert the sign to represent the impact on equity
                    adjusted_sign = -raw_amount
                else:
                    # Other accounts: keep original sign
                    adjusted_sign = raw_amount

                actual_entries.append({
                    'id': result['id'],
                    'name': result['name'] or result['move_name'],
                    'transaction_type': transaction_type_result,
                    'partner_name': result['partner_name'],
                    'amount': abs(raw_amount),  # Always show absolute value in the amount column
                    'sign': adjusted_sign,  # Use adjusted sign for dashboard interpretation
                    'date': result['date'],
                    'state': result['move_state'],
                    'reference': result['ref'] or result['move_name'],
                    'description': result['move_name'] or result['name'] or result['ref'] or '',  # Show move number first
                    'account_name': result['account_name'],
                    'move_id': result.get('move_id'),  # Add move ID for linking to journal entry
                })

        # Combine manual transactions with actual journal entries
        transaction_data = actual_entries  # Using only actual journal entries as requested

        # If we want to include manual equity transactions as well, uncomment the following:
        # transaction_data = []
        # for transaction in transactions:
        #     transaction_data.append({
        #         'id': transaction.id,
        #         'name': transaction.name,
        #         'transaction_type': transaction.transaction_type,
        #         'partner_name': transaction.partner_id.name,
        #         'amount': transaction.amount,
        #         'date': transaction.date,
        #         'state': transaction.state,
        #         'reference': transaction.reference or '',
        #         'description': transaction.description or '',
        #         'source': 'manual'  # Mark as manual transaction
        #     })
        #
        # # Add actual journal entries
        # transaction_data.extend(actual_entries)
        #
        # # Sort by date and ID
        # transaction_data.sort(key=lambda x: (x['date'], x['id']))

        # Calculate equity information for each partner based on actual account move lines
        equity_info = []
        partners_to_show = []

        # Get company's shared equity and drawing accounts
        company_record = self.env['res.company'].browse(company_id)
        equity_account = company_record.equity_shared_account_id
        drawing_account = company_record.drawing_shared_account_id

        if not equity_account and not drawing_account:
            # If no equity or drawing accounts are configured, skip equity calculation
            equity_info = []
        else:
            # Determine which partners to include in equity calculation
            if partner_id:
                # If a specific partner is selected, only show that partner's equity
                partners_to_show = [int(partner_id)]
            else:
                # Otherwise, show equity for all equity owners
                all_equity_partners = self.env['res.partner'].search([('is_equity_owner', '=', True)])
                partners_to_show = [p.id for p in all_equity_partners]

            for partner_id_calc in partners_to_show:
                partner = self.env['res.partner'].browse(partner_id_calc)

                # Calculate balance from equity account (contributions increase equity)
                equity_balance = 0.0
                if equity_account:
                    # Query account move lines for this partner in the equity account
                    print(f"DEBUG: Calculating equity balance for partner {partner_id_calc}, account {equity_account.id}")
                    self.env.cr.execute("""
                        SELECT SUM(aml.balance)
                        FROM account_move_line aml
                        JOIN account_move am ON aml.move_id = am.id
                        WHERE aml.partner_id = %s
                          AND aml.account_id = %s
                          AND aml.date <= %s
                          AND aml.company_id = %s
                          AND am.state = 'posted'
                    """, (partner_id_calc, equity_account.id, date_to, company_id))

                    result = self.env.cr.fetchone()[0]
                    equity_balance = result or 0.0
                    print(f"DEBUG: Equity balance result: {equity_balance}")

                # Calculate balance from drawing account (withdrawals decrease equity)
                drawing_balance = 0.0
                if drawing_account:
                    # Query account move lines for this partner in the drawing account
                    self.env.cr.execute("""
                        SELECT SUM(aml.balance)
                        FROM account_move_line aml
                        JOIN account_move am ON aml.move_id = am.id
                        WHERE aml.partner_id = %s
                          AND aml.account_id = %s
                          AND aml.date <= %s
                          AND aml.company_id = %s
                          AND am.state = 'posted'
                    """, (partner_id_calc, drawing_account.id, date_to, company_id))

                    result = self.env.cr.fetchone()[0]
                    drawing_balance = result or 0.0

                # Calculate current equity: Equity account balance - Drawing account balance
                # (drawing account typically has credit balances that reduce equity)
                current_equity = -(equity_balance + drawing_balance)

                equity_info.append({
                    'partner_name': partner.name,
                    'partner_id': partner.id,
                    'equity_account_balance': -(equity_balance),
                    'drawing_account_balance': drawing_balance,
                    'current_equity': current_equity,
                })

        # Get company information
        company = self.env['res.company'].browse(company_id)

        return {
            'transactions': transaction_data,
            'equity_info': equity_info,
            'date_from': date_from,
            'date_to': date_to,
            'partner_id': partner_id,
            'transaction_type': transaction_type,
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