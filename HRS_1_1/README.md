# VALE Housing Resale Simulator (HRS)

This is a Streamlit-based interactive Housing Resale Simulator (HRS) prototype.

Quick start

1. Create a virtual environment and install requirements:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

2. Run the app:

```powershell
streamlit run app.py
```

Features

- Load data from CSV, Excel, or a Google Sheets CSV export URL
- Interactive sliders and toggles for financial parameters
- Homeowner net proceeds and community affordability charts
- Export computed projections as CSV

Notes

- Financial calculations are provisional. See `finance.py` comments where assumptions are flagged for review.
- Google Sheets access supports public/published-as-CSV links. For private sheets, configure `gspread` with a service account.

Files of interest

- `app.py` - main Streamlit app UI
- `finance.py` - core financial model (annotated)
- `data_loader.py` - helpers to load CSV/Excel/Google Sheets

Next steps

- Hook up SQL data sources via SQLAlchemy
- Add user/session sharing (e.g., small server or Streamlit sharing)
