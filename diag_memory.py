# diag_memory.py
import os, json
from agent import ROOT, MEMORY_PATH, load_memory, ensure_memory

print("cwd:", os.getcwd())
print("ROOT (agent):", ROOT)
print("MEMORY_PATH (agent):", MEMORY_PATH)
print("exists:", os.path.exists(MEMORY_PATH))
if os.path.exists(MEMORY_PATH):
    print("size:", os.path.getsize(MEMORY_PATH))
    print("head:", open(MEMORY_PATH,'r',encoding='utf-8').read()[:1000])
print("load_memory() ->", load_memory())
# ensure file exists (safe)
ensure_memory()
print("after ensure_memory exists:", os.path.exists(MEMORY_PATH))
