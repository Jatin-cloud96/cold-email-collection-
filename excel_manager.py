import os
import json
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Set
import pandas as pd
from openpyxl import load_workbook, Workbook
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter

import config

COLUMNS = [
    "Name",
    "Title",
    "Company",
    "Domain",
    "Email",
    "Verification status",
    "Source",
    "Date found"
]

class ExcelManager:
    """Handles Excel creation, deduplication, styling, and persistence."""
    def __init__(self, excel_path: Path = config.EXCEL_OUTPUT_PATH, seen_path: Path = config.SEEN_LEADS_PATH):
        self.excel_path = excel_path
        self.seen_path = seen_path
        self.seen_people: Set[str] = set()
        self.seen_emails: Set[str] = set()
        self._init_storage()

    def _make_person_key(self, name: str, company: str) -> str:
        return f"{name.strip().lower()}||{company.strip().lower()}"

    def _init_storage(self):
        # 1. Load seen leads cache
        if self.seen_path.exists():
            try:
                with open(self.seen_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    self.seen_people = set(data.get("people", []))
                    self.seen_emails = set(data.get("emails", []))
            except Exception:
                pass

        # 2. If excel exists, read it to populate seen sets and ensure sync
        if self.excel_path.exists():
            try:
                df = pd.read_excel(self.excel_path)
                for _, row in df.iterrows():
                    name = str(row.get("Name", "")).strip()
                    company = str(row.get("Company", "")).strip()
                    email = str(row.get("Email", "")).strip().lower()
                    if name and company:
                        self.seen_people.add(self._make_person_key(name, company))
                    if email and email != "nan":
                        self.seen_emails.add(email)
            except Exception as e:
                print(f"[ExcelManager] Note reading existing sheet: {e}")
        else:
            # Create a fresh workbook with headers
            wb = Workbook()
            ws = wb.active
            ws.title = "Verified Leads"
            ws.append(COLUMNS)
            self._apply_styles(ws)
            wb.save(self.excel_path)

    def is_person_seen(self, name: str, company: str) -> bool:
        """Returns True if this person + company is already processed."""
        return self._make_person_key(name, company) in self.seen_people

    def is_email_seen(self, email: str) -> bool:
        """Returns True if this email is already recorded."""
        return email.strip().lower() in self.seen_emails

    def mark_seen(self, name: str, company: str, email: str = ""):
        self.seen_people.add(self._make_person_key(name, company))
        if email:
            self.seen_emails.add(email.strip().lower())
        self._save_seen_cache()

    def _save_seen_cache(self):
        try:
            with open(self.seen_path, "w", encoding="utf-8") as f:
                json.dump({
                    "people": list(self.seen_people),
                    "emails": list(self.seen_emails)
                }, f, indent=2)
        except Exception:
            pass

    def append_leads(self, leads: List[Dict[str, str]]) -> int:
        """
        Appends new valid leads to the Excel workbook and formats them nicely.
        Returns the number of leads added.
        """
        if not leads:
            return 0

        wb = load_workbook(self.excel_path)
        ws = wb.active

        count_added = 0
        thin_border = Border(
            left=Side(style='thin', color='DDDDDD'),
            right=Side(style='thin', color='DDDDDD'),
            top=Side(style='thin', color='DDDDDD'),
            bottom=Side(style='thin', color='DDDDDD')
        )
        valid_fill = PatternFill(start_color="E8F5E9", end_color="E8F5E9", fill_type="solid")

        for lead in leads:
            name = lead.get("Name", "")
            company = lead.get("Company", "")
            email = lead.get("Email", "")
            status = lead.get("Verification status", "valid")

            row_data = [
                name,
                lead.get("Title", ""),
                company,
                lead.get("Domain", ""),
                email,
                status,
                lead.get("Source", ""),
                lead.get("Date found", datetime.now().strftime("%Y-%m-%d"))
            ]
            ws.append(row_data)
            current_row = ws.max_row

            # Apply cell styles
            for col_idx in range(1, len(COLUMNS) + 1):
                cell = ws.cell(row=current_row, column=col_idx)
                cell.font = Font(name="Segoe UI", size=10)
                cell.alignment = Alignment(vertical="center")
                cell.border = thin_border
                if status == "valid" and col_idx == 6: # Status col
                    cell.fill = valid_fill
                    cell.font = Font(name="Segoe UI", size=10, bold=True, color="2E7D32")

            self.mark_seen(name, company, email)
            count_added += 1

        self._apply_styles(ws)
        wb.save(self.excel_path)
        return count_added

    def _apply_styles(self, ws):
        # Header styling
        header_font = Font(name="Segoe UI", size=11, bold=True, color="FFFFFF")
        header_fill = PatternFill(start_color="1F497D", end_color="1F497D", fill_type="solid")
        header_align = Alignment(horizontal="center", vertical="center", wrap_text=True)

        for col_idx in range(1, len(COLUMNS) + 1):
            cell = ws.cell(row=1, column=col_idx)
            cell.font = header_font
            cell.fill = header_fill
            cell.alignment = header_align
            ws.row_dimensions[1].height = 28

        # Auto-fit column widths
        for col in ws.columns:
            max_len = 0
            col_letter = get_column_letter(col[0].column)
            for cell in col:
                val = str(cell.value or "")
                if len(val) > max_len:
                    max_len = len(val)
            ws.column_dimensions[col_letter].width = max(max_len + 4, 15)

        # Enable auto-filter
        ws.auto_filter.ref = ws.dimensions

