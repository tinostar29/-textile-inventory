import io
from datetime import datetime
from database import get_db
from stock_service import get_raw_yarn_stock_summary, get_finished_goods_summary, round_kg, round_curr
import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter

from reportlab.lib.pagesizes import letter, landscape, A4
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors

# Style constants for openpyxl
HEADER_FILL = PatternFill(start_color="1E293B", end_color="1E293B", fill_type="solid") # Slate 800
HEADER_FONT = Font(name="Arial", size=11, bold=True, color="FFFFFF")
TITLE_FONT = Font(name="Arial", size=14, bold=True, color="0F172A")
SUBTITLE_FONT = Font(name="Arial", size=10, italic=True, color="64748B")
DATA_FONT = Font(name="Arial", size=10)
TOTAL_FONT = Font(name="Arial", size=10, bold=True)
TOTAL_FILL = PatternFill(start_color="F1F5F9", end_color="F1F5F9", fill_type="solid")

THIN_BORDER = Border(
    left=Side(style='thin', color='E2E8F0'),
    right=Side(style='thin', color='E2E8F0'),
    top=Side(style='thin', color='E2E8F0'),
    bottom=Side(style='thin', color='E2E8F0')
)

def style_excel_sheet(ws, title, subtitle, headers, data, totals=None, number_formats=None):
    # Title
    ws.append([title])
    ws.merge_cells(start_row=1, start_column=1, end_row=1, end_column=len(headers))
    ws.cell(row=1, column=1).font = TITLE_FONT
    ws.cell(row=1, column=1).alignment = Alignment(horizontal="left", vertical="center")
    
    # Subtitle / Generated At
    ws.append([f"{subtitle} | Generated on {datetime.now().strftime('%d-%b-%Y %I:%M %p')}"])
    ws.merge_cells(start_row=2, start_column=1, end_row=2, end_column=len(headers))
    ws.cell(row=2, column=1).font = SUBTITLE_FONT
    ws.append([]) # Empty row

    # Headers
    header_row_idx = 4
    ws.append(headers)
    for col_idx in range(1, len(headers) + 1):
        cell = ws.cell(row=header_row_idx, column=col_idx)
        cell.fill = HEADER_FILL
        cell.font = HEADER_FONT
        cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
        cell.border = THIN_BORDER
    ws.row_dimensions[header_row_idx].height = 28

    # Data Rows
    current_row = header_row_idx + 1
    for row in data:
        ws.append(row)
        for col_idx in range(1, len(headers) + 1):
            cell = ws.cell(row=current_row, column=col_idx)
            cell.font = DATA_FONT
            cell.border = THIN_BORDER
            
            # Align numbers right, text left
            val = cell.value
            if isinstance(val, (int, float)):
                cell.alignment = Alignment(horizontal="right", vertical="center")
                if number_formats and col_idx - 1 in number_formats:
                    cell.number_format = number_formats[col_idx - 1]
            else:
                cell.alignment = Alignment(horizontal="left", vertical="center")
        current_row += 1

    # Total row if provided
    if totals:
        ws.append(totals)
        for col_idx in range(1, len(headers) + 1):
            cell = ws.cell(row=current_row, column=col_idx)
            cell.fill = TOTAL_FILL
            cell.font = TOTAL_FONT
            cell.border = THIN_BORDER
            val = cell.value
            if isinstance(val, (int, float)):
                cell.alignment = Alignment(horizontal="right", vertical="center")
                if number_formats and col_idx - 1 in number_formats:
                    cell.number_format = number_formats[col_idx - 1]
            else:
                cell.alignment = Alignment(horizontal="left", vertical="center")
        current_row += 1

    # Auto-adjust column widths
    for col in ws.columns:
        max_len = 0
        col_letter = get_column_letter(col[0].column)
        for cell in col:
            # Skip merged title row
            if cell.row in (1, 2):
                continue
            val_str = str(cell.value or '')
            if len(val_str) > max_len:
                max_len = len(val_str)
        ws.column_dimensions[col_letter].width = max(max_len + 4, 14)

