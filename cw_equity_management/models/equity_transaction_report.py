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
                    'description': f"{result['move_name']} - {result['ref']}" if result['move_name'] and result['ref'] else result['move_name'] or result['ref'] or result['name'] or '',  # Show move number - reference
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

                # Calculate profit/loss allocation for this partner
                pl_allocation = 0.0
                # Get active ownership record for this partner during the period
                ownership = self.env['equity.ownership'].search([
                    ('partner_id', '=', partner_id_calc),
                    ('company_id', '=', company_id),
                    ('date_from', '<=', date_to),
                    '|', ('date_to', '=', False), ('date_to', '>=', date_from)
                ], limit=1)

                if ownership:
                    # Calculate P&L allocation using the same algorithm as in equity_allocation.py
                    # Call the existing report to get the net profit/loss
                    report_model = self.env['report.custom_account_move_line.profit_loss_report']

                    # Prepare the data for the report
                    date_from_str = str(date_from)
                    date_to_str = str(date_to)

                    report_data = {
                        'date_from': date_from_str,
                        'date_to': date_to_str,
                        'company_id': company_id
                    }

                    try:
                        # Get the report values
                        report_values = report_model._get_report_values([], data=report_data)

                        # Extract the net profit from the report values
                        lines = report_values.get('lines', [])

                        # Find the net profit line (the one with 'Net Profit' in the name)
                        net_profit_line = None
                        for line in lines:  # Look through all lines to find the Net Profit line
                            if 'Net Profit' in str(line.get('account_name', '')) or 'net profit' in str(line.get('account_name', '')).lower():
                                net_profit_line = line
                                break

                        if net_profit_line:
                            original_net_profit = net_profit_line.get('balance', 0.0)

                            # Calculate the sum of balances for equity_unaffected accounts during the period
                            equity_unaffected_accounts = self.env['account.account'].search([
                                ('company_ids', 'in', company_id),
                                ('account_type', '=', 'equity_unaffected')
                            ])

                            total_equity_unaffected_change = 0.0
                            if equity_unaffected_accounts:
                                # Query the account move lines for equity unaffected accounts during the period
                                self.env.cr.execute("""
                                    SELECT SUM(aml.balance) FROM account_move_line aml
                                    JOIN account_account aa ON aml.account_id = aa.id
                                    JOIN account_move am ON aml.move_id = am.id
                                    WHERE aa.id IN %s
                                    AND aml.date >= %s
                                    AND aml.date <= %s
                                    AND aml.company_id = %s
                                    AND am.state = 'posted'
                                """, (tuple(equity_unaffected_accounts.ids), date_from, date_to, company_id))

                                result = self.env.cr.fetchone()[0]
                                total_equity_unaffected_change = result or 0.0

                            adjusted_result = original_net_profit - total_equity_unaffected_change
                            
                            # Calculate this partner's share based on their ownership percentage
                            pl_allocation = adjusted_result * (ownership.percentage / 100.0)
                        else:
                            # If we can't find the net profit line, calculate it manually from the lines
                            # Find all income and expense lines
                            income_total = 0.0
                            expense_total = 0.0

                            for line in lines:
                                if line.get('key') in ['income', 'other_income']:
                                    income_value = line.get('balance', 0.0)
                                    income_total += income_value
                                elif line.get('key') in ['cogs', 'opex', 'other_exp', 'depr']:
                                    expense_value = line.get('balance', 0.0)
                                    expense_total += expense_value

                            # Calculate the sum of balances for equity_unaffected accounts during the period
                            equity_unaffected_accounts = self.env['account.account'].search([
                                ('company_ids', 'in', company_id),
                                ('account_type', '=', 'equity_unaffected')
                            ])

                            total_equity_unaffected_change = 0.0
                            if equity_unaffected_accounts:
                                # Query the account move lines for equity unaffected accounts during the period
                                self.env.cr.execute("""
                                    SELECT SUM(aml.balance) FROM account_move_line aml
                                    JOIN account_account aa ON aml.account_id = aa.id
                                    JOIN account_move am ON aml.move_id = am.id
                                    WHERE aa.id IN %s
                                    AND aml.date >= %s
                                    AND aml.date <= %s
                                    AND aml.company_id = %s
                                    AND am.state = 'posted'
                                """, (tuple(equity_unaffected_accounts.ids), date_from, date_to, company_id))

                                result = self.env.cr.fetchone()[0]
                                total_equity_unaffected_change = result or 0.0

                            manual_result = income_total - expense_total - total_equity_unaffected_change
                            # Calculate this partner's share based on their ownership percentage
                            pl_allocation = manual_result * (ownership.percentage / 100.0)
                    except Exception as e:
                        print(f"DEBUG: Error calculating P&L allocation: {e}")
                        pl_allocation = 0.0

                # Calculate current equity after P&L allocation
                current_equity_after_pl = current_equity + pl_allocation

                # Calculate available for withdrawal considering individual equity position and company liquidity
                # Get liquid asset accounts for the company based on configuration
                company_record = self.env['res.company'].browse(company_id)
                
                # Use configured liquid asset types if using account type method, otherwise use specific accounts
                if company_record.liquidity_configuration_method == 'account_type':
                    # Get liquid asset types from company configuration
                    liquid_asset_types = company_record.liquid_asset_types.mapped('type')
                    liquid_asset_accounts = self.env['account.account'].search([
                        ('company_ids', 'in', company_id),
                        ('account_type', 'in', liquid_asset_types)
                    ])
                else:  # specific_account method
                    # Use specific liquid asset accounts from company configuration
                    liquid_asset_accounts = company_record.liquid_asset_accounts

                print(f"DEBUG: Company ID: {company_id}")
                print(f"DEBUG: Configuration Method: {company_record.liquidity_configuration_method}")
                
                # Calculate total liquid assets for the company
                total_liquid_assets = 0.0
                if liquid_asset_accounts:
                    print(f"DEBUG: Liquid Asset Accounts: {[acc.code + ' - ' + acc.name for acc in liquid_asset_accounts]}")
                    print(f"DEBUG: Liquid Asset Account IDs: {liquid_asset_accounts.ids}")
                    
                    # Query account move lines for liquid asset accounts (without partner restriction)
                    # This includes all liquid assets in the company
                    self.env.cr.execute("""
                        SELECT SUM(aml.balance)
                        FROM account_move_line aml
                        JOIN account_move am ON aml.move_id = am.id
                        JOIN account_account aa ON aml.account_id = aa.id
                        WHERE aa.id IN %s
                          AND aml.date <= %s
                          AND aml.company_id = %s
                          AND am.state = 'posted'
                    """, (tuple(liquid_asset_accounts.ids), date_to, company_id))

                    result = self.env.cr.fetchone()[0]
                    total_liquid_assets = result or 0.0
                    print(f"DEBUG: Total Liquid Assets before liability adjustment: {total_liquid_assets}")
                else:
                    print(f"DEBUG: No liquid asset accounts found for company {company_id}")

                # Handle liability accounts if configured
                total_liability_assets = 0.0
                if company_record.liquidity_configuration_method == 'account_type':
                    liability_types = company_record.liability_types.mapped('type')
                    print(f"DEBUG: Liability Types: {liability_types}")
                    if liability_types:
                        liability_accounts = self.env['account.account'].search([
                            ('company_ids', 'in', company_id),
                            ('account_type', 'in', liability_types)
                        ])
                        print(f"DEBUG: Liability Accounts: {[acc.code + ' - ' + acc.name for acc in liability_accounts]}")
                        if liability_accounts:
                            # Query account move lines for liability accounts
                            self.env.cr.execute("""
                                SELECT SUM(aml.balance)
                                FROM account_move_line aml
                                JOIN account_move am ON aml.move_id = am.id
                                JOIN account_account aa ON aml.account_id = aa.id
                                WHERE aa.id IN %s
                                  AND aml.date <= %s
                                  AND aml.company_id = %s
                                  AND am.state = 'posted'
                            """, (tuple(liability_accounts.ids), date_to, company_id))

                            result = self.env.cr.fetchone()[0]
                            total_liability_assets = result or 0.0
                            print(f"DEBUG: Total Liability Assets: {total_liability_assets}")
                        else:
                            print(f"DEBUG: No liability accounts found for company {company_id}")
                    else:
                        print(f"DEBUG: No liability types configured for company {company_id}")
                else:  # specific_account method
                    liability_accounts = company_record.liability_accounts
                    print(f"DEBUG: Specific Liability Accounts: {[acc.code + ' - ' + acc.name for acc in liability_accounts]}")
                    if liability_accounts:
                        # Query account move lines for specific liability accounts
                        self.env.cr.execute("""
                            SELECT SUM(aml.balance)
                            FROM account_move_line aml
                            JOIN account_move am ON aml.move_id = am.id
                            JOIN account_account aa ON aml.account_id = aa.id
                            WHERE aa.id IN %s
                              AND aml.date <= %s
                              AND aml.company_id = %s
                              AND am.state = 'posted'
                        """, (tuple(liability_accounts.ids), date_to, company_id))

                        result = self.env.cr.fetchone()[0]
                        total_liability_assets = result or 0.0
                        print(f"DEBUG: Total Liability Assets: {total_liability_assets}")
                    else:
                        print(f"DEBUG: No specific liability accounts configured for company {company_id}")

                # Adjust total liquid assets based on liability configuration
                # If liabilities should be considered, they may reduce available liquidity
                original_liquid_assets = total_liquid_assets
                total_liquid_assets = total_liquid_assets + total_liability_assets
                print(f"DEBUG: Original Liquid Assets: {original_liquid_assets}, Liability Assets: {total_liability_assets}, Final Liquid Assets: {total_liquid_assets}")

                # Calculate the individual partner's equity position
                # This considers their specific contributions and withdrawals
                partner_equity_position = current_equity_after_pl  # This already includes their contributions, drawings, and P&L allocation

                print(f"DEBUG: Partner {partner.name} calculations:")
                print(f"DEBUG: - Equity Account Balance: {-(equity_balance)}")
                print(f"DEBUG: - Drawing Account Balance: {drawing_balance}")
                print(f"DEBUG: - Current Equity: {current_equity}")
                print(f"DEBUG: - P&L Allocation: {pl_allocation}")
                print(f"DEBUG: - Current Equity After P&L: {current_equity_after_pl}")
                print(f"DEBUG: - Partner Equity Position: {partner_equity_position}")
                print(f"DEBUG: - Total Company Liquid Assets: {total_liquid_assets}")
                
                # Available for withdrawal is the minimum of:
                # 1. Their individual equity position (can't withdraw more than they own)
                # 2. Available company liquid assets (can't withdraw more than company has)

                #If total is negative means that libilites more than assets
                #We make zero for report visual
                total_liquid_assets = max(0, total_liquid_assets)
                available_for_withdrawal = min(max(0, partner_equity_position), total_liquid_assets)
                print(f"DEBUG: - Available for Withdrawal: {available_for_withdrawal}")

                equity_info.append({
                    'partner_name': partner.name,
                    'partner_id': partner.id,
                    'equity_account_balance': -(equity_balance),
                    'drawing_account_balance': drawing_balance,
                    'current_equity': current_equity,
                    'pl_allocation': pl_allocation,  # P&L allocation for this partner
                    'current_equity_after_pl': current_equity_after_pl,  # Current equity after P&L allocation
                    'available_for_withdrawal': available_for_withdrawal,  # Available for withdrawal based on individual equity position and company liquidity
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