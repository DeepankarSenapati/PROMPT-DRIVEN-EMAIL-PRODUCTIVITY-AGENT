# # # agent.py
# # """
# # Advanced Email Agent (Option C)
# # - Function-calling style orchestration
# # - Tools: summarize, extract_actions, draft_reply, search_emails, list_actions
# # - Conversation memory (file-based)
# # - Uses llm_client.call_gemini_text and call_gemini_structured
# # """

# # import json
# # import os
# # from datetime import datetime
# # from typing import Any, Dict, List, Optional

# # from llm_client import call_gemini_text, call_gemini_structured

# # ROOT = os.getcwd()
# # INBOX_PATH = os.path.join(ROOT, "mock_inbox.json")
# # PROMPTS_PATH = os.path.join(ROOT, "prompts.json")
# # MEMORY_PATH = os.path.join(ROOT, "memory.json")  # stores chat histories per session/email
# # PROCESSED_PATH = os.path.join(ROOT, "processed_outputs.json")
# # DRAFTS_PATH = os.path.join(ROOT, "drafts.json")
# # SENT_LOG = os.path.join(ROOT, "logs", "mock_sent.log")

# # # Load prompts
# # with open(PROMPTS_PATH, "r", encoding="utf-8") as f:
# #     PROMPTS = json.load(f)["prompts"]

# # # Utility loads
# # def load_inbox() -> List[Dict[str, Any]]:
# #     with open(INBOX_PATH, "r", encoding="utf-8") as f:
# #         return json.load(f)

# # def load_processed() -> List[Dict[str, Any]]:
# #     if not os.path.exists(PROCESSED_PATH):
# #         return []
# #     with open(PROCESSED_PATH, "r", encoding="utf-8") as f:
# #         return json.load(f)

# # def ensure_memory():
# #     if not os.path.exists(MEMORY_PATH):
# #         with open(MEMORY_PATH, "w", encoding="utf-8") as f:
# #             json.dump({}, f)

# # def load_memory() -> Dict[str, Any]:
# #     ensure_memory()
# #     with open(MEMORY_PATH, "r", encoding="utf-8") as f:
# #         return json.load(f)

# # def save_memory(mem: Dict[str, Any]):
# #     with open(MEMORY_PATH, "w", encoding="utf-8") as f:
# #         json.dump(mem, f, indent=2, ensure_ascii=False)

# # # --------------------
# # # Tools (functions the agent may call)
# # # --------------------

# # def tool_summarize(email_id: str, length: str = "short") -> Dict[str, str]:
# #     """
# #     Summarize the email body for given id.
# #     Retries with increasing token budgets and truncates very long emails.
# #     """
# #     inbox = load_inbox()
# #     e = next((x for x in inbox if x["id"] == email_id), None)
# #     if not e:
# #         return {"summary": f"Email {email_id} not found."}

# #     # Truncate long emails for safety
# #     MAX_EMAIL_CHARS = 1200
# #     raw_body = e.get("body", "")
# #     if len(raw_body) > MAX_EMAIL_CHARS:
# #         email_for_prompt = raw_body[:MAX_EMAIL_CHARS] + "\n\n...(truncated)"
# #     else:
# #         email_for_prompt = raw_body

# #     template = PROMPTS.get("summarization_v1", {}).get("template",
# #         "Summarize the following email in a {length} form. Email: {email}")
# #     prompt = template.format(email=email_for_prompt, subject=e.get("subject"), length=length)

# #     # Try successive budgets (small -> larger)
# #     attempts = [256, 512, 1024]
# #     last_err = None
# #     for tok in attempts:
# #         try:
# #             text = call_gemini_text(prompt, max_output_tokens=tok, temperature=0.0)
# #             if text and isinstance(text, str) and text.strip():
# #                 return {"summary": text.strip()}
# #         except Exception as exc:
# #             last_err = str(exc)
# #             # if it's a MAX_TOKENS finish, try next attempt; else break and return error
# #             if "MAX_TOKENS" in last_err or "\"finish_reason\": 2" in last_err or "no extractable text" in last_err:
# #                 continue
# #             else:
# #                 return {"summary": f"Error summarizing: {exc}"}
# #     # fallback
# #     return {"summary": f"Summary unavailable (model returned no extractable text). Last error: {last_err}"}


# # def tool_extract_actions(email_id: str) -> Dict[str, Any]:
# #     """
# #     Extract actions from a single email safely.
# #     - Truncates long emails
# #     - Retries structured extraction with larger token budgets
# #     - Falls back gracefully to empty list instead of errors
# #     """
# #     inbox = load_inbox()
# #     e = next((x for x in inbox if x["id"] == email_id), None)
# #     if not e:
# #         return {"actions": []}

# #     # --- safe truncation ---
# #     MAX_EMAIL_CHARS = 800
# #     raw_body = e.get("body", "")
# #     if len(raw_body) > MAX_EMAIL_CHARS:
# #         email_for_prompt = raw_body[:MAX_EMAIL_CHARS] + "\n\n...(truncated)"
# #     else:
# #         email_for_prompt = raw_body

# #     action_prompt_template = PROMPTS["action_extraction_v1"]["template"]
# #     action_prompt = f"{action_prompt_template}\n\nEmail:\nSubject: {e['subject']}\n\n{email_for_prompt}"

# #     # JSON schema for a list of actions
# #     schema = {
# #         "type": "array",
# #         "items": {
# #             "type": "object",
# #             "properties": {
# #                 "task": {"type": "string"},
# #                 "deadline": {"type": ["string", "null"]},
# #                 "assignee": {"type": ["string", "null"]}
# #             },
# #             "required": ["task"]
# #         }
# #     }

# #     attempts = [512, 1024]  # token budgets

# #     last_error = None
# #     for tok in attempts:
# #         try:
# #             parsed = call_gemini_structured(action_prompt, json_schema=schema,
# #                                             max_output_tokens=tok, temperature=0.0)
# #             if parsed:
# #                 return {"actions": parsed}
# #         except Exception as exc:
# #             last_error = str(exc)
# #             # continue to next attempt

# #     # --- fallback: try text mode ---
# #     try:
# #         raw = call_gemini_text(action_prompt, max_output_tokens=512, temperature=0.0)
# #         parsed = json.loads(raw)
# #         if isinstance(parsed, list):
# #             return {"actions": parsed}
# #     except Exception as exc:
# #         last_error = str(exc)

# #     # --- final fallback: no actions ---
# #     try:
# #         os.makedirs("logs", exist_ok=True)
# #         with open("logs/action_extraction_errors.log", "a", encoding="utf-8") as f:
# #             f.write(f"{datetime.utcnow().isoformat()} email={email_id} err={last_error}\n")
# #     except:
# #         pass

# #     return {"actions": []}


# # def tool_draft_reply(email_id: Optional[str], tone: str = "professional", length: str = "short", user_instruction: Optional[str] = None) -> Dict[str, str]:
# #     """
# #     Draft a reply to the given email.
# #     - If email_id is present we use the email text.
# #     - If email_id is None but user_instruction is present, we produce a draft based on instruction.
# #     - Retries with larger budgets on MAX_TOKENS/no-text diagnostics.
# #     - Logs diagnostics and falls back to a safe template.
# #     """
# #     inbox = load_inbox()
# #     e = None
# #     if email_id:
# #         # safe, case-insensitive, whitespace-cleaning match
# #         eid_clean = str(email_id).strip().lower()
# #         e = next(
# #             (x for x in inbox if str(x.get("id", "")).strip().lower() == eid_clean),
# #             None
# #         )

# #     # If no email but the user provided a direct instruction, allow drafting from the instruction
# #     if not e and not user_instruction:
# #         # original behavior: ask for original email (or return safe message)
# #         return {"draft": "Please provide the original email you'd like me to reply to!"}

# #     # Build prompt source: either email body (preferred) or the user instruction
# #     if e:
# #         # truncate email body if very long
# #         MAX_EMAIL_CHARS = 1200
# #         raw_body = e.get("body", "")
# #         if len(raw_body) > MAX_EMAIL_CHARS:
# #             email_for_prompt = raw_body[:MAX_EMAIL_CHARS] + "\n\n...(truncated)"
# #         else:
# #             email_for_prompt = raw_body
# #         prompt_source = email_for_prompt
# #     else:
# #         prompt_source = user_instruction or ""

# #     template = PROMPTS.get("draft_prompt_v1", {}).get(
# #         "template",
# #         "Draft a concise, professional reply to the following email with tone {tone} and length {length}. Include next steps if action is required. Email: {email}"
# #     )
# #     prompt = template.format(email=prompt_source, subject=(e.get("subject") if e else None), tone=tone, length=length)

# #     # attempts with increasing token budgets
# #     attempts = [
# #         {"max_output_tokens": 512, "temperature": 0.0},
# #         {"max_output_tokens": 1024, "temperature": 0.0},
# #         {"max_output_tokens": 1536, "temperature": 0.0},
# #     ]

