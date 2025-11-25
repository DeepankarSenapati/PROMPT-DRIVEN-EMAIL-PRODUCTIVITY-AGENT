import streamlit as st
from pathlib import Path
import json
import os
from datetime import datetime
import pandas as pd

from agent import handle_user_message, get_memory, append_to_memory, load_memory  # functions in agent.py

ROOT = Path.cwd()
MOCK_INBOX = ROOT / "mock_inbox.json"
PROCESSED = ROOT / "processed_outputs.json"
PROMPTS = ROOT / "prompts.json"
ASSIGNMENT_PATH = str(Path("Assignment-2.pdf").absolute())  # uploaded file path (use as link)

st.set_page_config(page_title="Email Agent — Phase 1+2", layout="wide")
st.title("Ocean.AI — Email Agent (Phase 1 + 2)")

col1, col2 = st.columns([2, 1])

with col2:
    st.markdown("### Actions & Files")
    if Path(ASSIGNMENT_PATH).exists():
        st.markdown(f"[Open assignment brief]({ASSIGNMENT_PATH})")
    st.markdown("---")
    if st.button("Run Ingestion (batch)"):
        # execute ingest.py synchronously
        python_exe = os.sys.executable
        import subprocess
        proc = subprocess.run([python_exe, "ingest.py"], capture_output=True, text=True)
        if proc.returncode == 0:
            st.success("Ingestion finished.")
            st.code(proc.stdout)
        else:
            st.error("Ingestion failed.")
            st.code(proc.stdout + "\n\n" + proc.stderr)
    st.markdown("---")
    st.markdown("### Download files")
    if PROCESSED.exists():
        st.download_button("Download processed_outputs.json", PROCESSED.read_bytes(), file_name="processed_outputs.json")
    if MOCK_INBOX.exists():
        st.download_button("Download mock_inbox.json", MOCK_INBOX.read_bytes(), file_name="mock_inbox.json")
    if PROMPTS.exists():
        st.download_button("Download prompts.json", PROMPTS.read_bytes(), file_name="prompts.json")

