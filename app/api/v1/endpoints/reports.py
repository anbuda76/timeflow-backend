from fastapi.responses import StreamingResponse
import io
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter
import math
import calendar

@router.get("/export-excel")
def export_excel(
    year: int = Query(...),
    month: int = Query(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_manager),
):
    MONTH_NAMES = ['','Gennaio','Febbraio','Marzo','Aprile','Maggio','Giugno',
                   'Luglio','Agosto','Settembre','Ottobre','Novembre','Dicembre']

    # Stili
    header_fill = PatternFill("solid", start_color="1d4ed8", end_color="1d4ed8")
    header_font = Font(bold=True, color="FFFFFF", size=10)
    subheader_fill = PatternFill("solid", start_color="dbeafe", end_color="dbeafe")
    subheader_font = Font(bold=True, size=9)
    weekend_fill = PatternFill("solid", start_color="f1f5f9", end_color="f1f5f9")
    total_fill = PatternFill("solid", start_color="eff6ff", end_color="eff6ff")
    center = Alignment(horizontal="center", vertical="center")
    thin = Border(
        left=Side(style='thin'), right=Side(style='thin'),
        top=Side(style='thin'), bottom=Side(style='thin')
    )

    # Recupera utenti dell'org
    users_q = db.query(User).filter(
        User.organization_id == current_user.organization_id,
        User.is_active == True,
        User.role != UserRole.SUPER_ADMIN,
    )
    if current_user.role == UserRole.MANAGER:
        team_ids = [u.id for u in db.query(User).filter(User.manager_id == current_user.id).all()]
        team_ids.append(current_user.id)
        users_q = users_q.filter(User.id.in_(team_ids))
    users = users_q.all()

    # Recupera progetti normali dell'org
    projects = db.query(Project).filter(
        Project.organization_id == current_user.organization_id,
        Project.is_system == False,
        Project.is_active == True,
    ).all()

    # Recupera system projects (FERIE, PERMESSI, MALATTIA, STRAORDINARI)
    system_projects = db.query(Project).filter(
        Project.organization_id == current_user.organization_id,
        Project.is_system == True,
    ).all()
    system_map = {p.name.upper(): p.id for p in system_projects}

    # Recupera tutti i timesheet approvati del mese
    days_in_month = calendar.monthrange(year, month)[1]

    def get_entries_for_user(user_id):
        ts = db.query(Timesheet).filter(
            Timesheet.user_id == user_id,
            Timesheet.year == year,
            Timesheet.month == month,
        ).first()
        if not ts:
            return {}
        entries = db.query(TimesheetEntry).filter(
            TimesheetEntry.timesheet_id == ts.id
        ).all()
        result = {}
        for e in entries:
            day = e.entry_date.day
            if e.project_id not in result:
                result[e.project_id] = {}
            result[e.project_id][day] = e.hours
        return result

    wb = Workbook()

    # ── FOGLIO 1: RIEPILOGO GIORNATE ─────────────────────────────────────────
    ws1 = wb.active
    ws1.title = "RIEPILOGO GIORNATE"

    row_offset = 0
    for user in users:
        entries = get_entries_for_user(user.id)
        base_row = row_offset + 1

        # Nome utente
        ws1.merge_cells(start_row=base_row, start_column=3, end_row=base_row, end_column=3+days_in_month)
        cell = ws1.cell(row=base_row, column=3, value=f"{user.first_name.upper()} {user.last_name.upper()}")
        cell.font = Font(bold=True, size=11)
        cell.fill = header_fill
        cell.font = header_font
        cell.alignment = center

        # Anno e Mese
        ws1.cell(row=base_row, column=1, value="ANNO").font = subheader_font
        ws1.cell(row=base_row, column=2, value=year)
        ws1.cell(row=base_row+1, column=1, value="MESE").font = subheader_font
        ws1.cell(row=base_row+1, column=2, value=MONTH_NAMES[month])

        # Header giorni
        ws1.cell(row=base_row+2, column=2, value="")
        ws1.cell(row=base_row+2, column=3, value="GIORNI").font = subheader_font

        for d in range(1, days_in_month+1):
            col = d + 3
            ws1.cell(row=base_row+2, column=col, value=d)
            ws1.cell(row=base_row+2, column=col).alignment = center
            ws1.cell(row=base_row+2, column=col).font = Font(bold=True, size=9)
            # Giorno settimana
            dow = calendar.weekday(year, month, d)
            day_letter = ['L','M','M','G','V','S','D'][dow]
            ws1.cell(row=base_row+3, column=col, value=day_letter)
            ws1.cell(row=base_row+3, column=col).alignment = center
            ws1.cell(row=base_row+3, column=col).font = Font(size=8)
            if dow >= 5:  # weekend
                for r in range(base_row+2, base_row+9):
                    ws1.cell(row=r, column=col).fill = weekend_fill

        # Righe dati
        row_labels = [
            ("ORE", None),
            ("STRAORDINARI", system_map.get("STRAORDINARI")),
            ("PERMESSI", system_map.get("PERMESSI")),
            ("MALATTIA", system_map.get("MALATTIA")),
            ("ASSENZE/FERIE", system_map.get("FERIE")),
        ]

        for i, (label, proj_id) in enumerate(row_labels):
            data_row = base_row + 4 + i
            ws1.cell(row=data_row, column=3, value=label).font = Font(bold=True, size=9)

            row_total = 0
            for d in range(1, days_in_month+1):
                col = d + 3
                if label == "ORE":
                    # Somma tutte le ore dei progetti normali per quel giorno
                    val = sum(
                        proj_entries.get(d, 0)
                        for p_id, proj_entries in entries.items()
                        if p_id in [p.id for p in projects]
                    )
                elif proj_id:
                    val = entries.get(proj_id, {}).get(d, 0)
                else:
                    val = 0

                if val:
                    ws1.cell(row=data_row, column=col, value=val)
                    ws1.cell(row=data_row, column=col).alignment = center
                    row_total += val

            # Totale riga
            tot_col = days_in_month + 4
            ws1.cell(row=data_row, column=tot_col, value=f'=SUM({get_column_letter(4)}{data_row}:{get_column_letter(tot_col-1)}{data_row})')
            ws1.cell(row=data_row, column=tot_col).fill = total_fill
            ws1.cell(row=data_row, column=tot_col).font = Font(bold=True, size=9)

        row_offset += 10  # spazio tra utenti

    # Larghezze colonne foglio 1
    ws1.column_dimensions['A'].width = 8
    ws1.column_dimensions['B'].width = 12
    ws1.column_dimensions['C'].width = 16
    for d in range(1, 32):
        ws1.column_dimensions[get_column_letter(d+3)].width = 4
    ws1.column_dimensions[get_column_letter(35)].width = 8

    # ── FOGLIO 2: RIEPILOGO PROGETTI ─────────────────────────────────────────
    ws2 = wb.create_sheet("RIEPILOGO PROGETTI")

    # Header utenti
    ws2.cell(row=1, column=2, value="n°").font = subheader_font
    ws2.cell(row=1, column=3, value="PROGETTO").font = subheader_font
    ws2.cell(row=1, column=1, value=f"{MONTH_NAMES[month]} {year}").font = Font(bold=True, size=11)

    col = 4
    for user in users:
        ws2.merge_cells(start_row=1, start_column=col, end_row=1, end_column=col+1)
        cell = ws2.cell(row=1, column=col, value=user.last_name.upper())
        cell.font = header_font
        cell.fill = header_fill
        cell.alignment = center
        ws2.cell(row=2, column=col, value="ORE").font = subheader_font
        ws2.cell(row=2, column=col).alignment = center
        ws2.cell(row=2, column=col+1, value="GIORNI").font = subheader_font
        ws2.cell(row=2, column=col+1).alignment = center
        col += 3

    # Righe progetti
    for i, project in enumerate(projects):
        data_row = i + 3
        ws2.cell(row=data_row, column=2, value=i+1)
        ws2.cell(row=data_row, column=3, value=project.name).font = Font(size=9)

        col = 4
        for user in users:
            entries = get_entries_for_user(user.id)
            hours = sum(entries.get(project.id, {}).values())
            giorni = math.ceil(hours / 8) if hours > 0 else 0
            if hours > 0:
                ws2.cell(row=data_row, column=col, value=hours).alignment = center
            if giorni > 0:
                ws2.cell(row=data_row, column=col+1, value=giorni).alignment = center
            col += 3

    # Larghezze colonne foglio 2
    ws2.column_dimensions['A'].width = 12
    ws2.column_dimensions['B'].width = 5
    ws2.column_dimensions['C'].width = 30
    for i, user in enumerate(users):
        ws2.column_dimensions[get_column_letter(4 + i*3)].width = 8
        ws2.column_dimensions[get_column_letter(5 + i*3)].width = 8
        ws2.column_dimensions[get_column_letter(6 + i*3)].width = 3

    # Salva in memoria
    output = io.BytesIO()
    wb.save(output)
    output.seek(0)

    filename = f"timeflow_export_{year}_{month:02d}.xlsx"
    return StreamingResponse(
        output,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )