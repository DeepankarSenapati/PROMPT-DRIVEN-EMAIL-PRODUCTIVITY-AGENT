**📧 DEVELOPMENT OF A PROMPT-DRIVEN EMAIL PRODUCTIVITY AGENT**
**🚀 End-to-end LLM-powered Email Intelligence System (Gemini 2.5 Flash + Python + Streamlit + FastAPI)**

This project implements a full email-processing pipeline using Gemini 2.5 Flash, with:
Email ingestion (categorization + action extraction)
Natural-language powered Email Agent
Draft generation, summarization, Q&A
Persistent conversation memory
Saved draft manager + mock send
Streamlit UI

***✅ PHASE 1 — Email Ingestion Pipeline***
STEP 1 — Understanding the assignment
To visualize system architecture, I created diagrams on Mermaid Charts:
Flowchart (Sequence of Operations).png
Component Working Diagram (Architecture + Data Flow).png

STEP 2 — Building mock_inbox.json
Created 20 realistic sample emails: Meeting invitations, Newsletter content, Spam-like offers, Requests requiring action and Project updates

STEP 3 — Creating prompts.json
A modular prompt file holding all templates:
Categorization, Action extraction, Drafting, Summarization, Intent detection, Q&A agent
This keeps prompts editable without touching code.

STEP 4 — Creating llm_client.py (Gemini wrapper)
llm_client.py manages:
Deterministic LLM calls (temperature=0)
Structured output (JSON Schema)
Retry logic
MAX_TOKEN recovery
Diagnostics logging

Install the official Gemini SDK:
pip install google-genai

STEP 5 — Creating ingest.py
Responsible for:
Reading mock_inbox.json
Running categorization + action extraction
Producing processed_outputs.json
Fallback recovery (batch → per-email)
Output looks like:
[
  {
    "email_id": "email_001",
    "category": "To-Do",
    "extracted_actions": [...],
    "processed_at": "..."
  }
]

Install deps:
pip install fastapi uvicorn python-dotenv google-genai

Run:
uvicorn app_api:app --reload --port 8000

Visit Swagger UI:
http://localhost:8000/docs


STEP 7 — Initial environment setup
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt

.env file:
GEMINI_API_KEY=your_key_here

Test using:
python test_gemini.py


STEP 8 — Run ingestion
python ingest.py
This generates processed_outputs.json.

STEP 9 — Build Streamlit UI
Install Streamlit:
pip install streamlit pandas

Run:
streamlit run app_streamlit.py

***✅ PHASE 2 — Intelligent Email Agent***
STEP 1 — Created agent.py
Capabilities:
Summarization
Natural language Q&A
Task/action re-extraction
Draft generation (tone, length, fallback)
Memory tracking per session
Search emails
List all extracted tasks

All tool functions are modular:
tool_summarize
tool_extract_actions
tool_draft_reply
tool_search_emails
tool_list_actions
Gemini calls are robust, with:
Truncation of long emails
Multiple token-budget retries
Diagnostics logging
Fallback generation

STEP 2 — Updated prompts.json
Added templates for:
draft reply
summarization
Q&A agent
rewrite tone
intent detection

STEP 3 — Extended Streamlit UI
app_streamlit.py now includes:
Inbox table
Email Agent Chat panel
Memory per session
Safe try/except wrapper around LLM
Conversation history
Download data
Run ingestion button

Memory persisted in:
✔ memory.json

STEP 4 — Test workflow
Run:
streamlit run app_streamlit.py
Use:
Summarize this email → summary
What are the tasks here? → action list
Draft a reply accepting the meeting... → email draft
Find emails about migration → search results
List actions → all tasks

Inspect memory:
memory.json

✔ What Phase 2 implemented
Intent detection (LLM + heuristic fallback)
Full agent toolset
Robust draft engine (truncation + retries + fallback)
Robust action extractor (structured + fallback text parse)
Working conversation memory
Clean Streamlit UI with error handling
Logging system for failures
Quota/MAX_TOKEN safe design

***✅ PHASE 3 — Drafts Manager + Mock Sending***
STEP 1 — Implement draft storage in agent.py
Added:
load_drafts()
save_draft()
mock_send_draft()
list_drafts()

Draft structure in drafts.json:
{
  "id": "draft_1_1732452000",
  "email_id": "email_003",
  "draft_text": "...",
  "created_at": "...",
  "saved_by": "you@company.com",
  "sent": false,
  "sent_at": null
}

Mock send logs:
✔ logs/mock_sent.log

STEP 2 — Updated Streamlit UI
Added:

Save draft button
Mock send button
Saved Drafts Manager
View drafts
Mock-send drafts
Delete drafts

STEP 3 — Test full workflow
streamlit run app_streamlit.py

Flow:
Select email
Ask: Draft a reply accepting the meeting…
Click Save draft → appears in drafts.json
Click Mock send → log entry created
View/delete drafts from Saved drafts panel

🏗 Folder Structure
Ocean.AI/
│
├── app_streamlit.py
├── app_api.py
├── agent.py
├── ingest.py
├── llm_client.py
│
├── mock_inbox.json
├── processed_outputs.json
├── prompts.json
├── drafts.json
├── memory.json
│
├── logs/
│   ├── draft_errors.log
│   └── mock_sent.log
│
├── requirements.txt
└── Assignment - 2.pdf


🔧 Setup Instructions
1. Install dependencies
pip install -r requirements.txt
2. Create .env
GEMINI_API_KEY=YOUR_KEY
3. Run ingestion
python ingest.py
4. Run Streamlit UI
streamlit run app_streamlit.py
5. (Optional) Run FastAPI
uvicorn app_api:app --reload --port 8000


🚀 Demo Script (2–3 minutes)
Run:
streamlit run app_streamlit.py
Show inbox table
Select email_003
Ask:
“Summarize this email”
“What are the tasks here?”
“Draft a reply in friendly tone”

Click Save Draft
Go to Saved Drafts → show it
Click Mock Send → show log entry
Show memory.json (conversation remembered)
