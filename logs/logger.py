from datetime import datetime
import pandas as pd
import os


def log_conversation(person, message, logs_dir="logs"):
    now = datetime.now()
    day = now.day
    day_suffix = (
        "th" if 11 <= day <= 13 else {1: "st", 2: "nd", 3: "rd"}.get(day % 10, "th")
    )
    rest_of_date = now.strftime("%B, %Y")
    formatted_date = f"{day}{day_suffix} {rest_of_date}"  # e.g. 28th May, 2025

    formatted_time = now.strftime("%I:%M:%S %p")  # e.g. 03:02:01 PM

    os.makedirs(logs_dir, exist_ok=True)
    file_path = os.path.join(logs_dir, f"{formatted_date}.csv")

    data = {
        "Date": [formatted_date],
        "Time": [formatted_time],
        "Person": [person],
        "Context": [message],
    }

    if os.path.exists(file_path):
        df = pd.read_csv(file_path)
        df = pd.concat([df, pd.DataFrame(data)], ignore_index=True)
    else:
        df = pd.DataFrame(data)

    df.to_csv(file_path, index=False)
    return 0
