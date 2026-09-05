import io
from datetime import datetime
from typing import Dict, Any, List
import pandas as pd
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter

from reportlab.lib.pagesizes import letter, A4
from reportlab.lib import colors
from reportlab.lib.units import inch
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak, KeepTogether, HRFlowable
)
from reportlab.pdfgen import canvas

from backend.database import get_db_connection
from backend.settlement import calculate_trip_settlement

# Numbered canvas for "Page X of Y" in PDF
class NumberedCanvas(canvas.Canvas):
    def __init__(self, *args, **kwargs):
        super(NumberedCanvas, self).__init__(*args, **kwargs)
        self._saved_page_states = []

    def showPage(self):
        self._saved_page_states.append(dict(self.__dict__))
        self._startPage()

    def save(self):
        num_pages = len(self._saved_page_states)
        for state in self._saved_page_states:
            self.__dict__.update(state)
            self.draw_page_number(num_pages)
            canvas.Canvas.showPage(self)
        canvas.Canvas.save(self)

    def draw_page_number(self, page_count):
        self.saveState()
        self.setFont("Helvetica", 8)
        self.setFillColor(colors.HexColor("#64748B"))
        page_text = f"Page {self._pageNumber} of {page_count}"
        self.drawRightString(A4[0] - 36, 20, page_text)
        self.drawString(36, 20, "Spillter - Travel Group Expense Tracker & Settlement Statement")
        self.restoreState()


def get_trip_full_data(trip_id: int) -> Dict[str, Any]:
    settlement_data = calculate_trip_settlement(trip_id)
    conn = get_db_connection()
    cursor = conn.cursor()

    # Fetch expenses with payer and splits
    cursor.execute("""
        SELECT e.*, m.name as payer_name
        FROM expenses e
        JOIN members m ON e.payer_id = m.id
        WHERE e.trip_id = ?
        ORDER BY e.date ASC, e.id ASC
    """, (trip_id,))
    expense_rows = cursor.fetchall()

    expenses = []
    for exp_row in expense_rows:
        exp = dict(exp_row)
        # Fetch splits for this expense
        cursor.execute("""
            SELECT es.*, m.name as member_name
            FROM expense_splits es
            JOIN members m ON es.member_id = m.id
            WHERE es.expense_id = ?
        """, (exp["id"],))
        splits = [dict(s) for s in cursor.fetchall()]
        exp["splits"] = splits
        expenses.append(exp)

    conn.close()
    settlement_data["expenses"] = expenses
    return settlement_data


