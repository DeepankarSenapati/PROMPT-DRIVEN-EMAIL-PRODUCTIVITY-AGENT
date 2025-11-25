# test_save.py
from agent import save_draft, load_drafts, DRAFTS_PATH
print("DRAFTS_PATH:", DRAFTS_PATH)
res = save_draft(email_id="email_test", draft_text="This is a quick test draft", saved_by="you@company.com")
print("save_draft returned:", res)
print("Current drafts:", load_drafts())
