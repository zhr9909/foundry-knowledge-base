import os,sys

fp = r"E:\AgentProjects\ai-solution-architect-lab\projects\foundry-knowledge-base\app\app.js"
with open(fp, "rb") as f:
    b = bytearray(f.read())

# Fix catch: loadConversation (line 144 area)
# Pattern: .catch(function() { showToast('加载对话失败', 'error'); });
pat1_1 = ".catch(function() { showToast('".encode("utf-8")
# This is tricky - find by the surrounding context
pat1 = b'.catch(function() { showToast('
idx = b.find(pat1, 5000)
if idx >= 0:
    end_q = b.find(b"'", idx + 30)
    end_brace = b.find(b"}", idx)
    if end_q >= 0 and end_brace >= 0:
        # Replace from the ( just before 'error'
        paren_start = b.rfind(b"(", 0, end_brace)
        if paren_start > idx:
            # Add console.error before showToast
            insert = b"console.error('convErr:', e); "
            old_catch = b".catch(function() { "
            new_catch = b".catch(function(e) { "
            if b[idx:idx+len(old_catch)] == old_catch:
                b[idx:idx+len(old_catch)] = new_catch
                b[idx+len(new_catch):idx+len(new_catch)] = insert
                print("Fixed loadConversation catch handler")
            else:
                print("Pattern mismatch at", idx)
                print(b[idx:idx+40])

with open(fp, "wb") as f:
    f.write(b)
print("Done")