def export_raw_yarn_stock_excel():
    stocks = get_raw_yarn_stock_summary()
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Raw Yarn Stock"

    headers = ["Yarn Type / Count", "Yarn Colour", "Batches", "Total Purchased (KG)", "Used in Prod (KG)", "Available Stock (KG)", "Avg Price/KG (₹)", "Status", "Last Purchase"]
    data = []
    tot_purchased = 0.0
    tot_used = 0.0
    tot_avail = 0.0

    for s in stocks:
        tot_purchased += s['purchased_kg']
        tot_used += s['used_kg']
        tot_avail += s['remaining_kg']
        data.append([
            s['yarn_type'],
            s['yarn_colour'],
            s['purchase_count'],
            s['purchased_kg'],
            s['used_kg'],
            s['remaining_kg'],
            s['avg_price_per_kg'],
            s['status'],
            s['last_purchase_date'] or '-'
        ])

    totals = ["TOTALS", "", "", tot_purchased, tot_used, tot_avail, "", "", ""]
    num_formats = {3: '#,##0.000 "KG"', 4: '#,##0.000 "KG"', 5: '#,##0.000 "KG"', 6: '₹#,##0.00'}

    style_excel_sheet(ws, "Raw Yarn Inventory Stock Report", "Current Live Raw Yarn Balances", headers, data, totals, num_formats)

    stream = io.BytesIO()
    wb.save(stream)
    stream.seek(0)
    return stream

def export_finished_goods_excel(product_type=None):
    stocks = get_finished_goods_summary(product_type=product_type)
    wb = openpyxl.Workbook()
    ws = wb.active
    title = f"{product_type} Stock" if product_type else "Finished Goods Stock"
    ws.title = title[:30]

    headers = ["Product Type", "Colour", "Batches", "Total Produced (KG)", "Total Sold (KG)", "Available Stock (KG)", "Status", "Last Produced"]
    data = []
    tot_produced = 0.0
    tot_sold = 0.0
    tot_avail = 0.0

    for s in stocks:
        tot_produced += s['produced_kg']
        tot_sold += s['sold_kg']
        tot_avail += s['available_kg']
        data.append([
            s['product_type'],
            s['colour'],
            s['batch_count'],
            s['produced_kg'],
            s['sold_kg'],
            s['available_kg'],
            s['status'],
            s['last_produced_date'] or '-'
        ])

    totals = ["TOTALS", "", "", tot_produced, tot_sold, tot_avail, "", ""]
    num_formats = {3: '#,##0.000 "KG"', 4: '#,##0.000 "KG"', 5: '#,##0.000 "KG"'}

    style_excel_sheet(ws, f"{title} Report", "Tape, Rope & Tipping Finished Goods Balance", headers, data, totals, num_formats)

    stream = io.BytesIO()
    wb.save(stream)
    stream.seek(0)
    return stream

