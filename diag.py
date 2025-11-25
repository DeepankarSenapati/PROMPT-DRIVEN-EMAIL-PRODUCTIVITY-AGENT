import os, json
from agent import ROOT, DRAFTS_PATH, load_drafts

print("cwd:", os.getcwd())
print("ROOT:", ROOT)
print("DRAFTS_PATH:", DRAFTS_PATH)
print("exists:", os.path.exists(DRAFTS_PATH))

if os.path.exists(DRAFTS_PATH):
    print("size:", os.path.getsize(DRAFTS_PATH))
    with open(DRAFTS_PATH,'r',encoding='utf-8') as f:
        print("content head:", f.read()[:800])

print("load_drafts():", load_drafts())
