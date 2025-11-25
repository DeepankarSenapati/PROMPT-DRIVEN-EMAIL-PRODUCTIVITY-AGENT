import json
import time
import traceback
from datetime import datetime
from typing import Any, Dict

from llm_client import call_gemini_text, call_gemini_structured

MOCK_INBOX_PATH = "mock_inbox.json"
PROMPTS_PATH = "prompts.json"
OUTPUT_PATH = "processed_outputs.json"

with open(MOCK_INBOX_PATH, "r", encoding="utf-8") as f:
    emails = json.load(f)

with open(PROMPTS_PATH, "r", encoding="utf-8") as f:
    prompts = json.load(f)["prompts"]

action_item_schema = {
    "type": "object",
    "properties": {
        "task": {"type": "string"},
        "deadline": {"type": ["string", "null"]},
        "assignee": {"type": ["string", "null"]}
    },
    "required": ["task"]
}

actions_array_schema = {
    "type": "array",
    "items": action_item_schema
}

batch_schema = {
    "type": "array",
    "items": {
        "type": "object",
        "properties": {
            "email_id": {"type": "string"},
            "category": {"type": "string"},
            "extracted_actions": actions_array_schema
        },
        "required": ["email_id", "category", "extracted_actions"]
    }
}

def sanitize_text_output(raw: str):
    """
    Removes Gemini SDK repr outputs such as:
    'response:\nGenerateContentResponse(... done=True ...)'.
    Returns clean text or None.
    """
    if not raw:
        return None

    s = raw.strip()

    # If output looks like an SDK object representation, ignore it
    if s.startswith("response:") or "GenerateContentResponse" in s:
        return None

    # Remove markdown fences
    if s.startswith("```"):
        s = s.strip("`").strip()

    return s


def try_parse_json_from_text(raw: str):
    """
    Extracts first JSON object/array substring from text.
    """
    if not raw:
        return None

    txt = raw.strip()

    # remove markdown fences
    if txt.startswith("```"):
        txt = txt.strip("`").strip()

    # find JSON object or array
    o_start = txt.find("{")
    a_start = txt.find("[")
    if o_start == -1 and a_start == -1:
        return None

    # earliest brace
    start = min([i for i in [o_start, a_start] if i != -1])
    # last closing brace
    end = max(txt.rfind("}"), txt.rfind("]"))
    if end == -1 or end <= start:
        return None

    candidate = txt[start:end + 1]

    try:
        return json.loads(candidate)
    except Exception:
        return None

def build_batch_prompt(emails_list):
    cat_template = prompts["categorization_v1"]["template"]
    action_template = prompts["action_extraction_v1"]["template"]

    instruction = (
        "You will be provided an array of email objects. For each email, return an object with keys:\n"
        "  - email_id (string)\n"
        "  - category (Important, Newsletter, Spam, To-Do, Project Update)\n"
        "  - extracted_actions (array of {task, deadline, assignee})\n\n"
        "Rules:\n"
        f"- Categorization rules: {cat_template}\n"
        f"- Action extraction rules: {action_template}\n"
        "- Respond ONLY with valid JSON that matches the schema.\n"
        "- No explanations, no markdown, no commentary.\n\n"
        "Here is the email array:\n"
    )

    return instruction + json.dumps(emails_list, ensure_ascii=False)


def write_outputs(results):
    now = datetime.utcnow().isoformat() + "Z"
    out = []
    for item in results:
        out.append({
            "email_id": item["email_id"],
            "category": item["category"],
            "extracted_actions": item["extracted_actions"],
            "processed_at": now
        })
    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(out, f, indent=2, ensure_ascii=False)
    print("Wrote", len(out), "results to processed_outputs.json")


def run_batch_chunked(chunk_size=5):
    """
    Split emails into chunks and call structured batch for each chunk.
    Writes combined output.
    """
    all_results = []
    total = len(emails)
    for i in range(0, total, chunk_size):
        chunk = emails[i:i+chunk_size]
        print(f"Batch chunk {i//chunk_size + 1}: processing {len(chunk)} emails...")
        prompt = build_batch_prompt(chunk)
        parsed = call_gemini_structured(prompt, json_schema=batch_schema, temperature=0.0, max_output_tokens=4096)
        if parsed is None or not isinstance(parsed, list):
            print("Chunk failed or returned invalid JSON; falling back to per-email for that chunk.")

            for e in chunk:
               
                all_results.append({
                    "email_id": e["id"],
                    "category": "Unknown",
                    "extracted_actions": [],
                })
            continue
        all_results.extend(parsed)

    # normalize and write
    now = datetime.utcnow().isoformat() + "Z"
    normalized = []
    for item in all_results:
        normalized.append({
            "email_id": item.get("email_id"),
            "category": item.get("category"),
            "extracted_actions": item.get("extracted_actions", []),
            "processed_at": now
        })
    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(normalized, f, indent=2, ensure_ascii=False)
    print(f"Wrote {len(normalized)} results to {OUTPUT_PATH}")
    return True

def run_per_email(rate_limit_seconds=6.0):
    print("Running per-email fallback with", rate_limit_seconds, "sec delay per email.")

    outputs = []

    for idx, e in enumerate(emails, start=1):
        print(f"[{idx}/{len(emails)}] {e['id']} - {e['subject']}")

        email_text = f"Subject: {e['subject']}\n\n{e['body']}"

        cat_prompt = (
            prompts["categorization_v1"]["template"]
            + "\n\nEmail:\n"
            + email_text
            + "\n\nRespond with a single category label."
        )

        cat_raw = call_gemini_text(cat_prompt, max_output_tokens=256)
        cat_text = sanitize_text_output(cat_raw)
        category = cat_text.strip() if cat_text else "Unknown"

        action_prompt = (
            prompts["action_extraction_v1"]["template"]
            + "\n\nEmail:\n"
            + email_text
        )

        actions = call_gemini_structured(
            action_prompt,
            json_schema=actions_array_schema,
            max_output_tokens=512
        )

        if actions is None:
            # fallback parse
            raw = call_gemini_text(action_prompt, max_output_tokens=512)
            parsed = try_parse_json_from_text(raw)
            actions = parsed if parsed is not None else []

        outputs.append({
            "email_id": e["id"],
            "category": category,
            "extracted_actions": actions,
            "processed_at": datetime.utcnow().isoformat() + "Z"
        })

        time.sleep(rate_limit_seconds)

    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(outputs, f, indent=2, ensure_ascii=False)

    print("Per-email ingestion complete.")


if __name__ == "__main__":
    success = run_batch_chunked()
    if not success:
        print("Batch failed. Using per-email fallback.")
        run_per_email()
