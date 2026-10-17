"""Google Sheets write helpers."""

from __future__ import annotations

from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from sqlalchemy.orm import Session

from app.config import get_settings
from app.export.errors import raise_google_error
from app.export.oauth import get_credentials_obj


def _service(db: Session):
    creds = get_credentials_obj(db)
    return build("sheets", "v4", credentials=creds, cache_discovery=False)


def write_sheet(
    db: Session,
    spreadsheet_id: str,
    sheet_title: str,
    headers: list[str],
    rows: list[list],
    note: str,
) -> None:
    settings = get_settings()
    service = _service(db)
    try:
        service.spreadsheets().batchUpdate(
            spreadsheetId=spreadsheet_id,
            body={
                "requests": [
                    {
                        "updateSpreadsheetProperties": {
                            "properties": {
                                "locale": "ru_RU",
                                "timeZone": settings.app_timezone,
                            },
                            "fields": "locale,timeZone",
                        }
                    },
                    {
                        "updateSheetProperties": {
                            "properties": {
                                "sheetId": 0,
                                "title": sheet_title,
                                "gridProperties": {"frozenRowCount": 1},
                            },
                            "fields": "title,gridProperties.frozenRowCount",
                        }
                    },
                ]
            },
        ).execute()

        values = [headers] + rows
        service.spreadsheets().values().update(
            spreadsheetId=spreadsheet_id,
            range=f"'{sheet_title}'!A1",
            valueInputOption="RAW",
            body={"values": values},
        ).execute()

        end_col = chr(ord("A") + max(len(headers) - 1, 0))
        end_row = len(values)
        requests = [
            {
                "repeatCell": {
                    "range": {
                        "sheetId": 0,
                        "startRowIndex": 0,
                        "endRowIndex": 1,
                    },
                    "cell": {
                        "userEnteredFormat": {
                            "textFormat": {"bold": True},
                            "backgroundColor": {
                                "red": 0.9,
                                "green": 0.93,
                                "blue": 0.96,
                            },
                        }
                    },
                    "fields": (
                        "userEnteredFormat(textFormat,backgroundColor)"
                    ),
                }
            },
            {
                "setBasicFilter": {
                    "filter": {
                        "range": {
                            "sheetId": 0,
                            "startRowIndex": 0,
                            "endRowIndex": end_row,
                            "startColumnIndex": 0,
                            "endColumnIndex": len(headers),
                        }
                    }
                }
            },
            {
                "updateCells": {
                    "rows": [
                        {
                            "values": [
                                {
                                    "note": note,
                                }
                            ]
                        }
                    ],
                    "fields": "note",
                    "start": {
                        "sheetId": 0,
                        "rowIndex": 0,
                        "columnIndex": 0,
                    },
                }
            },
            {
                "autoResizeDimensions": {
                    "dimensions": {
                        "sheetId": 0,
                        "dimension": "COLUMNS",
                        "startIndex": 0,
                        "endIndex": len(headers),
                    }
                }
            },
        ]
        service.spreadsheets().batchUpdate(
            spreadsheetId=spreadsheet_id,
            body={"requests": requests},
        ).execute()
    except HttpError as exc:
        raise_google_error(exc)
