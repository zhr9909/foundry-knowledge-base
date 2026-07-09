import os

base = r"E:\AgentProjects\ai-solution-architect-lab\projects\foundry-knowledge-base"
fp = os.path.join(base, "app", "app.js")

with open(fp, "r", encoding="utf-8") as f:
    d = f.read()

# Fix 1: Add conv_id and token params
old1 = "if (state.history.length > 0) params.set('history', JSON.stringify(state.history.slice(-6)));"
new1 = old1 + "\n    if (_convId) params.set('conv_id', _convId);\n    if (authState.token) params.set('token', authState.token);"
if old1 in d:
    d = d.replace(old1, new1)
    print("Fix 1: Added params OK")
else:
    print("Fix 1: pattern not found")

# Fix 2: Add conv_id handler
old2 = "      hasData = true;\n\n      // --- Log events ---"
new2 = "      hasData = true;\n\n      // --- Conversation ID ---\n      if (data.type === 'conv_id' && data.conv_id) {\n        _convId = data.conv_id;\n        return;\n      }\n\n      // --- Log events ---"
if old2 in d:
    d = d.replace(old2, new2)
    print("Fix 2: Added conv_id handler OK")
else:
    print("Fix 2: pattern not found")

# Fix 3: Add _lca() after stream completes
old3 = "          state.history.push("
new3 = "          if (_convId) { _lca(); }\n          state.history.push("
# We need the LAST occurrence (inside sendMessageSSE)
count = d.count(old3)
print(f"Fix 3: Found {count} occurrences of pattern")
if count > 0:
    # Replace the last occurrence
    idx = d.rfind(old3)
    d = d[:idx] + new3 + d[idx+len(old3):]
    print("Fix 3: Added _lca call OK")
else:
    print("Fix 3: pattern not found")

with open(fp, "w", encoding="utf-8") as f:
    f.write(d)

# Verify
with open(fp, "rb") as f:
    raw = f.read()
opens = raw.count(b"{")
closes = raw.count(b"}")
print(f"Braces: {opens} = {closes} {'OK' if opens == closes else 'MISMATCH!'}")
print(f"Has conv_id handler: {b'conv_id' in raw}")
print(f"Has _lca after stream: {b'if (_convId) { _lca(); }' in raw}")