def export_purchases_excel(start_date=None, end_date=None):
    conn = get_db()
    cur = conn.cursor()
    query = """
        SELECT p.purchase_date, p.invoice_number, s.name as supplier_name, p.yarn_type, p.yarn_colour, 
               p.bags_cones, p.weight_kg, p.price_per_kg, p.total_amount, p.status, p.notes
        FROM yarn_purchases p
        LEFT JOIN suppliers s ON p.supplier_id = s.id
        WHERE 1=1
    """
    params = []
    if start_date:
        query += " AND p.purchase_date >= ?"
        params.append(start_date)
    if end_date:
        query += " AND p.purchase_date <= ?"
        params.append(end_date)
    query += " ORDER BY p.purchase_date DESC, p.id DESC"

    cur.execute(query, params)
    rows = cur.fetchall()
    conn.close()

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Purchases"

    headers = ["Date", "Invoice #", "Supplier", "Yarn Type", "Colour", "Bags/Cones", "Weight (KG)", "Price/KG (₹)", "Total Amount (₹)", "Status", "Notes"]
    data = []
    tot_kg = 0.0
    tot_amt = 0.0

    for r in rows:
        if r['status'] == 'ACTIVE':
            tot_kg += r['weight_kg']
            tot_amt += r['total_amount']
        data.append([
            r['purchase_date'],
            r['invoice_number'] or '-',
            r['supplier_name'] or '-',
            r['yarn_type'],
            r['yarn_colour'],
            r['bags_cones'],
            round_kg(r['weight_kg']),
            round_curr(r['price_per_kg']),
            round_curr(r['total_amount']),
            r['status'],
            r['notes'] or ''
        ])

    totals = ["TOTALS (Active)", "", "", "", "", "", tot_kg, "", tot_amt, "", ""]
    num_formats = {6: '#,##0.000 "KG"', 7: '₹#,##0.00', 8: '₹#,##0.00'}

    style_excel_sheet(ws, "Yarn Purchases History", "Detailed log of yarn purchases", headers, data, totals, num_formats)

    stream = io.BytesIO()
    wb.save(stream)
    stream.seek(0)
    return stream

def export_production_excel(start_date=None, end_date=None):
    conn = get_db()
    cur = conn.cursor()
    query = """
        SELECT p.batch_number, p.production_date, p.machine_name, p.operator_name,
               p.input_yarn_type, p.input_yarn_colour, p.input_weight_kg,
               (SELECT GROUP_CONCAT(product_type || ': ' || ROUND(weight_kg, 2) || ' KG', '; ') FROM production_items WHERE production_id = p.id) as finished_breakdown,
               p.total_finished_weight_kg, p.wastage_weight_kg,
               ROUND((p.wastage_weight_kg / p.input_weight_kg) * 100, 2) as waste_pct,
               p.status, p.notes
        FROM productions p
        WHERE 1=1
    """
    params = []
    if start_date:
        query += " AND p.production_date >= ?"
        params.append(start_date)
    if end_date:
        query += " AND p.production_date <= ?"
        params.append(end_date)
    query += " ORDER BY p.production_date DESC, p.id DESC"

    cur.execute(query, params)
    rows = cur.fetchall()
    conn.close()

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Production Runs"

    headers = ["Batch #", "Date", "Machine", "Operator", "Input Yarn", "Colour", "Input (KG)", "Finished Products", "Finished (KG)", "Wastage (KG)", "Waste %", "Status"]
    data = []
    tot_input = 0.0
    tot_finished = 0.0
    tot_waste = 0.0

    for r in rows:
        if r['status'] == 'ACTIVE':
            tot_input += r['input_weight_kg']
            tot_finished += r['total_finished_weight_kg']
            tot_waste += r['wastage_weight_kg']
        data.append([
            r['batch_number'],
            r['production_date'],
            r['machine_name'],
            r['operator_name'] or '-',
            r['input_yarn_type'],
            r['input_yarn_colour'],
            round_kg(r['input_weight_kg']),
            r['finished_breakdown'] or '-',
            round_kg(r['total_finished_weight_kg']),
            round_kg(r['wastage_weight_kg']),
            f"{r['waste_pct']}%" if r['waste_pct'] is not None else '-',
            r['status']
        ])

    totals = ["TOTALS (Active)", "", "", "", "", "", tot_input, "", tot_finished, tot_waste, "", ""]
    num_formats = {6: '#,##0.000 "KG"', 8: '#,##0.000 "KG"', 9: '#,##0.000 "KG"'}

    style_excel_sheet(ws, "Production & Twisting Report", "Batch-wise conversion and wastage tracking", headers, data, totals, num_formats)

    stream = io.BytesIO()
    wb.save(stream)
    stream.seek(0)
    return stream

