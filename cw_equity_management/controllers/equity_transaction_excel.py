import io
from odoo import http
from odoo.http import request
import xlsxwriter
from datetime import datetime


class EquityTransactionExcelController(http.Controller):

    @http.route('/report/equity_transaction/excel', type='http', auth='user')
    def equity_transaction_excel(self, date_from=None, date_to=None, partner_id=None, transaction_type=None, company_id=None):

        report = request.env['report.cw_equity_management.equity_transaction_report']
        data = report._get_report_values(
            None,
            data={
                'date_from': date_from if date_from and date_from != 'False' else None,
                'date_to': date_to if date_to and date_to != 'False' else None,
                'partner_id': int(partner_id) if partner_id and partner_id != 'None' and partner_id != 'False' else None,
                'transaction_type': transaction_type if transaction_type and transaction_type != 'None' and transaction_type != 'False' else None,
                'company_id': int(company_id) if company_id else request.env.user.company_id.id,
            }
        )

        transactions = data['transactions']

        # 2️⃣ Create in-memory Excel
        output = io.BytesIO()
        workbook = xlsxwriter.Workbook(output, {'in_memory': True})
        sheet = workbook.add_worksheet('Equity Transactions')

        # Define formats with improved styling
        title_format = workbook.add_format({
            'bold': True,
            'font_size': 16,
            'align': 'center',
            'valign': 'vcenter'
        })

        header_format = workbook.add_format({
            'bold': True,
            'bg_color': '#4472C4',
            'font_color': 'white',
            'border': 1,
            'align': 'center',
            'valign': 'vcenter'
        })

        cell_format = workbook.add_format({
            'border': 1,
            'align': 'left'
        })

        currency_format = workbook.add_format({
            'border': 1,
            'num_format': '#,##0.00',
            'align': 'right'
        })

        date_format = workbook.add_format({
            'border': 1,
            'num_format': 'yyyy-mm-dd',
            'align': 'center'
        })

        # Status formats
        draft_format = workbook.add_format({
            'border': 1,
            'font_color': '#888888',
            'align': 'center'
        })

        posted_format = workbook.add_format({
            'border': 1,
            'font_color': '#28a745',
            'bold': True,
            'align': 'center'
        })

        cancelled_format = workbook.add_format({
            'border': 1,
            'font_color': '#dc3545',
            'align': 'center'
        })

        # 3️⃣ Add report title and metadata
        company_name = request.env['res.company'].browse(int(company_id) if company_id else request.env.user.company_id.id).name
        sheet.merge_range('A1:F1', f'Equity Transactions Report - {company_name}', title_format)
        sheet.write('A2', 'Generated on:', cell_format)
        sheet.write('B2', datetime.now().strftime('%Y-%m-%d %H:%M:%S'), cell_format)

        # Add filter information
        filters_applied = []
        if date_from and date_from != 'False':
            filters_applied.append(f'From: {date_from}')
        if date_to and date_to != 'False':
            filters_applied.append(f'To: {date_to}')

        # Headers start at row 3 since filters are at the end
        start_row = 3

        # 4️⃣ Headers
        headers = [
            'Date',
            'Partner',
            'Type',
            'Amount',
            'Status',
            'Description'
        ]

        # Write headers
        for col, header in enumerate(headers):
            sheet.write(start_row, col, header, header_format)

        # Set column widths
        sheet.set_column('A:A', 15)  # Date
        sheet.set_column('B:B', 25)  # Partner
        sheet.set_column('C:C', 15)  # Type
        sheet.set_column('D:D', 15)  # Amount
        sheet.set_column('E:E', 12)  # Status
        sheet.set_column('F:F', 40)  # Description

        row = start_row + 1

        # 5️⃣ Write data rows
        total_amount = 0
        for trans in transactions:
            # Apply appropriate format based on status
            status_format = cell_format  # Default
            if trans['state'] == 'draft':
                status_format = draft_format
            elif trans['state'] == 'posted':
                status_format = posted_format
            elif trans['state'] == 'cancelled':
                status_format = cancelled_format

            sheet.write_datetime(row, 0, datetime.strptime(str(trans['date']), '%Y-%m-%d'), date_format)
            sheet.write(row, 1, trans['partner_name'], cell_format)
            
            # Format transaction type
            trans_type = ''
            if trans['transaction_type'] == 'contribution':
                trans_type = 'Contribution'
            elif trans['transaction_type'] == 'withdrawal':
                trans_type = 'Withdrawal'
            else:
                trans_type = trans['transaction_type']
            sheet.write(row, 2, trans_type, cell_format)
            
            sheet.write(row, 3, trans['amount'], currency_format)
            sheet.write(row, 4, trans['state'].title(), status_format)
            sheet.write(row, 5, trans['description'] or '', cell_format)
            
            total_amount += trans['amount']
            row += 1

        # Add total row
        sheet.write(row, 0, 'Total', cell_format)
        sheet.write(row, 1, '', cell_format)
        sheet.write(row, 2, '', cell_format)
        sheet.write(row, 3, total_amount, currency_format)
        sheet.write(row, 4, '', cell_format)
        sheet.write(row, 5, '', cell_format)

        # Write filters at the end of the report
        if filters_applied:
            row += 2  # Add blank rows before filters
            # Write each filter in a separate column with smaller font
            small_font_format = workbook.add_format({
                'font_size': 9,  # Smaller font size
                'border': 1,
                'align': 'left'
            })
            for col_idx, filter_text in enumerate(filters_applied):
                sheet.write(row, col_idx, filter_text, small_font_format)

        workbook.close()
        output.seek(0)

        # 7️⃣ Return file
        return request.make_response(
            output.read(),
            headers=[
                ('Content-Type',
                 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'),
                ('Content-Disposition',
                 f'attachment; filename=Equity_Transactions_{datetime.now().strftime("%Y%m%d_%H%M%S")}.xlsx')
            ]
        )