# #     last_diag = None
# #     for attempt in attempts:
# #         try:
# #             text = call_gemini_text(prompt, max_output_tokens=attempt["max_output_tokens"], temperature=attempt["temperature"])
# #             if text and isinstance(text, str) and text.strip():
# #                 return {"draft": text.strip()}
# #             last_diag = f"Empty string returned for tokens={attempt['max_output_tokens']}"
# #         except ValueError as ve:
# #             msg = str(ve)
# #             last_diag = msg
# #             if "MAX_TOKENS" in msg or "\"finish_reason\": 2" in msg or "no extractable text" in msg:
# #                 try:
# #                     with open("logs/draft_errors.log", "a", encoding="utf-8") as lf:
# #                         lf.write(f"{datetime.utcnow().isoformat()} - draft attempt failed (MAX_TOKENS) tokens={attempt['max_output_tokens']} - diag={msg}\n")
# #                 except Exception:
# #                     pass
# #                 continue
# #             else:
# #                 try:
# #                     with open("logs/draft_errors.log", "a", encoding="utf-8") as lf:
# #                         lf.write(f"{datetime.utcnow().isoformat()} - draft unexpected error tokens={attempt['max_output_tokens']} - diag={msg}\n")
# #                 except Exception:
# #                     pass
# #                 return {"draft": f"Error drafting reply: {msg}"}
# #         except Exception as exc:
# #             last_diag = str(exc)
# #             try:
# #                 with open("logs/draft_errors.log", "a", encoding="utf-8") as lf:
# #                     lf.write(f"{datetime.utcnow().isoformat()} - draft unexpected exception tokens={attempt['max_output_tokens']} - exc={repr(exc)}\n")
# #             except Exception:
# #                 pass
# #             continue

# #     # all attempts exhausted -> fallback
# #     try:
# #         with open("logs/draft_errors.log", "a", encoding="utf-8") as lf:
# #             lf.write(f"{datetime.utcnow().isoformat()} - draft all attempts failed for email_id={email_id}. last_diag={last_diag}\n")
# #     except Exception:
# #         pass

# #     # friendly fallback draft
# #     if e:
# #         name = e.get('sender', '').split('@')[0].split('.')[0].capitalize()
# #     else:
# #         name = "there"
# #     fallback = (
# #         f"Hi {name},\n\n"
# #         "Thanks for the message — I’m available and happy to help. Please share any specific times or details and I’ll confirm. Looking forward to it.\n\n"
# #         "Best regards,\n[Your Name]"
# #     )
# #     return {"draft": fallback}

# # def tool_search_emails(query: str, limit: int = 5) -> Dict[str, Any]:
# #     """
# #     Very basic search over subject/body and sender. Returns top `limit` hits.
# #     """
# #     inbox = load_inbox()
# #     q = query.lower()
# #     results = []
# #     for e in inbox:
# #         score = 0
# #         if q in e.get("subject", "").lower():
# #             score += 3
# #         if q in e.get("body", "").lower():
# #             score += 2
# #         if q in e.get("sender", "").lower():
# #             score += 1
# #         if score > 0:
# #             results.append((score, e))
# #     results.sort(key=lambda x: -x[0])
# #     hits = [r[1] for r in results][:limit]
# #     return {"hits": hits}

# # def tool_list_actions() -> Dict[str, Any]:
# #     """
# #     Return aggregated actions from processed_outputs.json
# #     """
# #     processed = load_processed()
# #     actions_map = []
# #     for p in processed:
# #         for a in p.get("extracted_actions", []):
# #             actions_map.append({"email_id": p["email_id"], "task": a.get("task"), "deadline": a.get("deadline")})
# #     return {"actions": actions_map}

# # # --------------------
# # # Draft persistence + mock-send (robust)
# # # --------------------

# # def _ensure_drafts_file():
# #     """Ensure drafts.json exists and is initialized as an array."""
# #     try:
# #         if not os.path.exists(DRAFTS_PATH):
# #             with open(DRAFTS_PATH, "w", encoding="utf-8") as f:
# #                 json.dump([], f)
# #         else:
# #             if os.path.getsize(DRAFTS_PATH) == 0:
# #                 with open(DRAFTS_PATH, "w", encoding="utf-8") as f:
# #                     json.dump([], f)
# #     except Exception as exc:
# #         print("ensure_drafts_file error:", exc)

# # def load_drafts() -> List[Dict[str, Any]]:
# #     _ensure_drafts_file()
# #     try:
# #         with open(DRAFTS_PATH, "r", encoding="utf-8") as f:
# #             data = f.read()
# #             if not data.strip():
# #                 return []
# #             return json.loads(data)
# #     except Exception as exc:
# #         print("load_drafts: error reading drafts.json:", exc)
# #         return []

# # def save_draft(email_id: Optional[str], draft_text: str, saved_by: str = "you@company.com") -> Dict[str, Any]:
# #     """
# #     Save a draft and return the saved draft object.
# #     Uses atomic write to avoid zero-byte files.
# #     """
# #     _ensure_drafts_file()
# #     drafts = load_drafts()
# #     draft_id = f"draft_{len(drafts)+1}_{int(datetime.utcnow().timestamp())}"
# #     draft_obj = {
# #         "id": draft_id,
# #         "email_id": email_id,
# #         "draft_text": draft_text,
# #         "created_at": datetime.utcnow().isoformat() + "Z",
# #         "saved_by": saved_by,
# #         "sent": False,
# #         "sent_at": None
# #     }
# #     drafts.append(draft_obj)
# #     try:
# #         tmp = DRAFTS_PATH + ".tmp"
# #         with open(tmp, "w", encoding="utf-8") as f:
# #             json.dump(drafts, f, indent=2, ensure_ascii=False)
# #         os.replace(tmp, DRAFTS_PATH)
# #     except Exception as exc:
# #         print("save_draft: failed to write drafts.json:", exc)
# #         return {"error": "write_failed", "detail": str(exc)}
# #     return draft_obj

# # def list_drafts(limit: int = 50) -> List[Dict[str, Any]]:
# #     drafts = load_drafts()
# #     drafts_sorted = sorted(drafts, key=lambda d: d.get("created_at", ""), reverse=True)
# #     return drafts_sorted[:limit]

# # def delete_draft(draft_id: str) -> Dict[str, Any]:
# #     """Delete a draft by id and return status dict."""
# #     drafts = load_drafts()
# #     remaining = [d for d in drafts if d.get("id") != draft_id]
# #     if len(remaining) == len(drafts):
# #         return {"error": "not_found", "id": draft_id}
# #     try:
# #         tmp = DRAFTS_PATH + ".tmp"
# #         with open(tmp, "w", encoding="utf-8") as f:
# #             json.dump(remaining, f, indent=2, ensure_ascii=False)
# #         os.replace(tmp, DRAFTS_PATH)
# #         return {"status": "deleted", "id": draft_id}
# #     except Exception as exc:
# #         print("delete_draft: failed:", exc)
# #         return {"error": "write_failed", "detail": str(exc)}

# # def mock_send_draft(draft_id: str, sender: str = "you@company.com", attach_urls: Optional[List[str]] = None) -> Dict[str, Any]:
# #     """
# #     Mock-send a draft: mark as sent in drafts.json, write an entry to logs/mock_sent.log.
# #     Returns metadata or error.
# #     """
# #     drafts = load_drafts()
# #     found = None
# #     for d in drafts:
# #         if d.get("id") == draft_id:
# #             found = d
# #             break
# #     if not found:
# #         return {"error": "draft_not_found", "draft_id": draft_id}

# #     found["sent"] = True
# #     found["sent_at"] = datetime.utcnow().isoformat() + "Z"

# #     try:
# #         tmp = DRAFTS_PATH + ".tmp"
# #         with open(tmp, "w", encoding="utf-8") as f:
# #             json.dump(drafts, f, indent=2, ensure_ascii=False)
# #         os.replace(tmp, DRAFTS_PATH)
# #     except Exception as exc:
# #         print("mock_send_draft: failed to update drafts.json:", exc)

# #     try:
# #         os.makedirs(os.path.dirname(SENT_LOG), exist_ok=True)
# #     except Exception:
# #         pass

# #     try:
# #         with open(SENT_LOG, "a", encoding="utf-8") as lf:
# #             lf.write(f"{datetime.utcnow().isoformat()} - MOCK SEND - draft_id={draft_id} sender={sender} email_id={found.get('email_id')} attached={attach_urls}\n")
# #     except Exception as exc:
# #         print("mock_send_draft: failed to write sent log:", exc)

# #     return {"status": "mock_sent", "draft_id": draft_id, "sent_at": found.get("sent_at"), "attach_urls": attach_urls or []}

# # # --------------------
# # # Routing + intent detection
# # # --------------------

# # INTENT_PROMPT = PROMPTS.get("intent_detection_v1", {}).get("template", 
# #     "You are an intent classifier. Given the user message, classify intent as one of: summarize, extract_actions, draft_reply, search, list_actions, other. Respond with a single JSON: {\"intent\":\"...\",\"params\":{}}. Params may include email_id, query, tone, length.")

# # def detect_intent(user_text: str) -> Dict[str, Any]:
# #     schema = {
# #         "type": "object",
# #         "properties": {
# #             "intent": {"type": "string"},
# #             "params": {"type": "object"}
# #         },
# #         "required": ["intent"]
# #     }
# #     prompt = INTENT_PROMPT + "\n\nUser message:\n" + user_text + "\n\nReturn JSON only."

