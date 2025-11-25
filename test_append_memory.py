# test_append_memory.py
from agent import append_to_memory, load_memory, MEMORY_PATH
print("Memory before:", load_memory())
append_to_memory("diag-session", {"role":"user","text":"hello from test","intent":"debug","params":{}})
print("Memory after:", load_memory())
print("File path:", MEMORY_PATH)