def generate_trip_pdf(trip_id: int) -> io.BytesIO:
    data = get_trip_full_data(trip_id)
    trip = data["trip"]
    currency = trip.get("currency", "₹")
    # For PDF, use standard symbols or text representation to avoid encoding issues
    curr_symbol = "Rs. " if currency == "₹" else f"{currency} "

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        leftMargin=36,
        rightMargin=36,
        topMargin=36,
        bottomMargin=36
    )

    styles = getSampleStyleSheet()
    
    # Custom styles
    title_style = ParagraphStyle(
        'DocTitle',
        parent=styles['Heading1'],
        fontName='Helvetica-Bold',
        fontSize=20,
        leading=24,
        textColor=colors.HexColor("#1E1B4B"),
        spaceAfter=4
    )
    subtitle_style = ParagraphStyle(
        'DocSubtitle',
        parent=styles['Normal'],
        fontName='Helvetica-Oblique',
        fontSize=10,
        leading=13,
        textColor=colors.HexColor("#475569"),
        spaceAfter=12
    )
    h2_style = ParagraphStyle(
        'Heading2Custom',
        parent=styles['Heading2'],
        fontName='Helvetica-Bold',
        fontSize=12,
        leading=16,
        textColor=colors.HexColor("#312E81"),
        spaceBefore=14,
        spaceAfter=6
    )
    cell_style = ParagraphStyle(
        'TableCell',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=8.5,
        leading=11,
        textColor=colors.HexColor("#1F2937")
    )
    cell_bold_style = ParagraphStyle(
        'TableCellBold',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=8.5,
        leading=11,
        textColor=colors.HexColor("#1F2937")
    )
    header_cell_style = ParagraphStyle(
        'HeaderCell',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=9,
        leading=12,
        textColor=colors.white
    )

    story = []

    # Title & Header
    # Remove non-ascii emojis for standard PDF font compatibility
    clean_trip_name = trip['name'].encode('ascii', 'ignore').decode().strip() or trip['name']
    clean_desc = (trip.get('description') or '').encode('ascii', 'ignore').decode().strip()

    story.append(Paragraph(f"Trip Expense Statement: {clean_trip_name}", title_style))
    if clean_desc:
        story.append(Paragraph(clean_desc, subtitle_style))
    
    gen_time = datetime.now().strftime("%d %b %Y, %I:%M %p")
    story.append(Paragraph(f"<b>Generated on:</b> {gen_time} | <b>Currency:</b> {trip.get('currency', '₹')}", cell_style))
    story.append(Spacer(1, 10))

    # Summary KPI Table
    kpi_data = [
        [
            Paragraph("<b>Total Trip Expense</b>", cell_style),
            Paragraph("<b>Total Members</b>", cell_style),
            Paragraph("<b>Average / Person</b>", cell_style),
            Paragraph("<b>Total Logged Bills</b>", cell_style)
        ],
        [
            Paragraph(f"<b>{curr_symbol}{data['total_expenses']:,.2f}</b>", ParagraphStyle('Kpi1', parent=cell_style, fontSize=12, textColor=colors.HexColor("#1E1B4B"))),
            Paragraph(f"<b>{data['member_count']} Persons</b>", ParagraphStyle('Kpi2', parent=cell_style, fontSize=12, textColor=colors.HexColor("#1E1B4B"))),
            Paragraph(f"<b>{curr_symbol}{data['average_expense']:,.2f}</b>", ParagraphStyle('Kpi3', parent=cell_style, fontSize=12, textColor=colors.HexColor("#1E1B4B"))),
            Paragraph(f"<b>{len(data['expenses'])} Items</b>", ParagraphStyle('Kpi4', parent=cell_style, fontSize=12, textColor=colors.HexColor("#1E1B4B")))
        ]
    ]
    t_kpi = Table(kpi_data, colWidths=[130, 130, 130, 130])
    t_kpi.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor("#F1F5F9")),
        ('BOX', (0, 0), (-1, -1), 1, colors.HexColor("#CBD5E1")),
        ('INNERGRID', (0, 0), (-1, -1), 0.5, colors.HexColor("#E2E8F0")),
        ('TOPPADDING', (0, 0), (-1, -1), 6),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
        ('LEFTPADDING', (0, 0), (-1, -1), 8),
        ('RIGHTPADDING', (0, 0), (-1, -1), 8),
    ]))
    story.append(t_kpi)
    story.append(Spacer(1, 14))

    # Section: Simplified Settlements ("Who Pays Whom")
    story.append(Paragraph("1. Final Settlement Summary (Who Pays Whom)", h2_style))
    story.append(Paragraph("Debt-minimization algorithm result: settle all group balances in the minimum transactions.", cell_style))
    story.append(Spacer(1, 4))

    if data["settlements"]:
        settle_table_data = [
            [
                Paragraph("<b>From (Payer)</b>", header_cell_style),
                Paragraph("<b>Action</b>", header_cell_style),
                Paragraph("<b>To (Receiver)</b>", header_cell_style),
                Paragraph("<b>Amount to Pay</b>", header_cell_style)
            ]
        ]
        for s in data["settlements"]:
            settle_table_data.append([
                Paragraph(f"<b>{s['from_name']}</b>", cell_style),
                Paragraph("pays ➔", cell_style),
                Paragraph(f"<b>{s['to_name']}</b>", cell_style),
                Paragraph(f"<b>{curr_symbol}{s['amount']:,.2f}</b>", cell_bold_style)
            ])
        t_settle = Table(settle_table_data, colWidths=[150, 80, 150, 140])
        t_settle.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#4F46E5")),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor("#CBD5E1")),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor("#F8FAFC")]),
            ('PADDING', (0, 0), (-1, -1), 5),
        ]))
        story.append(t_settle)
    else:
        story.append(Paragraph("All members are completely settled up.", cell_style))

    if data.get("settlement_history"):
        story.append(Spacer(1, 10))
        story.append(Paragraph("<b>Completed Settlement Payments:</b>", cell_bold_style))
        story.append(Spacer(1, 4))
        comp_data = [
            [
                Paragraph("<b>Date</b>", header_cell_style),
                Paragraph("<b>Payer</b>", header_cell_style),
                Paragraph("<b>Receiver</b>", header_cell_style),
                Paragraph("<b>Amount Paid</b>", header_cell_style)
            ]
        ]
        for sh in data["settlement_history"]:
            comp_data.append([
                Paragraph(sh["date"], cell_style),
                Paragraph(sh["payer_name"], cell_style),
                Paragraph(sh["receiver_name"], cell_style),
                Paragraph(f"<b>{curr_symbol}{float(sh['amount']):,.2f}</b>", cell_bold_style)
            ])
        t_comp = Table(comp_data, colWidths=[90, 150, 150, 130])
        t_comp.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#059669")),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor("#CBD5E1")),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor("#F8FAFC")]),
            ('PADDING', (0, 0), (-1, -1), 4),
        ]))
        story.append(t_comp)

    story.append(Spacer(1, 14))

    # Section: Member Balance Breakdown
    story.append(Paragraph("2. Member Balance Summary", h2_style))
    mem_table_data = [
        [
            Paragraph("<b>Member</b>", header_cell_style),
            Paragraph("<b>Total Paid</b>", header_cell_style),
            Paragraph("<b>Total Share (Owed)</b>", header_cell_style),
            Paragraph("<b>Net Balance</b>", header_cell_style),
            Paragraph("<b>Status</b>", header_cell_style),
        ]
    ]
    for m in data["member_stats"]:
        net = m["net_balance"]
        if net > 0.009:
            status = "Gets Back"
            net_text = f"+{curr_symbol}{abs(net):,.2f}"
            color = colors.HexColor("#065F46") # Emerald dark
        elif net < -0.009:
            status = "Owes"
            net_text = f"-{curr_symbol}{abs(net):,.2f}"
            color = colors.HexColor("#991B1B") # Red dark
        else:
            status = "Settled"
            net_text = f"{curr_symbol}0.00"
            color = colors.HexColor("#475569")

        mem_table_data.append([
            Paragraph(f"<b>{m['name']}</b>", cell_style),
            Paragraph(f"{curr_symbol}{m['total_paid']:,.2f}", cell_style),
            Paragraph(f"{curr_symbol}{m['total_owed']:,.2f}", cell_style),
            Paragraph(f"<b>{net_text}</b>", ParagraphStyle('NetStyle', parent=cell_style, textColor=color)),
            Paragraph(status, ParagraphStyle('StatStyle', parent=cell_style, textColor=color, fontName='Helvetica-Bold')),
        ])

    t_mem = Table(mem_table_data, colWidths=[120, 100, 100, 100, 100])
    t_mem.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#334155")),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor("#CBD5E1")),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor("#F8FAFC")]),
        ('PADDING', (0, 0), (-1, -1), 5),
    ]))
    story.append(t_mem)
    story.append(Spacer(1, 14))

    # Section: Itemized Expenses Log Statement
    story.append(Paragraph("3. Itemized Expense Statement (All Entries)", h2_style))
    exp_table_data = [
        [
            Paragraph("<b>Date</b>", header_cell_style),
            Paragraph("<b>Expense Title</b>", header_cell_style),
            Paragraph("<b>Category</b>", header_cell_style),
            Paragraph("<b>Paid By</b>", header_cell_style),
            Paragraph("<b>Mode</b>", header_cell_style),
            Paragraph("<b>Split Type</b>", header_cell_style),
            Paragraph("<b>Amount</b>", header_cell_style),
        ]
    ]

    for e in data["expenses"]:
        clean_title = e["title"].encode('ascii', 'ignore').decode().strip() or e["title"]
        mode = e.get("payment_mode") or "UPI"
        exp_table_data.append([
            Paragraph(e["date"], cell_style),
            Paragraph(f"<b>{clean_title}</b>", cell_style),
            Paragraph(e["category"], cell_style),
            Paragraph(e["payer_name"], cell_style),
            Paragraph(mode, cell_style),
            Paragraph(e["split_type"].capitalize(), cell_style),
            Paragraph(f"<b>{curr_symbol}{e['amount']:,.2f}</b>", cell_bold_style),
        ])

    t_exp = Table(exp_table_data, colWidths=[55, 125, 65, 75, 65, 60, 75])
    t_exp.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#1E293B")),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor("#CBD5E1")),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor("#F8FAFC")]),
        ('PADDING', (0, 0), (-1, -1), 4.5),
    ]))
    story.append(t_exp)

    # Build PDF
    doc.build(story, canvasmaker=NumberedCanvas)
    buffer.seek(0)
    return buffer


