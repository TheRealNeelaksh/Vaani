import streamlit as st
import pandas as pd
from pathlib import Path
import re

st.set_page_config(page_title="Shrudaya Logs Viewer", layout="wide")

# Logs directory
logs_dir = Path(__file__).resolve().parent.parent / "logs"


# Regex to match files like '28th May, 2025.csv'
def date_sort_key(filename):
    match = re.match(r"(\d{1,2})(st|nd|rd|th) (\w+), (\d{4})", filename.stem)
    if not match:
        # Return a very old timestamp so unmatched files appear at the end
        return pd.Timestamp.min
    day, _, month, year = match.groups()
    return pd.to_datetime(f"{day} {month} {year}", format="%d %B %Y")


# Find latest file
csv_files = sorted(logs_dir.glob("*.csv"), key=date_sort_key, reverse=True)

st.title("📜 Shrudaya - Daily Conversation Logs")

if csv_files:
    latest_file = csv_files[0]
    st.success(f"Showing logs from: **{latest_file.stem}**")

    df = pd.read_csv(latest_file)
    st.dataframe(df, use_container_width=True)

else:
    st.warning("No logs found yet. Speak to your AI buddy first!")