with col1:
    st.subheader("Inbox & Agent Chat")
    inbox = json.load(open(MOCK_INBOX, "r", encoding="utf-8"))
    processed = json.load(open(PROCESSED, "r", encoding="utf-8")) if PROCESSED.exists() else []
    processed_map = {p["email_id"]: p for p in processed}

    # Inbox table
    rows = []
    for e in inbox:
        rows.append((e["id"], e["sender"], e["subject"], processed_map.get(e["id"], {}).get("category","")))
    df = pd.DataFrame(rows, columns=["id","sender","subject","category"])
    st.dataframe(df, use_container_width=True)

    st.markdown("---")
    st.markdown("### Email Agent Chat")
    session_id = st.text_input("Session ID (use anything unique per session):", value="default-session")
    email_choice = st.selectbox("Select email to chat about (optional):", options=["(none)"] + [e["id"] for e in inbox])
    user_input = st.text_area("Message to agent:", height=120, key="agent_input")
    
    col_a, col_b = st.columns([1,1])
    
    if col_a.button("Send"):
        sel = None if email_choice == "(none)" else email_choice

        with st.spinner("Thinking..."):
            try:
                out = handle_user_message(session_id, user_input, selected_email_id=sel)
                st.success("Agent replied")

                st.write("**Intent:**", out.get("intent"))
                st.write("**Reply:**")
                st.write(out.get("reply"))
                st.markdown("**Tool output (raw)**")
                st.json(out.get("tool_output"))

                # ---- Draft-specific actions: Save / Mock send ----
                # Store draft in session state so it persists across reruns
                if out.get("intent") == "draft_reply" or (out.get("tool_output") and out.get("tool_output").get("draft")):
                    # Store the draft and email_id in session state
                    draft_text = (out.get("tool_output") or {}).get("draft") or (out.get("reply") or "")
                    st.session_state['current_draft'] = draft_text
                    st.session_state['current_draft_email_id'] = sel

            except Exception as e:
                # Friendly UI error
                st.error("❗ The agent encountered an error while generating a response.")
                
                # Show short message
                st.write("**Summary of error:**")
                st.write(str(e)[:500])

                # Optional: reveal raw diagnostics if the user wants it
                with st.expander("Show technical details"):
                    st.exception(e)

                # Create a minimal fallback so UI doesn't break
                out = {
                    "reply": f"Error: {e}",
                    "tool_output": {"error": str(e)},
                    "intent": "error",
                }

    if 'current_draft' in st.session_state and st.session_state['current_draft']:
        st.markdown("---")
        st.markdown("#### Draft actions")

        # Editable draft area
        edited = st.text_area(
            "Draft (edit before saving/sending):", 
            value=st.session_state['current_draft'], 
            height=200, 
            key="draft_edit_area"
        )

        col_save, col_send, col_clear = st.columns([1,1,1])

        # Save draft
        if col_save.button("💾 Save draft"):
            from agent import save_draft
            email_id = st.session_state.get('current_draft_email_id')
            saved = save_draft(email_id=email_id, draft_text=edited, saved_by="you@company.com")
            
            if saved.get('id'):
                st.success(f"✅ Saved draft {saved.get('id')}")
                st.json(saved)
                st.rerun()
            else:
                st.error("❌ Failed to save draft")
                st.json(saved)

        if col_send.button("📧 Mock send"):
            from agent import save_draft, mock_send_draft
            email_id = st.session_state.get('current_draft_email_id')
            
            saved = save_draft(email_id=email_id, draft_text=edited, saved_by="you@company.com")
            
            if saved.get('id'):
                # Attach the assignment brief
                attach_example = [ASSIGNMENT_PATH] if Path(ASSIGNMENT_PATH).exists() else []
                sent = mock_send_draft(saved.get("id"), sender="you@company.com", attach_urls=attach_example)
                
                if sent.get("status") == "mock_sent":
                    st.success(f"✅ Mock-sent draft {saved.get('id')} (logged).")
                    if attach_example:
                        st.write("Attached files (mock):")
                        for a in attach_example:
                            st.write(f"  📎 {a}")
                    # Clear the draft from session state
                    del st.session_state['current_draft']
                    if 'current_draft_email_id' in st.session_state:
                        del st.session_state['current_draft_email_id']
                    st.rerun()
                else:
                    st.error("❌ Mock send failed.")
                    st.json(sent)
            else:
                st.error("❌ Failed to save draft before sending")

        # Clear draft
        if col_clear.button("🗑️ Clear draft"):
            del st.session_state['current_draft']
            if 'current_draft_email_id' in st.session_state:
                del st.session_state['current_draft_email_id']
            st.rerun()

    if col_b.button("Show conversation history"):
        mem = load_memory()
        hist = mem.get(session_id, {}).get("history", [])
        st.markdown(f"### History for session `{session_id}` (last {len(hist)} entries)")
        for entry in hist:
            ts = entry.get("ts")
            role = entry.get("role")
            if role == "user":
                st.markdown(f"**User @ {ts}:** {entry.get('text')}")
            else:
                st.markdown(f"**Agent @ {ts}:** {entry.get('text')}")
                if entry.get("tool_output"):
                    st.json(entry.get("tool_output"))
    st.markdown("---")
    st.subheader("📝 Saved drafts")

    from agent import list_drafts, mock_send_draft, delete_draft

    drafts = list_drafts(limit=50)

    if not drafts:
        st.info("No drafts saved yet. Generate a draft reply above and click 'Save draft' to save it.")
    else:
        st.write(f"**Total drafts:** {len(drafts)}")
        for d in drafts:
            draft_id = d.get('id')
            email_id = d.get('email_id') or 'N/A'
            created = d.get('created_at', '')
            is_sent = d.get('sent', False)
            
            status_emoji = "✅" if is_sent else "📝"
            status_text = "SENT" if is_sent else "Draft"
            
            with st.expander(f"{status_emoji} {draft_id} — Email: {email_id} — {status_text} — {created}"):
                st.text_area(
                    "Draft content:", 
                    value=d.get("draft_text", ""), 
                    height=150, 
                    key=f"view_{draft_id}",
                    disabled=True
                )

                cols = st.columns([1, 1, 1, 1])

                if not is_sent:
                    if cols[0].button("📧 Mock send", key=f"mock_{draft_id}"):
                        attach_example = [ASSIGNMENT_PATH] if Path(ASSIGNMENT_PATH).exists() else []
                        sent = mock_send_draft(draft_id, sender="you@company.com", attach_urls=attach_example)
                        
                        if sent.get("status") == "mock_sent":
                            st.success(f"✅ Mock-sent {draft_id}")
                            st.rerun()
                        else:
                            st.error("❌ Mock send failed")
                            st.json(sent)
                else:
                    cols[0].write("Already sent ✅")

                if cols[1].button("🗑️ Delete", key=f"del_{draft_id}"):
                    res = delete_draft(draft_id)
                    if res.get("status") == "deleted":
                        st.success(f"✅ Deleted {draft_id}")
                        st.rerun()
                    else:
                        st.error("❌ Delete failed")
                        st.json(res)

                cols[2].write(f"**Sent:** {is_sent}")
                if is_sent and d.get("sent_at"):
                    cols[3].write(f"**Sent at:** {d.get('sent_at')}")

st.markdown("---")
st.caption("Advanced Agent — supports summarization, extraction, drafting, search, and memory.")