def export_sales_excel(start_date=None, end_date=None):
    conn = get_db()
    cur = conn.cursor()
    query = """
        SELECT s.sale_date, s.invoice_number, c.name as customer_name, s.product_type, s.product_colour,
               s.quantity_kg, s.price_per_kg, s.total_amount, s.payment_status, s.paid_amount, s.balance_amount,
               s.status, s.notes
        FROM sales s
        LEFT JOIN customers c ON s.customer_id = c.id
        WHERE 1=1
    """
    params = []
    if start_date:
        query += " AND s.sale_date >= ?"
        params.append(start_date)
    if end_date:
        query += " AND s.sale_date <= ?"
        params.append(end_date)
    query += " ORDER BY s.sale_date DESC, s.id DESC"

    cur.execute(query, params)
    rows = cur.fetchall()
    conn.close()

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Sales"

    headers = ["Date", "Invoice #", "Customer", "Product", "Colour", "Qty (KG)", "Price/KG (₹)", "Total (₹)", "Payment Status", "Paid (₹)", "Balance (₹)", "Status"]
    data = []
    tot_qty = 0.0
    tot_val = 0.0
    tot_paid = 0.0
    tot_bal = 0.0

    for r in rows:
        if r['status'] == 'ACTIVE':
            tot_qty += r['quantity_kg']
            tot_val += r['total_amount']
            tot_paid += r['paid_amount']
            tot_bal += r['balance_amount']
        data.append([
            r['sale_date'],
            r['invoice_number'],
            r['customer_name'] or '-',
            r['product_type'],
            r['product_colour'],
            round_kg(r['quantity_kg']),
            round_curr(r['price_per_kg']),
            round_curr(r['total_amount']),
            r['payment_status'],
            round_curr(r['paid_amount']),
            round_curr(r['balance_amount']),
            r['status']
        ])

    totals = ["TOTALS (Active)", "", "", "", "", tot_qty, "", tot_val, "", tot_paid, tot_bal, ""]
    num_formats = {5: '#,##0.000 "KG"', 6: '₹#,##0.00', 7: '₹#,##0.00', 9: '₹#,##0.00', 10: '₹#,##0.00'}

    style_excel_sheet(ws, "Finished Goods Sales Report", "Sales of Tape, Rope & Tipping to Garment Manufacturers", headers, data, totals, num_formats)

    stream = io.BytesIO()
    wb.save(stream)
    stream.seek(0)
    return stream

# --- PDF Generation with ReportLab ---

def export_generic_pdf(title, subtitle, headers, data, column_widths=None):
    stream = io.BytesIO()
    doc = SimpleDocTemplate(
        stream,
        pagesize=landscape(A4),
        leftMargin=24,
        rightMargin=24,
        topMargin=24,
        bottomMargin=24
    )

    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        'RepTitle',
        parent=styles['Heading1'],
        fontName='Helvetica-Bold',
        fontSize=15,
        textColor=colors.HexColor('#0F172A'),
        spaceAfter=4
    )
    sub_style = ParagraphStyle(
        'RepSub',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=9,
        textColor=colors.HexColor('#64748B'),
        spaceAfter=12
    )
    cell_style = ParagraphStyle(
        'RepCell',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=8,
        textColor=colors.HexColor('#1E293B'),
        leading=10
    )
    head_style = ParagraphStyle(
        'RepHead',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=8,
        textColor=colors.white,
        leading=10
    )

    story = []
    story.append(Paragraph(f"<b>TEXTILE MANUFACTURING SYSTEM</b> - {title}", title_style))
    story.append(Paragraph(f"{subtitle} | Generated: {datetime.now().strftime('%d-%b-%Y %I:%M %p')}", sub_style))

    table_data = []
    # Header row
    table_data.append([Paragraph(str(h), head_style) for h in headers])

    for row in data:
        table_data.append([Paragraph(str(cell), cell_style) for cell in row])

    t = Table(table_data, colWidths=column_widths, repeatRows=1)
    t.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1E293B')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 6),
        ('TOPPADDING', (0, 0), (-1, 0), 6),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#F8FAFC')]),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#E2E8F0')),
    ]))

    story.append(t)
    doc.build(story)
    stream.seek(0)
    return stream