# #     try:
# #         parsed = call_gemini_structured(prompt, json_schema=schema, max_output_tokens=512, temperature=0.0)
# #         if parsed is None:
# #             raise ValueError("No structured JSON from model")
# #         return parsed
# #     except Exception as exc:
# #         # Log diagnostics for debugging
# #         print("Intent detection failed, falling back to heuristics. Error:", exc)
# #         lower = user_text.lower()
# #         # Simple heuristics fallback
# #         if "summar" in lower:
# #             return {"intent": "summarize", "params": {}}
# #         if any(k in lower for k in ("task", "tasks", "action", "todo", "to-do", "deadline")):
# #             return {"intent": "extract_actions", "params": {}}
# #         if "draft" in lower or "reply" in lower:
# #             return {"intent": "draft_reply", "params": {}}
# #         if "find" in lower or "search" in lower:
# #             return {"intent": "search", "params": {"query": user_text}}
# #         if "list actions" in lower or "all tasks" in lower:
# #             return {"intent": "list_actions", "params": {}}
# #         return {"intent": "other", "params": {}}


# # # --------------------
# # # Conversation memory
# # # --------------------

# # def append_to_memory(session_id: str, message: Dict[str, Any]):
# #     mem = load_memory()
# #     if session_id not in mem:
# #         mem[session_id] = {"history": []}
# #     mem[session_id]["history"].append({"ts": datetime.utcnow().isoformat() + "Z", **message})
# #     save_memory(mem)

# # def get_memory(session_id: str, limit: int = 10) -> List[Dict[str, Any]]:
# #     mem = load_memory()
# #     hist = mem.get(session_id, {}).get("history", [])
# #     return hist[-limit:]

# # # --------------------
# # # Main orchestrator
# # # --------------------

# # def handle_user_message(session_id: str, user_text: str, selected_email_id: Optional[str] = None) -> Dict[str, Any]:
# #     """
# #     Main entry to process a user message and call tools as needed.
# #     Quick heuristic: if an email is selected and the user asks about tasks/actions,
# #     prefer extract_actions intent immediately (avoids misclassification).
# #     """

# #     # ----- SAFE DEFAULTS -----
# #     intent = "other"
# #     params: Dict[str, Any] = {}

# #     # QUICK HEURISTIC:
# #     lower = (user_text or "").lower()
# #     task_keywords = ["task", "tasks", "action", "actions", "todo", "to-do", "deadline", "what are the tasks", "what tasks"]
# #     if selected_email_id and any(k in lower for k in task_keywords):
# #         intent = "extract_actions"
# #         params = {"email_id": selected_email_id}
# #     else:
# #         # LLM-based detection (existing) — keep in try so detection errors don't break the function
# #         try:
# #             intent_obj = detect_intent(user_text)
# #             # defend against None or bad shapes
# #             if isinstance(intent_obj, dict):
# #                 intent = intent_obj.get("intent", intent)
# #                 params = intent_obj.get("params", {}) or {}
# #             else:
# #                 intent = "other"
# #                 params = {}
# #         except Exception as exc:
# #             # log for debugging but keep running with defaults
# #             print("DEBUG: detect_intent failed:", exc)
# #             intent = "other"
# #             params = {}

# #     # Debug print — do this after intent/params exist
# #     print("DEBUG handle_user_message() session:", session_id, "selected_email_id:", repr(selected_email_id), "intent:", intent, "params:", params)

# #     # Merge selected email id if provided and param doesn't override
# #     if selected_email_id and "email_id" not in params:
# #         params["email_id"] = selected_email_id

# #     tool_output = None
# #     text_reply = None

# #     # route to tools
# #     try:
# #         if intent == "summarize":
# #             eid = params.get("email_id") or selected_email_id
# #             res = tool_summarize(eid, length=params.get("length", "short"))
# #             tool_output = res
# #             text_reply = res.get("summary")
# #         elif intent == "extract_actions":
# #             eid = params.get("email_id") or selected_email_id
# #             res = tool_extract_actions(eid)
# #             tool_output = res
# #             text_reply = "I extracted {} action(s).".format(len(res.get("actions", [])))
# #         elif intent == "draft_reply":
# #             # Prefer selected email; fallback to params; fallback to None
# #             eid = selected_email_id or params.get("email_id")
            
# #             # Pass user text so the tool can still draft if email missing
# #             res = tool_draft_reply(
# #                 email_id=eid,
# #                 tone=params.get("tone", "professional"),
# #                 length=params.get("length", "short"),
# #                 user_instruction=user_text
# #             )

# #             tool_output = res
# #             text_reply = res.get("draft")

# #         elif intent == "search":
# #             res = tool_search_emails(params.get("query", user_text), limit=params.get("limit", 5))
# #             tool_output = res
# #             text_reply = f"Found {len(res.get('hits', []))} matching emails."
# #         elif intent == "list_actions":
# #             res = tool_list_actions()
# #             tool_output = res
# #             text_reply = f"Found {len(res.get('actions', []))} total actions in processed outputs."
# #         else:
# #             # fallback: simple LLM reply using QA template over the selected email
# #             eid = params.get("email_id") or selected_email_id
# #             inbox = load_inbox()
# #             e = next((x for x in inbox if str(x.get("id","")).strip().lower() == str(eid).strip().lower()), None) if eid else None
# #             qa_template = PROMPTS.get("qa_agent_v1", {}).get("template", "Answer the question about the email: {email}\nQuestion: {question}")
# #             prompt_email = e["body"] if e else ""
# #             prompt = qa_template.format(email=prompt_email, question=user_text)
# #             text = call_gemini_text(prompt, max_output_tokens=512, temperature=0.0)
# #             tool_output = {"answer": text}
# #             text_reply = text

# #     except Exception as exc:
# #         # in case of tool or LLM error, return descriptive message
# #         text_reply = f"Error invoking tool or LLM: {exc}"
# #         tool_output = {"error": str(exc)}

# #     # record conversation memory
# #     append_to_memory(session_id, {"role": "user", "text": user_text, "intent": intent, "params": params})
# #     append_to_memory(session_id, {"role": "assistant", "text": (text_reply or ""), "tool_output": tool_output})

# #     return {"reply": text_reply, "tool_output": tool_output, "intent": intent, "params": params}

# """
# Advanced Email Agent (Option C)
# - Function-calling style orchestration
# - Tools: summarize, extract_actions, draft_reply, search_emails, list_actions
# - Conversation memory (file-based)
# - Uses llm_client.call_gemini_text and call_gemini_structured
# """

# import json
# import os
# from datetime import datetime
# from typing import Any, Dict, List, Optional

# from llm_client import call_gemini_text, call_gemini_structured

# ROOT = os.getcwd()
# INBOX_PATH = os.path.join(ROOT, "mock_inbox.json")
# PROMPTS_PATH = os.path.join(ROOT, "prompts.json")
# MEMORY_PATH = os.path.join(ROOT, "memory.json")  # stores chat histories per session/email
# PROCESSED_PATH = os.path.join(ROOT, "processed_outputs.json")
# DRAFTS_PATH = os.path.join(ROOT, "drafts.json")
# SENT_LOG = os.path.join(ROOT, "logs", "mock_sent.log")

# # Load prompts
# with open(PROMPTS_PATH, "r", encoding="utf-8") as f:
#     PROMPTS = json.load(f)["prompts"]

# # Utility loads
# def load_inbox() -> List[Dict[str, Any]]:
#     with open(INBOX_PATH, "r", encoding="utf-8") as f:
#         return json.load(f)

# def load_processed() -> List[Dict[str, Any]]:
#     if not os.path.exists(PROCESSED_PATH):
#         return []
#     with open(PROCESSED_PATH, "r", encoding="utf-8") as f:
#         return json.load(f)

# def ensure_memory():
#     if not os.path.exists(MEMORY_PATH):
#         with open(MEMORY_PATH, "w", encoding="utf-8") as f:
#             json.dump({}, f)

# def load_memory() -> Dict[str, Any]:
#     ensure_memory()
#     with open(MEMORY_PATH, "r", encoding="utf-8") as f:
#         return json.load(f)

# def save_memory(mem: Dict[str, Any]):
#     with open(MEMORY_PATH, "w", encoding="utf-8") as f:
#         json.dump(mem, f, indent=2, ensure_ascii=False)

# # --------------------
# # Helper: Find email by ID (case-insensitive, robust)
# # --------------------
# def find_email_by_id(email_id: Optional[str]) -> Optional[Dict[str, Any]]:
#     """
#     Find an email by ID with robust matching.
#     Returns None if email_id is None or not found.
#     """
#     if not email_id:
#         return None
    
#     inbox = load_inbox()
#     eid_clean = str(email_id).strip().lower()
    
#     for email in inbox:
#         if str(email.get("id", "")).strip().lower() == eid_clean:
#             return email
    
#     return None

# # --------------------
# # Tools (functions the agent may call)
# # --------------------

# def tool_summarize(email_id: str, length: str = "short") -> Dict[str, str]:
#     """
#     Summarize the email body for given id.
#     Retries with increasing token budgets and truncates very long emails.
#     """
#     e = find_email_by_id(email_id)
#     if not e:
#         return {"summary": f"Email {email_id} not found."}

#     # Truncate long emails for safety
#     MAX_EMAIL_CHARS = 1200
#     raw_body = e.get("body", "")
#     if len(raw_body) > MAX_EMAIL_CHARS:
#         email_for_prompt = raw_body[:MAX_EMAIL_CHARS] + "\n\n...(truncated)"
#     else:
#         email_for_prompt = raw_body

#     template = PROMPTS.get("summarization_v1", {}).get("template",
#         "Summarize the following email in a {length} form. Email: {email}")
#     prompt = template.format(email=email_for_prompt, subject=e.get("subject"), length=length)

