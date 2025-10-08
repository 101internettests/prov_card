import logging
from typing import List, Optional
from datetime import datetime, timezone

import gspread


def get_sheet_url(sheet_id: Optional[str]) -> Optional[str]:
    if not sheet_id:
        return None
    return f"https://docs.google.com/spreadsheets/d/{sheet_id}"


def append_negative_result(
    sheet_id: Optional[str],
    service_account_json: Optional[str],
    worksheet_title: Optional[str],
    url: str,
    when_utc: Optional[datetime],
    providers_without_fee: List[str],
) -> bool:
    if not sheet_id or not service_account_json:
        logging.warning("Google Sheets не настроен (SHEET_ID/GOOGLE_SERVICE_ACCOUNT_JSON)")
        return False

    try:
        client = gspread.service_account(filename=service_account_json)
        spreadsheet = client.open_by_key(sheet_id)
        if worksheet_title:
            try:
                worksheet = spreadsheet.worksheet(worksheet_title)
            except gspread.WorksheetNotFound:
                worksheet = spreadsheet.add_worksheet(title=worksheet_title, rows=1000, cols=10)
        else:
            worksheet = spreadsheet.sheet1

        ts = (when_utc or datetime.now(timezone.utc)).astimezone(timezone.utc).strftime("%Y-%m-%d %H:%M:%S %Z")
        providers_str = ", ".join(providers_without_fee) if providers_without_fee else "-"
        row = [url, ts, providers_str]
        worksheet.append_row(row, value_input_option="RAW")
        logging.info("Добавлена строка в Google Sheets: %s", row)
        return True
    except Exception as exc:  # gspread/IO errors
        logging.exception("Не удалось записать в Google Sheets: %s", exc)
        return False

