# app_api.py
from fastapi import FastAPI
import json

app = FastAPI()

@app.get("/emails")
def get_emails():
    with open("mock_inbox.json") as f:
        return json.load(f)

@app.get("/processed")
def get_processed():
    with open("processed_outputs.json") as f:
        return json.load(f)

@app.get("/prompts")
def get_prompts():
    with open("prompts.json") as f:
        return json.load(f)

# add POST endpoints to update prompts and to trigger ingestion (call ingest.py)