#     # Try successive budgets (small -> larger)
#     attempts = [256, 512, 1024]
#     last_err = None
#     for tok in attempts:
#         try:
#             text = call_gemini_text(prompt, max_output_tokens=tok, temperature=0.0)
#             if text and isinstance(text, str) and text.strip():
#                 return {"summary": text.strip()}
#         except Exception as exc:
#             last_err = str(exc)
#             # if it's a MAX_TOKENS finish, try next attempt; else break and return error
#             if "MAX_TOKENS" in last_err or "\"finish_reason\": 2" in last_err or "no extractable text" in last_err:
#                 continue
#             else:
#                 return {"summary": f"Error summarizing: {exc}"}
#     # fallback
#     return {"summary": f"Summary unavailable (model returned no extractable text). Last error: {last_err}"}


# def tool_extract_actions(email_id: str) -> Dict[str, Any]:
#     """
#     Extract actions from a single email safely.
#     - Truncates long emails
#     - Retries structured extraction with larger token budgets
#     - Falls back gracefully to empty list instead of errors
#     """
#     e = find_email_by_id(email_id)
#     if not e:
#         return {"actions": []}

#     # --- safe truncation ---
#     MAX_EMAIL_CHARS = 800
#     raw_body = e.get("body", "")
#     if len(raw_body) > MAX_EMAIL_CHARS:
#         email_for_prompt = raw_body[:MAX_EMAIL_CHARS] + "\n\n...(truncated)"
#     else:
#         email_for_prompt = raw_body

#     action_prompt_template = PROMPTS["action_extraction_v1"]["template"]
#     action_prompt = f"{action_prompt_template}\n\nEmail:\nSubject: {e['subject']}\n\n{email_for_prompt}"

#     # JSON schema for a list of actions
#     schema = {
#         "type": "array",
#         "items": {
#             "type": "object",
#             "properties": {
#                 "task": {"type": "string"},
#                 "deadline": {"type": ["string", "null"]},
#                 "assignee": {"type": ["string", "null"]}
#             },
#             "required": ["task"]
#         }
#     }

#     attempts = [512, 1024]  # token budgets

#     last_error = None
#     for tok in attempts:
#         try:
#             parsed = call_gemini_structured(action_prompt, json_schema=schema,
#                                             max_output_tokens=tok, temperature=0.0)
#             if parsed:
#                 return {"actions": parsed}
#         except Exception as exc:
#             last_error = str(exc)
#             # continue to next attempt

#     # --- fallback: try text mode ---
#     try:
#         raw = call_gemini_text(action_prompt, max_output_tokens=512, temperature=0.0)
#         parsed = json.loads(raw)
#         if isinstance(parsed, list):
#             return {"actions": parsed}
#     except Exception as exc:
#         last_error = str(exc)

#     # --- final fallback: no actions ---
#     try:
#         os.makedirs("logs", exist_ok=True)
#         with open("logs/action_extraction_errors.log", "a", encoding="utf-8") as f:
#             f.write(f"{datetime.utcnow().isoformat()} email={email_id} err={last_error}\n")
#     except:
#         pass

#     return {"actions": []}


# def tool_draft_reply(email_id: Optional[str], tone: str = "professional", length: str = "short", user_instruction: Optional[str] = None) -> Dict[str, str]:
#     """
#     Draft a reply to the given email.
#     - If email_id is present we use the email text.
#     - If email_id is None but user_instruction is present, we produce a draft based on instruction.
#     - Retries with larger budgets on MAX_TOKENS/no-text diagnostics.
#     - Logs diagnostics and falls back to a safe template.
#     """
#     print(f"🔍 DEBUG tool_draft_reply called with:")
#     print(f"   email_id: {repr(email_id)}")
#     print(f"   tone: {tone}, length: {length}")
#     print(f"   user_instruction: {repr(user_instruction)}")
    
#     e = find_email_by_id(email_id)
    
#     print(f"   Email found: {e is not None}")
#     if e:
#         print(f"   Email subject: {e.get('subject')}")

#     # If no email and no user instruction, we can't draft
#     if not e and not user_instruction:
#         inbox = load_inbox()
#         available_ids = [x.get("id") for x in inbox[:5]]
#         return {
#             "draft": f"⚠️ Could not find email with ID '{email_id}'.\n\n"
#                     f"Available email IDs: {', '.join(available_ids)}\n\n"
#                     f"Please select a valid email from your inbox."
#         }

#     # Build prompt source: either email body (preferred) or the user instruction
#     if e:
#         # truncate email body if very long
#         MAX_EMAIL_CHARS = 1200
#         raw_body = e.get("body", "")
#         if len(raw_body) > MAX_EMAIL_CHARS:
#             email_for_prompt = raw_body[:MAX_EMAIL_CHARS] + "\n\n...(truncated)"
#         else:
#             email_for_prompt = raw_body
#         prompt_source = email_for_prompt
#     else:
#         prompt_source = user_instruction or ""

#     template = PROMPTS.get("draft_prompt_v1", {}).get(
#         "template",
#         "Draft a concise, professional reply to the following email with tone {tone} and length {length}. Include next steps if action is required. Email: {email}"
#     )
    
#     # Build a clear, structured prompt
#     if e:
#         prompt = f"""You are drafting a reply to an email. 

# Original Email:
# Subject: {e.get('subject')}
# From: {e.get('sender')}

# {prompt_source}

# Task: Draft a {tone} reply with {length} length. Include next steps if action is required. Write ONLY the email reply text, nothing else."""
#     else:
#         prompt = template.format(email=prompt_source, subject=None, tone=tone, length=length)

#     # attempts with increasing token budgets
#     attempts = [
#         {"max_output_tokens": 512, "temperature": 0.0},
#         {"max_output_tokens": 1024, "temperature": 0.0},
#         {"max_output_tokens": 1536, "temperature": 0.0},
#     ]

#     last_diag = None
#     for attempt in attempts:
#         try:
#             text = call_gemini_text(prompt, max_output_tokens=attempt["max_output_tokens"], temperature=attempt["temperature"])
#             if text and isinstance(text, str) and text.strip():
#                 return {"draft": text.strip()}
#             last_diag = f"Empty string returned for tokens={attempt['max_output_tokens']}"
#         except ValueError as ve:
#             msg = str(ve)
#             last_diag = msg
#             if "MAX_TOKENS" in msg or "\"finish_reason\": 2" in msg or "no extractable text" in msg:
#                 try:
#                     os.makedirs("logs", exist_ok=True)
#                     with open("logs/draft_errors.log", "a", encoding="utf-8") as lf:
#                         lf.write(f"{datetime.utcnow().isoformat()} - draft attempt failed (MAX_TOKENS) tokens={attempt['max_output_tokens']} - diag={msg}\n")
#                 except Exception:
#                     pass
#                 continue
#             else:
#                 try:
#                     os.makedirs("logs", exist_ok=True)
#                     with open("logs/draft_errors.log", "a", encoding="utf-8") as lf:
#                         lf.write(f"{datetime.utcnow().isoformat()} - draft unexpected error tokens={attempt['max_output_tokens']} - diag={msg}\n")
#                 except Exception:
#                     pass
#                 return {"draft": f"Error drafting reply: {msg}"}
#         except Exception as exc:
#             last_diag = str(exc)
#             try:
#                 os.makedirs("logs", exist_ok=True)
#                 with open("logs/draft_errors.log", "a", encoding="utf-8") as lf:
#                     lf.write(f"{datetime.utcnow().isoformat()} - draft unexpected exception tokens={attempt['max_output_tokens']} - exc={repr(exc)}\n")
#             except Exception:
#                 pass
#             continue

#     # all attempts exhausted -> fallback
#     try:
#         os.makedirs("logs", exist_ok=True)
#         with open("logs/draft_errors.log", "a", encoding="utf-8") as lf:
#             lf.write(f"{datetime.utcnow().isoformat()} - draft all attempts failed for email_id={email_id}. last_diag={last_diag}\n")
#     except Exception:
#         pass

#     # friendly fallback draft
#     if e:
#         name = e.get('sender', '').split('@')[0].split('.')[0].capitalize()
#     else:
#         name = "there"
#     fallback = (
#         f"Hi {name},\n\n"
#         "Thanks for the message — I'm available and happy to help. Please share any specific times or details and I'll confirm. Looking forward to it.\n\n"
#         "Best regards,\n[Your Name]"
#     )
#     return {"draft": fallback}

# def tool_search_emails(query: str, limit: int = 5) -> Dict[str, Any]:
#     """
#     Very basic search over subject/body and sender. Returns top `limit` hits.
#     """
#     inbox = load_inbox()
#     q = query.lower()
#     results = []
#     for e in inbox:
#         score = 0
#         if q in e.get("subject", "").lower():
#             score += 3
#         if q in e.get("body", "").lower():
#             score += 2
#         if q in e.get("sender", "").lower():
#             score += 1
#         if score > 0:
#             results.append((score, e))
#     results.sort(key=lambda x: -x[0])
#     hits = [r[1] for r in results][:limit]
#     return {"hits": hits}

# def tool_list_actions() -> Dict[str, Any]:
#     """
#     Return aggregated actions from processed_outputs.json
#     """
#     processed = load_processed()
#     actions_map = []
#     for p in processed:
#         for a in p.get("extracted_actions", []):
#             actions_map.append({"email_id": p["email_id"], "task": a.get("task"), "deadline": a.get("deadline")})
#     return {"actions": actions_map}

# # --------------------
# # Draft persistence + mock-send (robust)
# # --------------------

