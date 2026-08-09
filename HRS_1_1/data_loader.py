import pandas as pd
import requests
from io import BytesIO
import json

try:
    import gspread
    from google.oauth2.service_account import Credentials
    GSPREAD_AVAILABLE = True
except Exception:
    GSPREAD_AVAILABLE = False


def load_csv(path_or_buffer):
    return pd.read_csv(path_or_buffer)


def load_excel(path):
    return pd.read_excel(path, engine="openpyxl")


def load_google_sheet_csv(export_csv_url):
    # Accepts a Google Sheets 'export?format=csv' URL or any publicly accessible CSV URL
    r = requests.get(export_csv_url)
    r.raise_for_status()
    return pd.read_csv(BytesIO(r.content))


def load_data(file_like):
    # file_like may be a path, URL, or pandas DataFrame already
    if isinstance(file_like, pd.DataFrame):
        return file_like
    if isinstance(file_like, str):
        if file_like.lower().endswith('.csv'):
            return load_csv(file_like)
        if file_like.lower().endswith('.xlsx') or file_like.lower().endswith('.xls'):
            return load_excel(file_like)
        if 'docs.google.com' in file_like or file_like.lower().startswith('http'):
            # Try to load as CSV URL
            return load_google_sheet_csv(file_like)
    raise ValueError('Unsupported data source type')


def load_google_sheet_with_service_account(service_account_info: dict, spreadsheet_key: str, worksheet=0):
    """
    Load a Google Sheet using a service account JSON (provided as dict) and return a pandas DataFrame.

    - `service_account_info`: dict parsed from the JSON key file
    - `spreadsheet_key`: the spreadsheet ID or full URL
    - `worksheet`: index or name of the worksheet
    """
    if not GSPREAD_AVAILABLE:
        raise ImportError("gspread and google-auth are required to use service account loader. Add them to requirements.")

    # Build credentials and open the sheet
    creds = Credentials.from_service_account_info(service_account_info, scopes=[
        'https://www.googleapis.com/auth/spreadsheets.readonly',
        'https://www.googleapis.com/auth/drive.readonly',
    ])
    client = gspread.Client(auth=creds)
    client.session = client.auth._session

    # Accept either a full URL or a spreadsheet key
    try:
        if spreadsheet_key.startswith('http'):
            # extract key
            parts = spreadsheet_key.split('/')
            # typical URL contains '/d/{key}/'
            if 'd' in parts:
                d_index = parts.index('d')
                key = parts[d_index + 1]
            else:
                # fallback: last non-empty part
                key = [p for p in parts if p][-1]
        else:
            key = spreadsheet_key

        sh = client.open_by_key(key)
    except Exception:
        # Try open by URL/title
        sh = client.open_by_url(spreadsheet_key)

    # Select worksheet
    if isinstance(worksheet, int):
        ws = sh.get_worksheet(worksheet)
    else:
        ws = sh.worksheet(worksheet)

    records = ws.get_all_records()
    return pd.DataFrame.from_records(records)
