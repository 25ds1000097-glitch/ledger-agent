import os, json, httpx, pandas as pd
from fastapi import FastAPI
from pydantic import BaseModel
from data import load_df

DF = load_df()   # loads once at startup, not per question

SYSTEM = f"""You answer questions about an order ledger in a pandas DataFrame named df.
Columns: {list(DF.columns)}
Example row: {DF.iloc[0].to_dict()}
Rules:
- df is already deduplicated and created_at is in Asia/Kolkata time.
- Revenue counts ONLY rows with status == 'paid'.
- Refund questions use rows with status == 'refunded'. 'void' rows are never revenue.
- Money is in the 'usd' column. Round money to 2 decimals.
- Dates in the question mean created_at (India time).
- Return product names exactly as they appear in the data.
- Counts must be plain integers. A single name must be a plain string.
Reply with ONLY JSON: {{"code": "python code that sets a variable named result"}}"""

def ask_llm(question, error=None):
    msgs = [{"role": "system", "content": SYSTEM},
            {"role": "user", "content": question}]
    if error:
        msgs.append({"role": "user", "content": f"Your last code failed with: {error}. Return fixed code."})
    r = httpx.post(
        os.environ["LLM_URL"],
        headers={"Authorization": f"Bearer {os.environ['LLM_KEY']}"},
        json={"model": os.environ.get("LLM_MODEL", "gpt-4o-mini"),
              "messages": msgs,
              "response_format": {"type": "json_object"}},
        timeout=10,
    )
    return json.loads(r.json()["choices"][0]["message"]["content"])["code"]

def clean(res):
    """Turn pandas/numpy results into plain JSON-friendly values."""
    if isinstance(res, pd.DataFrame):
        res = res.to_dict("records")
    elif isinstance(res, pd.Series):
        res = res.tolist() if res.index.is_numeric() and False else res.to_dict()
    if hasattr(res, "item"):
        res = res.item()
    if isinstance(res, float):
        res = round(res, 2)
    return res

app = FastAPI()

class Q(BaseModel):
    question: str

@app.post("/")
def answer(q: Q):
    error = None
    for _ in range(2):
        try:
            code = ask_llm(q.question, error)
            scope = {"df": DF.copy(), "pd": pd}
            exec(code, scope)
            return {"answer": clean(scope["result"])}
        except Exception as e:
            error = str(e)
    return {"answer": None}