# def _ensure_drafts_file():
#     """Ensure drafts.json exists and is initialized as an array."""
#     try:
#         if not os.path.exists(DRAFTS_PATH):
#             with open(DRAFTS_PATH, "w", encoding="utf-8") as f:
#                 json.dump([], f)
#         else:
#             if os.path.getsize(DRAFTS_PATH) == 0:
#                 with open(DRAFTS_PATH, "w", encoding="utf-8") as f:
#                     json.dump([], f)
#     except Exception as exc:
#         print("ensure_drafts_file error:", exc)

# def load_drafts() -> List[Dict[str, Any]]:
#     _ensure_drafts_file()
#     try:
#         with open(DRAFTS_PATH, "r", encoding="utf-8") as f:
#             data = f.read()
#             if not data.strip():
#                 return []
#             return json.loads(data)
#     except Exception as exc:
#         print("load_drafts: error reading drafts.json:", exc)
#         return []

# def save_draft(email_id: Optional[str], draft_text: str, saved_by: str = "you@company.com") -> Dict[str, Any]:
#     """
#     Save a draft and return the saved draft object.
#     Uses atomic write to avoid zero-byte files.
#     """
#     _ensure_drafts_file()
#     drafts = load_drafts()
#     draft_id = f"draft_{len(drafts)+1}_{int(datetime.utcnow().timestamp())}"
#     draft_obj = {
#         "id": draft_id,
#         "email_id": email_id,
#         "draft_text": draft_text,
#         "created_at": datetime.utcnow().isoformat() + "Z",
#         "saved_by": saved_by,
#         "sent": False,
#         "sent_at": None
#     }
#     drafts.append(draft_obj)
#     try:
#         tmp = DRAFTS_PATH + ".tmp"
#         with open(tmp, "w", encoding="utf-8") as f:
#             json.dump(drafts, f, indent=2, ensure_ascii=False)
#         os.replace(tmp, DRAFTS_PATH)
#     except Exception as exc:
#         print("save_draft: failed to write drafts.json:", exc)
#         return {"error": "write_failed", "detail": str(exc)}
#     return draft_obj

# def list_drafts(limit: int = 50) -> List[Dict[str, Any]]:
#     drafts = load_drafts()
#     drafts_sorted = sorted(drafts, key=lambda d: d.get("created_at", ""), reverse=True)
#     return drafts_sorted[:limit]

# def delete_draft(draft_id: str) -> Dict[str, Any]:
#     """Delete a draft by id and return status dict."""
#     drafts = load_drafts()
#     remaining = [d for d in drafts if d.get("id") != draft_id]
#     if len(remaining) == len(drafts):
#         return {"error": "not_found", "id": draft_id}
#     try:
#         tmp = DRAFTS_PATH + ".tmp"
#         with open(tmp, "w", encoding="utf-8") as f:
#             json.dump(remaining, f, indent=2, ensure_ascii=False)
#         os.replace(tmp, DRAFTS_PATH)
#         return {"status": "deleted", "id": draft_id}
#     except Exception as exc:
#         print("delete_draft: failed:", exc)
#         return {"error": "write_failed", "detail": str(exc)}

# def mock_send_draft(draft_id: str, sender: str = "you@company.com", attach_urls: Optional[List[str]] = None) -> Dict[str, Any]:
#     """
#     Mock-send a draft: mark as sent in drafts.json, write an entry to logs/mock_sent.log.
#     Returns metadata or error.
#     """
#     drafts = load_drafts()
#     found = None
#     for d in drafts:
#         if d.get("id") == draft_id:
#             found = d
#             break
#     if not found:
#         return {"error": "draft_not_found", "draft_id": draft_id}

#     found["sent"] = True
#     found["sent_at"] = datetime.utcnow().isoformat() + "Z"

#     try:
#         tmp = DRAFTS_PATH + ".tmp"
#         with open(tmp, "w", encoding="utf-8") as f:
#             json.dump(drafts, f, indent=2, ensure_ascii=False)
#         os.replace(tmp, DRAFTS_PATH)
#     except Exception as exc:
#         print("mock_send_draft: failed to update drafts.json:", exc)

#     try:
#         os.makedirs(os.path.dirname(SENT_LOG), exist_ok=True)
#     except Exception:
#         pass

#     try:
#         with open(SENT_LOG, "a", encoding="utf-8") as lf:
#             lf.write(f"{datetime.utcnow().isoformat()} - MOCK SEND - draft_id={draft_id} sender={sender} email_id={found.get('email_id')} attached={attach_urls}\n")
#     except Exception as exc:
#         print("mock_send_draft: failed to write sent log:", exc)

#     return {"status": "mock_sent", "draft_id": draft_id, "sent_at": found.get("sent_at"), "attach_urls": attach_urls or []}

# # --------------------
# # Routing + intent detection
# # --------------------

# INTENT_PROMPT = PROMPTS.get("intent_detection_v1", {}).get("template", 
#     "You are an intent classifier. Given the user message, classify intent as one of: summarize, extract_actions, draft_reply, search, list_actions, other. Respond with a single JSON: {\"intent\":\"...\",\"params\":{}}. Params may include email_id, query, tone, length.")

# def detect_intent(user_text: str) -> Dict[str, Any]:
#     schema = {
#         "type": "object",
#         "properties": {
#             "intent": {"type": "string"},
#             "params": {"type": "object"}
#         },
#         "required": ["intent"]
#     }
#     prompt = INTENT_PROMPT + "\n\nUser message:\n" + user_text + "\n\nReturn JSON only."

#     try:
#         parsed = call_gemini_structured(prompt, json_schema=schema, max_output_tokens=512, temperature=0.0)
#         if parsed is None:
#             raise ValueError("No structured JSON from model")
#         return parsed
#     except Exception as exc:
#         # Log diagnostics for debugging
#         print("Intent detection failed, falling back to heuristics. Error:", exc)
#         lower = user_text.lower()
#         # Simple heuristics fallback
#         if "summar" in lower:
#             return {"intent": "summarize", "params": {}}
#         if any(k in lower for k in ("task", "tasks", "action", "todo", "to-do", "deadline")):
#             return {"intent": "extract_actions", "params": {}}
#         if "draft" in lower or "reply" in lower:
#             return {"intent": "draft_reply", "params": {}}
#         if "find" in lower or "search" in lower:
#             return {"intent": "search", "params": {"query": user_text}}
#         if "list actions" in lower or "all tasks" in lower:
#             return {"intent": "list_actions", "params": {}}
#         return {"intent": "other", "params": {}}


# # --------------------
# # Conversation memory
# # --------------------

# def append_to_memory(session_id: str, message: Dict[str, Any]):
#     mem = load_memory()
#     if session_id not in mem:
#         mem[session_id] = {"history": []}
#     mem[session_id]["history"].append({"ts": datetime.utcnow().isoformat() + "Z", **message})
#     save_memory(mem)

# def get_memory(session_id: str, limit: int = 10) -> List[Dict[str, Any]]:
#     mem = load_memory()
#     hist = mem.get(session_id, {}).get("history", [])
#     return hist[-limit:]

# # --------------------
# # Main orchestrator
# # --------------------

# def handle_user_message(session_id: str, user_text: str, selected_email_id: Optional[str] = None) -> Dict[str, Any]:
#     """
#     Main entry to process a user message and call tools as needed.
#     Quick heuristic: if an email is selected and the user asks about tasks/actions,
#     prefer extract_actions intent immediately (avoids misclassification).
#     """
#     print(f"\n{'='*60}")
#     print(f"🎯 handle_user_message called:")
#     print(f"   session_id: {session_id}")
#     print(f"   user_text: {repr(user_text)}")
#     print(f"   selected_email_id: {repr(selected_email_id)}")
#     print(f"{'='*60}\n")

#     # ----- SAFE DEFAULTS -----
#     intent = "other"
#     params: Dict[str, Any] = {}

#     # QUICK HEURISTIC:
#     lower = (user_text or "").lower()
#     task_keywords = ["task", "tasks", "action", "actions", "todo", "to-do", "deadline", "what are the tasks", "what tasks"]
    
#     if selected_email_id and any(k in lower for k in task_keywords):
#         intent = "extract_actions"
#         params = {"email_id": selected_email_id}
#     else:
#         # LLM-based detection (existing) — keep in try so detection errors don't break the function
#         try:
#             intent_obj = detect_intent(user_text)
#             # defend against None or bad shapes
#             if isinstance(intent_obj, dict):
#                 intent = intent_obj.get("intent", intent)
#                 params = intent_obj.get("params", {}) or {}
#             else:
#                 intent = "other"
#                 params = {}
#         except Exception as exc:
#             # log for debugging but keep running with defaults
#             print("DEBUG: detect_intent failed:", exc)
#             intent = "other"
#             params = {}

#     # Merge selected email id if provided and param doesn't override
#     if selected_email_id and "email_id" not in params:
#         params["email_id"] = selected_email_id

#     print(f"📋 Detected intent: {intent}")
#     print(f"📋 Params: {params}")

#     tool_output = None
#     text_reply = None

#     # route to tools
#     try:
#         if intent == "summarize":
#             eid = params.get("email_id") or selected_email_id
#             if not eid:
#                 text_reply = "Please select an email to summarize."
#                 tool_output = {"error": "no_email_selected"}
#             else:
#                 res = tool_summarize(eid, length=params.get("length", "short"))
#                 tool_output = res
#                 text_reply = res.get("summary")
                
