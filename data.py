import json, os, httpx, pandas as pd

def load_df():
    root = httpx.get(os.environ["LEDGER_URL"], timeout=30).json()
    links = root["links"]

    rates = httpx.get(links["rates"], timeout=30).json()["usd_per_unit"]
    text = httpx.get(links["export"], timeout=60).text
    rows = [json.loads(l) for l in text.splitlines() if l.strip()]

    df = pd.DataFrame(rows)
    df["created_at"] = pd.to_datetime(df["created_at"], utc=True)
    df["updated_at"] = pd.to_datetime(df["updated_at"], utc=True)
    df = df.sort_values("updated_at").drop_duplicates("id", keep="last")
    df["created_at"] = df["created_at"].dt.tz_convert("Asia/Kolkata")
    df["usd"] = df["amount"] * df["currency"].map(rates)
    return df