from openpyxl import Workbook

def generate_trip_excel(trip_id: int) -> io.BytesIO:
    data = get_trip_full_data(trip_id)
    trip = data["trip"]
    currency = trip.get("currency", "₹")

    output = io.BytesIO()
    workbook = Workbook()

    # Define Styles
    header_fill = PatternFill(start_color="312E81", end_color="312E81", fill_type="solid")
    header_font = Font(name="Calibri", size=11, bold=True, color="FFFFFF")
    title_font = Font(name="Calibri", size=16, bold=True, color="1E1B4B")
    subtitle_font = Font(name="Calibri", size=11, italic=True, color="475569")
    bold_font = Font(name="Calibri", size=11, bold=True)
    thin_border = Border(
        left=Side(style='thin', color='CBD5E1'),
        right=Side(style='thin', color='CBD5E1'),
        top=Side(style='thin', color='CBD5E1'),
        bottom=Side(style='thin', color='CBD5E1')
    )
    currency_format = f'"{currency}" #,##0.00'

    # --- SHEET 1: Summary & Settlements ---
    ws_summary = workbook.active
    ws_summary.title = "Summary & Settlements"

    ws_summary["A1"] = f"Trip Statement: {trip['name']}"
    ws_summary["A1"].font = title_font
    ws_summary["A2"] = f"{trip.get('description', '')} | Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}"
    ws_summary["A2"].font = subtitle_font

    # Overview Box
    ws_summary["A4"] = "Total Trip Expense"
    ws_summary["B4"] = data["total_expenses"]
    ws_summary["B4"].number_format = currency_format
    ws_summary["B4"].font = bold_font

    ws_summary["A5"] = "Total Members"
    ws_summary["B5"] = data["member_count"]

    ws_summary["A6"] = "Average Expense / Member"
    ws_summary["B6"] = data["average_expense"]
    ws_summary["B6"].number_format = currency_format
    ws_summary["B6"].font = bold_font

    ws_summary["A7"] = "Total Expense Entries"
    ws_summary["B7"] = len(data["expenses"])

    for r in range(4, 8):
        ws_summary[f"A{r}"].font = bold_font
        ws_summary[f"A{r}"].fill = PatternFill(start_color="F1F5F9", end_color="F1F5F9", fill_type="solid")
        ws_summary[f"A{r}"].border = thin_border
        ws_summary[f"B{r}"].border = thin_border

    # Member Balances Table
    ws_summary["A9"] = "MEMBER BALANCE SUMMARY"
    ws_summary["A9"].font = Font(name="Calibri", size=12, bold=True, color="312E81")

    mem_headers = ["Member Name", "Total Paid", "Total Share (Owed)", "Net Balance", "Status"]
    for col_idx, h in enumerate(mem_headers, start=1):
        cell = ws_summary.cell(row=10, column=col_idx, value=h)
        cell.fill = header_fill
        cell.font = header_font
        cell.alignment = Alignment(horizontal="center")
        cell.border = thin_border

    row_idx = 11
    for m in data["member_stats"]:
        ws_summary.cell(row=row_idx, column=1, value=m["name"]).border = thin_border
        
        c_paid = ws_summary.cell(row=row_idx, column=2, value=m["total_paid"])
        c_paid.number_format = currency_format
        c_paid.border = thin_border

        c_owed = ws_summary.cell(row=row_idx, column=3, value=m["total_owed"])
        c_owed.number_format = currency_format
        c_owed.border = thin_border

        c_net = ws_summary.cell(row=row_idx, column=4, value=m["net_balance"])
        c_net.number_format = currency_format
        c_net.border = thin_border
        c_net.font = bold_font

        status_val = "Gets Back" if m["net_balance"] > 0.009 else ("Owes" if m["net_balance"] < -0.009 else "Settled")
        c_stat = ws_summary.cell(row=row_idx, column=5, value=status_val)
        c_stat.border = thin_border
        c_stat.alignment = Alignment(horizontal="center")
        if status_val == "Gets Back":
            c_stat.font = Font(name="Calibri", color="047857", bold=True)
        elif status_val == "Owes":
            c_stat.font = Font(name="Calibri", color="B91C1C", bold=True)
        row_idx += 1

    # Settlements Table ("Who Pays Whom")
    row_idx += 2
    ws_summary.cell(row=row_idx, column=1, value="FINAL SETTLEMENTS (WHO PAYS WHOM)").font = Font(name="Calibri", size=12, bold=True, color="312E81")
    row_idx += 1

    set_headers = ["Payer (Debtor)", "Action", "Receiver (Creditor)", "Amount to Pay"]
    for col_idx, h in enumerate(set_headers, start=1):
        cell = ws_summary.cell(row=row_idx, column=col_idx, value=h)
        cell.fill = PatternFill(start_color="4338CA", end_color="4338CA", fill_type="solid")
        cell.font = header_font
        cell.alignment = Alignment(horizontal="center")
        cell.border = thin_border
    row_idx += 1

    if data["settlements"]:
        for s in data["settlements"]:
            ws_summary.cell(row=row_idx, column=1, value=s["from_name"]).border = thin_border
            act = ws_summary.cell(row=row_idx, column=2, value="pays ➔")
            act.alignment = Alignment(horizontal="center")
            act.border = thin_border
            ws_summary.cell(row=row_idx, column=3, value=s["to_name"]).border = thin_border
            
            amt_cell = ws_summary.cell(row=row_idx, column=4, value=s["amount"])
            amt_cell.number_format = currency_format
            amt_cell.font = bold_font
            amt_cell.border = thin_border
            row_idx += 1
    else:
        ws_summary.cell(row=row_idx, column=1, value="All expenses are completely settled!").border = thin_border

    # Adjust summary column widths
    for col in ws_summary.columns:
        max_len = max(len(str(cell.value or '')) for cell in col)
        col_letter = get_column_letter(col[0].column)
        ws_summary.column_dimensions[col_letter].width = max(max_len + 3, 14)

    # --- SHEET 2: Detailed Expense Statement ---
    ws_expenses = workbook.create_sheet(title="All Expenses Statement")
    ws_expenses["A1"] = f"Detailed Expense Statement - {trip['name']}"
    ws_expenses["A1"].font = title_font

    exp_headers = ["ID", "Date", "Title", "Category", "Paid By", "Payment Mode", "Split Type", "Amount", "Split Breakdown", "Notes"]
    for col_idx, h in enumerate(exp_headers, start=1):
        cell = ws_expenses.cell(row=3, column=col_idx, value=h)
        cell.fill = header_fill
        cell.font = header_font
        cell.alignment = Alignment(horizontal="center")
        cell.border = thin_border

    row_idx = 4
    for e in data["expenses"]:
        splits_summary = ", ".join([f"{s['member_name']} ({currency}{s['share_amount']:,.2f})" for s in e["splits"]])
        ws_expenses.cell(row=row_idx, column=1, value=e["id"]).border = thin_border
        ws_expenses.cell(row=row_idx, column=2, value=e["date"]).border = thin_border
        ws_expenses.cell(row=row_idx, column=3, value=e["title"]).border = thin_border
        ws_expenses.cell(row=row_idx, column=4, value=e["category"]).border = thin_border
        ws_expenses.cell(row=row_idx, column=5, value=e["payer_name"]).border = thin_border
        ws_expenses.cell(row=row_idx, column=6, value=e.get("payment_mode") or "UPI").border = thin_border
        ws_expenses.cell(row=row_idx, column=7, value=e["split_type"].capitalize()).border = thin_border

        amt_cell = ws_expenses.cell(row=row_idx, column=8, value=e["amount"])
        amt_cell.number_format = currency_format
        amt_cell.font = bold_font
        amt_cell.border = thin_border

        ws_expenses.cell(row=row_idx, column=9, value=splits_summary).border = thin_border
        ws_expenses.cell(row=row_idx, column=10, value=e.get("notes") or "").border = thin_border
        row_idx += 1

    # Total row
    ws_expenses.cell(row=row_idx, column=7, value="Total").font = bold_font
    ws_expenses.cell(row=row_idx, column=7).border = thin_border
    total_cell = ws_expenses.cell(row=row_idx, column=8, value=data["total_expenses"])
    total_cell.number_format = currency_format
    total_cell.font = bold_font
    total_cell.border = thin_border

    for col in ws_expenses.columns:
        max_len = max(len(str(cell.value or '')) for cell in col)
        col_letter = get_column_letter(col[0].column)
        ws_expenses.column_dimensions[col_letter].width = min(max(max_len + 3, 12), 40)

    workbook.save(output)
    output.seek(0)
    return output