#         elif intent == "extract_actions":
#             eid = params.get("email_id") or selected_email_id
#             if not eid:
#                 text_reply = "Please select an email to extract actions from."
#                 tool_output = {"error": "no_email_selected"}
#             else:
#                 res = tool_extract_actions(eid)
#                 tool_output = res
#                 actions = res.get("actions", [])
#                 if actions:
#                     text_reply = f"I found {len(actions)} action(s):\n\n"
#                     for i, action in enumerate(actions, 1):
#                         text_reply += f"{i}. {action.get('task', 'N/A')}"
#                         if action.get('deadline'):
#                             text_reply += f" (Deadline: {action['deadline']})"
#                         text_reply += "\n"
#                 else:
#                     text_reply = "No specific actions found in this email."
                    
#         elif intent == "draft_reply":
#             # Prefer selected email; fallback to params; fallback to None
#             eid = selected_email_id or params.get("email_id")
            
#             print(f"📧 Drafting reply for email_id: {repr(eid)}")
            
#             # Pass user text so the tool can still draft if email missing
#             res = tool_draft_reply(
#                 email_id=eid,
#                 tone=params.get("tone", "professional"),
#                 length=params.get("length", "short"),
#                 user_instruction=user_text
#             )

#             tool_output = res
#             text_reply = res.get("draft")

#         elif intent == "search":
#             res = tool_search_emails(params.get("query", user_text), limit=params.get("limit", 5))
#             tool_output = res
#             hits = res.get('hits', [])
#             if hits:
#                 text_reply = f"Found {len(hits)} matching email(s):\n\n"
#                 for i, email in enumerate(hits, 1):
#                     text_reply += f"{i}. [{email.get('id')}] From: {email.get('sender')} - {email.get('subject')}\n"
#             else:
#                 text_reply = "No matching emails found."
                
#         elif intent == "list_actions":
#             res = tool_list_actions()
#             tool_output = res
#             actions = res.get('actions', [])
#             if actions:
#                 text_reply = f"Found {len(actions)} total action(s) across all processed emails:\n\n"
#                 for i, action in enumerate(actions, 1):
#                     text_reply += f"{i}. [{action.get('email_id')}] {action.get('task')}"
#                     if action.get('deadline'):
#                         text_reply += f" (Deadline: {action['deadline']})"
#                     text_reply += "\n"
#             else:
#                 text_reply = "No actions found in processed emails."
                
#         else:
#             # fallback: simple LLM reply using QA template over the selected email
#             eid = params.get("email_id") or selected_email_id
#             e = find_email_by_id(eid)
            
#             qa_template = PROMPTS.get("qa_agent_v1", {}).get("template", "Answer the question about the email: {email}\nQuestion: {question}")
#             prompt_email = e["body"] if e else ""
#             prompt = qa_template.format(email=prompt_email, question=user_text)
#             text = call_gemini_text(prompt, max_output_tokens=512, temperature=0.0)
#             tool_output = {"answer": text}
#             text_reply = text

#     except Exception as exc:
#         # in case of tool or LLM error, return descriptive message
#         text_reply = f"Error invoking tool or LLM: {exc}"
#         tool_output = {"error": str(exc)}
#         print(f"❌ Error: {exc}")

#     # record conversation memory
#     append_to_memory(session_id, {"role": "user", "text": user_text, "intent": intent, "params": params})
#     append_to_memory(session_id, {"role": "assistant", "text": (text_reply or ""), "tool_output": tool_output})

#     print(f"✅ Reply: {text_reply[:100]}..." if len(text_reply or "") > 100 else f"✅ Reply: {text_reply}")
#     print(f"{'='*60}\n")

#     return {"reply": text_reply, "tool_output": tool_output, "intent": intent, "params": params}


"""
Advanced Email Agent (Option C)
- Function-calling style orchestration
- Tools: summarize, extract_actions, draft_reply, search_emails, list_actions
- Conversation memory (file-based)
- Uses llm_client.call_gemini_text and call_gemini_structured
"""

import json
import os
from datetime import datetime
from typing import Any, Dict, List, Optional

from llm_client import call_gemini_text, call_gemini_structured

ROOT = os.getcwd()
INBOX_PATH = os.path.join(ROOT, "mock_inbox.json")
PROMPTS_PATH = os.path.join(ROOT, "prompts.json")
MEMORY_PATH = os.path.join(ROOT, "memory.json")  # stores chat histories per session/email
PROCESSED_PATH = os.path.join(ROOT, "processed_outputs.json")
DRAFTS_PATH = os.path.join(ROOT, "drafts.json")
SENT_LOG = os.path.join(ROOT, "logs", "mock_sent.log")

# Load prompts
with open(PROMPTS_PATH, "r", encoding="utf-8") as f:
    PROMPTS = json.load(f)["prompts"]

# Utility loads
def load_inbox() -> List[Dict[str, Any]]:
    with open(INBOX_PATH, "r", encoding="utf-8") as f:
        return json.load(f)

def load_processed() -> List[Dict[str, Any]]:
    if not os.path.exists(PROCESSED_PATH):
        return []
    with open(PROCESSED_PATH, "r", encoding="utf-8") as f:
        return json.load(f)

def ensure_memory():
    if not os.path.exists(MEMORY_PATH):
        with open(MEMORY_PATH, "w", encoding="utf-8") as f:
            json.dump({}, f)

def load_memory() -> Dict[str, Any]:
    ensure_memory()
    with open(MEMORY_PATH, "r", encoding="utf-8") as f:
        return json.load(f)

def save_memory(mem: Dict[str, Any]):
    with open(MEMORY_PATH, "w", encoding="utf-8") as f:
        json.dump(mem, f, indent=2, ensure_ascii=False)

# --------------------
# Helper: Find email by ID (case-insensitive, robust)
# --------------------
def find_email_by_id(email_id: Optional[str]) -> Optional[Dict[str, Any]]:
    """
    Find an email by ID with robust matching.
    Returns None if email_id is None or not found.
    """
    if not email_id:
        return None
    
    inbox = load_inbox()
    eid_clean = str(email_id).strip().lower()
    
    for email in inbox:
        if str(email.get("id", "")).strip().lower() == eid_clean:
            return email
    
    return None

# --------------------
# Tools (functions the agent may call)
# --------------------

def tool_summarize(email_id: str, length: str = "short") -> Dict[str, str]:
    """
    Summarize the email body for given id.
    Retries with increasing token budgets and truncates very long emails.
    """
    e = find_email_by_id(email_id)
    if not e:
        return {"summary": f"Email {email_id} not found."}

    # Truncate long emails for safety
    MAX_EMAIL_CHARS = 1200
    raw_body = e.get("body", "")
    if len(raw_body) > MAX_EMAIL_CHARS:
        email_for_prompt = raw_body[:MAX_EMAIL_CHARS] + "\n\n...(truncated)"
    else:
        email_for_prompt = raw_body

    template = PROMPTS.get("summarization_v1", {}).get("template",
        "Summarize the following email in a {length} form. Email: {email}")
    prompt = template.format(email=email_for_prompt, subject=e.get("subject"), length=length)

    # Try successive budgets (small -> larger)
    attempts = [256, 512, 1024]
    last_err = None
    for tok in attempts:
        try:
            text = call_gemini_text(prompt, max_output_tokens=tok, temperature=0.0)
            if text and isinstance(text, str) and text.strip():
                return {"summary": text.strip()}
        except Exception as exc:
            last_err = str(exc)
            # if it's a MAX_TOKENS finish, try next attempt; else break and return error
            if "MAX_TOKENS" in last_err or "\"finish_reason\": 2" in last_err or "no extractable text" in last_err:
                continue
            else:
                return {"summary": f"Error summarizing: {exc}"}
    # fallback
    return {"summary": f"Summary unavailable (model returned no extractable text). Last error: {last_err}"}


def tool_extract_actions(email_id: str) -> Dict[str, Any]:
    """
    Extract actions from a single email safely.
    - Truncates long emails
    - Retries structured extraction with larger token budgets
    - Falls back gracefully to empty list instead of errors
    """
    e = find_email_by_id(email_id)
    if not e:
        return {"actions": []}

    # --- safe truncation ---
    MAX_EMAIL_CHARS = 800
    raw_body = e.get("body", "")
    if len(raw_body) > MAX_EMAIL_CHARS:
        email_for_prompt = raw_body[:MAX_EMAIL_CHARS] + "\n\n...(truncated)"
    else:
        email_for_prompt = raw_body

    action_prompt_template = PROMPTS["action_extraction_v1"]["template"]
    action_prompt = f"{action_prompt_template}\n\nEmail:\nSubject: {e['subject']}\n\n{email_for_prompt}"

    # JSON schema for a list of actions
    schema = {
        "type": "array",
        "items": {
            "type": "object",
            "properties": {
                "task": {"type": "string"},
                "deadline": {"type": ["string", "null"]},
                "assignee": {"type": ["string", "null"]}
            },
            "required": ["task"]
        }
    }

    attempts = [512, 1024]  # token budgets

    last_error = None
    for tok in attempts:
        try:
            parsed = call_gemini_structured(action_prompt, json_schema=schema,
                                            max_output_tokens=tok, temperature=0.0)
            if parsed:
                return {"actions": parsed}
        except Exception as exc:
            last_error = str(exc)
            # continue to next attempt

    # --- fallback: try text mode ---
    try:
        raw = call_gemini_text(action_prompt, max_output_tokens=512, temperature=0.0)
        parsed = json.loads(raw)
        if isinstance(parsed, list):
            return {"actions": parsed}
    except Exception as exc:
        last_error = str(exc)

    # --- final fallback: no actions ---
    try:
        os.makedirs("logs", exist_ok=True)
        with open("logs/action_extraction_errors.log", "a", encoding="utf-8") as f:
            f.write(f"{datetime.utcnow().isoformat()} email={email_id} err={last_error}\n")
    except:
        pass

    return {"actions": []}


def tool_draft_reply(email_id: Optional[str], tone: str = "professional", length: str = "short", user_instruction: Optional[str] = None) -> Dict[str, str]:
    """
    Draft a reply to the given email.
    - If email_id is present we use the email text.
    - If email_id is None but user_instruction is present, we produce a draft based on instruction.
    - Retries with larger budgets on MAX_TOKENS/no-text diagnostics.
    - Logs diagnostics and falls back to a safe template.
    """
    print(f"🔍 DEBUG tool_draft_reply called with:")
    print(f"   email_id: {repr(email_id)}")
    print(f"   tone: {tone}, length: {length}")
    print(f"   user_instruction: {repr(user_instruction)}")
    
    e = find_email_by_id(email_id)
    
    print(f"   Email found: {e is not None}")
    if e:
        print(f"   Email subject: {e.get('subject')}")

    # If no email and no user instruction, we can't draft
    if not e and not user_instruction:
        inbox = load_inbox()
        available_ids = [x.get("id") for x in inbox[:5]]
        return {
            "draft": f"⚠️ Could not find email with ID '{email_id}'.\n\n"
                    f"Available email IDs: {', '.join(available_ids)}\n\n"
                    f"Please select a valid email from your inbox."
        }

    # Build prompt source: either email body (preferred) or the user instruction
    if e:
        # truncate email body if very long
        MAX_EMAIL_CHARS = 1200
        raw_body = e.get("body", "")
        if len(raw_body) > MAX_EMAIL_CHARS:
            email_for_prompt = raw_body[:MAX_EMAIL_CHARS] + "\n\n...(truncated)"
        else:
            email_for_prompt = raw_body
        prompt_source = email_for_prompt
    else:
        prompt_source = user_instruction or ""

    template = PROMPTS.get("draft_prompt_v1", {}).get(
        "template",
        "Draft a concise, professional reply to the following email with tone {tone} and length {length}. Include next steps if action is required. Email: {email}"
    )
    
    # Build a clear, structured prompt
    if e:
        prompt = f"""TASK: Write an email reply

ORIGINAL EMAIL YOU RECEIVED:
---
From: {e.get('sender')}
Subject: {e.get('subject')}

{prompt_source}
---

YOUR REPLY REQUIREMENTS:
- Tone: {tone}
- Length: {length}
- Include next steps if action needed

Now write ONLY your email reply below (do NOT write "here is the reply" or any meta-text)."""
    else:
        prompt = template.format(email=prompt_source, subject=None, tone=tone, length=length)

    # attempts with increasing token budgets
    attempts = [
        {"max_output_tokens": 512, "temperature": 0.0},
        {"max_output_tokens": 1024, "temperature": 0.0},
        {"max_output_tokens": 1536, "temperature": 0.0},
    ]

    last_diag = None
    for attempt in attempts:
        try:
            text = call_gemini_text(prompt, max_output_tokens=attempt["max_output_tokens"], temperature=attempt["temperature"])
            if text and isinstance(text, str) and text.strip():
                return {"draft": text.strip()}
            last_diag = f"Empty string returned for tokens={attempt['max_output_tokens']}"
        except ValueError as ve:
            msg = str(ve)
            last_diag = msg
            if "MAX_TOKENS" in msg or "\"finish_reason\": 2" in msg or "no extractable text" in msg:
                try:
                    os.makedirs("logs", exist_ok=True)
                    with open("logs/draft_errors.log", "a", encoding="utf-8") as lf:
                        lf.write(f"{datetime.utcnow().isoformat()} - draft attempt failed (MAX_TOKENS) tokens={attempt['max_output_tokens']} - diag={msg}\n")
                except Exception:
                    pass
                continue
            else:
                try:
                    os.makedirs("logs", exist_ok=True)
                    with open("logs/draft_errors.log", "a", encoding="utf-8") as lf:
                        lf.write(f"{datetime.utcnow().isoformat()} - draft unexpected error tokens={attempt['max_output_tokens']} - diag={msg}\n")
                except Exception:
                    pass
                return {"draft": f"Error drafting reply: {msg}"}
        except Exception as exc:
            last_diag = str(exc)
            try:
                os.makedirs("logs", exist_ok=True)
                with open("logs/draft_errors.log", "a", encoding="utf-8") as lf:
                    lf.write(f"{datetime.utcnow().isoformat()} - draft unexpected exception tokens={attempt['max_output_tokens']} - exc={repr(exc)}\n")
            except Exception:
                pass
            continue

    # all attempts exhausted -> fallback
    try:
        os.makedirs("logs", exist_ok=True)
        with open("logs/draft_errors.log", "a", encoding="utf-8") as lf:
            lf.write(f"{datetime.utcnow().isoformat()} - draft all attempts failed for email_id={email_id}. last_diag={last_diag}\n")
    except Exception:
        pass

    # friendly fallback draft
    if e:
        name = e.get('sender', '').split('@')[0].split('.')[0].capitalize()
    else:
        name = "there"
    fallback = (
        f"Hi {name},\n\n"
        "Thanks for the message — I'm available and happy to help. Please share any specific times or details and I'll confirm. Looking forward to it.\n\n"
        "Best regards,\n[Your Name]"
    )
    return {"draft": fallback}

def tool_search_emails(query: str, limit: int = 5) -> Dict[str, Any]:
    """
    Very basic search over subject/body and sender. Returns top `limit` hits.
    """
    inbox = load_inbox()
    q = query.lower()
    results = []
    for e in inbox:
        score = 0
        if q in e.get("subject", "").lower():
            score += 3
        if q in e.get("body", "").lower():
            score += 2
        if q in e.get("sender", "").lower():
            score += 1
        if score > 0:
            results.append((score, e))
    results.sort(key=lambda x: -x[0])
    hits = [r[1] for r in results][:limit]
    return {"hits": hits}

def tool_list_actions() -> Dict[str, Any]:
    """
    Return aggregated actions from processed_outputs.json
    """
    processed = load_processed()
    actions_map = []
    for p in processed:
        for a in p.get("extracted_actions", []):
            actions_map.append({"email_id": p["email_id"], "task": a.get("task"), "deadline": a.get("deadline")})
    return {"actions": actions_map}

# --------------------
# Draft persistence + mock-send (robust)
# --------------------

def _ensure_drafts_file():
    """Ensure drafts.json exists and is initialized as an array."""
    try:
        if not os.path.exists(DRAFTS_PATH):
            with open(DRAFTS_PATH, "w", encoding="utf-8") as f:
                json.dump([], f)
        else:
            if os.path.getsize(DRAFTS_PATH) == 0:
                with open(DRAFTS_PATH, "w", encoding="utf-8") as f:
                    json.dump([], f)
    except Exception as exc:
        print("ensure_drafts_file error:", exc)

def load_drafts() -> List[Dict[str, Any]]:
    _ensure_drafts_file()
    try:
        with open(DRAFTS_PATH, "r", encoding="utf-8") as f:
            data = f.read()
            if not data.strip():
                return []
            return json.loads(data)
    except Exception as exc:
        print("load_drafts: error reading drafts.json:", exc)
        return []

def save_draft(email_id: Optional[str], draft_text: str, saved_by: str = "you@company.com") -> Dict[str, Any]:
    """
    Save a draft and return the saved draft object.
    Uses atomic write to avoid zero-byte files.
    """
    _ensure_drafts_file()
    drafts = load_drafts()
    draft_id = f"draft_{len(drafts)+1}_{int(datetime.utcnow().timestamp())}"
    draft_obj = {
        "id": draft_id,
        "email_id": email_id,
        "draft_text": draft_text,
        "created_at": datetime.utcnow().isoformat() + "Z",
        "saved_by": saved_by,
        "sent": False,
        "sent_at": None
    }
    drafts.append(draft_obj)
    try:
        tmp = DRAFTS_PATH + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(drafts, f, indent=2, ensure_ascii=False)
        os.replace(tmp, DRAFTS_PATH)
    except Exception as exc:
        print("save_draft: failed to write drafts.json:", exc)
        return {"error": "write_failed", "detail": str(exc)}
    return draft_obj

def list_drafts(limit: int = 50) -> List[Dict[str, Any]]:
    drafts = load_drafts()
    drafts_sorted = sorted(drafts, key=lambda d: d.get("created_at", ""), reverse=True)
    return drafts_sorted[:limit]

def delete_draft(draft_id: str) -> Dict[str, Any]:
    """Delete a draft by id and return status dict."""
    drafts = load_drafts()
    remaining = [d for d in drafts if d.get("id") != draft_id]
    if len(remaining) == len(drafts):
        return {"error": "not_found", "id": draft_id}
    try:
        tmp = DRAFTS_PATH + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(remaining, f, indent=2, ensure_ascii=False)
        os.replace(tmp, DRAFTS_PATH)
        return {"status": "deleted", "id": draft_id}
    except Exception as exc:
        print("delete_draft: failed:", exc)
        return {"error": "write_failed", "detail": str(exc)}

def mock_send_draft(draft_id: str, sender: str = "you@company.com", attach_urls: Optional[List[str]] = None) -> Dict[str, Any]:
    """
    Mock-send a draft: mark as sent in drafts.json, write an entry to logs/mock_sent.log.
    Returns metadata or error.
    """
    drafts = load_drafts()
    found = None
    for d in drafts:
        if d.get("id") == draft_id:
            found = d
            break
    if not found:
        return {"error": "draft_not_found", "draft_id": draft_id}

    found["sent"] = True
    found["sent_at"] = datetime.utcnow().isoformat() + "Z"

    try:
        tmp = DRAFTS_PATH + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(drafts, f, indent=2, ensure_ascii=False)
        os.replace(tmp, DRAFTS_PATH)
    except Exception as exc:
        print("mock_send_draft: failed to update drafts.json:", exc)

    try:
        os.makedirs(os.path.dirname(SENT_LOG), exist_ok=True)
    except Exception:
        pass

    try:
        with open(SENT_LOG, "a", encoding="utf-8") as lf:
            lf.write(f"{datetime.utcnow().isoformat()} - MOCK SEND - draft_id={draft_id} sender={sender} email_id={found.get('email_id')} attached={attach_urls}\n")
    except Exception as exc:
        print("mock_send_draft: failed to write sent log:", exc)

    return {"status": "mock_sent", "draft_id": draft_id, "sent_at": found.get("sent_at"), "attach_urls": attach_urls or []}

# --------------------
# Routing + intent detection
# --------------------

INTENT_PROMPT = PROMPTS.get("intent_detection_v1", {}).get("template", 
    "You are an intent classifier. Given the user message, classify intent as one of: summarize, extract_actions, draft_reply, search, list_actions, other. Respond with a single JSON: {\"intent\":\"...\",\"params\":{}}. Params may include email_id, query, tone, length.")

def detect_intent(user_text: str) -> Dict[str, Any]:
    schema = {
        "type": "object",
        "properties": {
            "intent": {"type": "string"},
            "params": {"type": "object"}
        },
        "required": ["intent"]
    }
    prompt = INTENT_PROMPT + "\n\nUser message:\n" + user_text + "\n\nReturn JSON only."

    try:
        parsed = call_gemini_structured(prompt, json_schema=schema, max_output_tokens=512, temperature=0.0)
        if parsed is None:
            raise ValueError("No structured JSON from model")
        return parsed
    except Exception as exc:
        # Log diagnostics for debugging
        print("Intent detection failed, falling back to heuristics. Error:", exc)
        lower = user_text.lower()
        # Simple heuristics fallback
        if "summar" in lower:
            return {"intent": "summarize", "params": {}}
        if any(k in lower for k in ("task", "tasks", "action", "todo", "to-do", "deadline")):
            return {"intent": "extract_actions", "params": {}}
        if "draft" in lower or "reply" in lower:
            return {"intent": "draft_reply", "params": {}}
        if "find" in lower or "search" in lower:
            return {"intent": "search", "params": {"query": user_text}}
        if "list actions" in lower or "all tasks" in lower:
            return {"intent": "list_actions", "params": {}}
        return {"intent": "other", "params": {}}


# --------------------
# Conversation memory
# --------------------

def append_to_memory(session_id: str, message: Dict[str, Any]):
    mem = load_memory()
    if session_id not in mem:
        mem[session_id] = {"history": []}
    mem[session_id]["history"].append({"ts": datetime.utcnow().isoformat() + "Z", **message})
    save_memory(mem)

def get_memory(session_id: str, limit: int = 10) -> List[Dict[str, Any]]:
    mem = load_memory()
    hist = mem.get(session_id, {}).get("history", [])
    return hist[-limit:]

# --------------------
# Main orchestrator
# --------------------

def handle_user_message(session_id: str, user_text: str, selected_email_id: Optional[str] = None) -> Dict[str, Any]:
    """
    Main entry to process a user message and call tools as needed.
    Quick heuristic: if an email is selected and the user asks about tasks/actions,
    prefer extract_actions intent immediately (avoids misclassification).
    """
    print(f"\n{'='*60}")
    print(f"🎯 handle_user_message called:")
    print(f"   session_id: {session_id}")
    print(f"   user_text: {repr(user_text)}")
    print(f"   selected_email_id: {repr(selected_email_id)}")
    print(f"{'='*60}\n")

    # ----- SAFE DEFAULTS -----
    intent = "other"
    params: Dict[str, Any] = {}

    # QUICK HEURISTIC:
    lower = (user_text or "").lower()
    task_keywords = ["task", "tasks", "action", "actions", "todo", "to-do", "deadline", "what are the tasks", "what tasks"]
    
    if selected_email_id and any(k in lower for k in task_keywords):
        intent = "extract_actions"
        params = {"email_id": selected_email_id}
    else:
        # LLM-based detection (existing) — keep in try so detection errors don't break the function
        try:
            intent_obj = detect_intent(user_text)
            # defend against None or bad shapes
            if isinstance(intent_obj, dict):
                intent = intent_obj.get("intent", intent)
                params = intent_obj.get("params", {}) or {}
            else:
                intent = "other"
                params = {}
        except Exception as exc:
            # log for debugging but keep running with defaults
            print("DEBUG: detect_intent failed:", exc)
            intent = "other"
            params = {}

    # Merge selected email id if provided and param doesn't override
    if selected_email_id and "email_id" not in params:
        params["email_id"] = selected_email_id

    print(f"📋 Detected intent: {intent}")
    print(f"📋 Params: {params}")

    tool_output = None
    text_reply = None

    # route to tools
    try:
        if intent == "summarize":
            eid = params.get("email_id") or selected_email_id
            if not eid:
                text_reply = "Please select an email to summarize."
                tool_output = {"error": "no_email_selected"}
            else:
                res = tool_summarize(eid, length=params.get("length", "short"))
                tool_output = res
                text_reply = res.get("summary")
                
        elif intent == "extract_actions":
            eid = params.get("email_id") or selected_email_id
            if not eid:
                text_reply = "Please select an email to extract actions from."
                tool_output = {"error": "no_email_selected"}
            else:
                res = tool_extract_actions(eid)
                tool_output = res
                actions = res.get("actions", [])
                if actions:
                    text_reply = f"I found {len(actions)} action(s):\n\n"
                    for i, action in enumerate(actions, 1):
                        text_reply += f"{i}. {action.get('task', 'N/A')}"
                        if action.get('deadline'):
                            text_reply += f" (Deadline: {action['deadline']})"
                        text_reply += "\n"
                else:
                    text_reply = "No specific actions found in this email."
                    
        elif intent == "draft_reply":
            # Prefer selected email; fallback to params; fallback to None
            eid = selected_email_id or params.get("email_id")
            
            print(f"📧 Drafting reply for email_id: {repr(eid)}")
            
            # Pass user text so the tool can still draft if email missing
            res = tool_draft_reply(
                email_id=eid,
                tone=params.get("tone", "professional"),
                length=params.get("length", "short"),
                user_instruction=user_text
            )

            tool_output = res
            text_reply = res.get("draft")

        elif intent == "search":
            res = tool_search_emails(params.get("query", user_text), limit=params.get("limit", 5))
            tool_output = res
            hits = res.get('hits', [])
            if hits:
                text_reply = f"Found {len(hits)} matching email(s):\n\n"
                for i, email in enumerate(hits, 1):
                    text_reply += f"{i}. [{email.get('id')}] From: {email.get('sender')} - {email.get('subject')}\n"
            else:
                text_reply = "No matching emails found."
                
        elif intent == "list_actions":
            res = tool_list_actions()
            tool_output = res
            actions = res.get('actions', [])
            if actions:
                text_reply = f"Found {len(actions)} total action(s) across all processed emails:\n\n"
                for i, action in enumerate(actions, 1):
                    text_reply += f"{i}. [{action.get('email_id')}] {action.get('task')}"
                    if action.get('deadline'):
                        text_reply += f" (Deadline: {action['deadline']})"
                    text_reply += "\n"
            else:
                text_reply = "No actions found in processed emails."
                
        else:
            # fallback: simple LLM reply using QA template over the selected email
            eid = params.get("email_id") or selected_email_id
            e = find_email_by_id(eid)
            
            qa_template = PROMPTS.get("qa_agent_v1", {}).get("template", "Answer the question about the email: {email}\nQuestion: {question}")
            prompt_email = e["body"] if e else ""
            prompt = qa_template.format(email=prompt_email, question=user_text)
            text = call_gemini_text(prompt, max_output_tokens=512, temperature=0.0)
            tool_output = {"answer": text}
            text_reply = text

    except Exception as exc:
        # in case of tool or LLM error, return descriptive message
        text_reply = f"Error invoking tool or LLM: {exc}"
        tool_output = {"error": str(exc)}
        print(f"❌ Error: {exc}")

    # record conversation memory
    try:
        append_to_memory(session_id, {"role": "user", "text": user_text, "intent": intent, "params": params})
        append_to_memory(session_id, {"role": "assistant", "text": (text_reply or ""), "tool_output": tool_output})
        print(f"💾 Memory updated for session: {session_id}")
    except Exception as mem_err:
        print(f"❌ MEMORY UPDATE FAILED: {mem_err}")

    print(f"✅ Reply: {text_reply[:100]}..." if len(text_reply or "") > 100 else f"✅ Reply: {text_reply}")
    print(f"{'='*60}\n")

    return {"reply": text_reply, "tool_output": tool_output, "intent": intent, "params": params}