import os

base = r"E:/AgentProjects/ai-solution-architect-lab/projects/foundry-knowledge-base"
fp = os.path.join(base, "app", "app.js")

with open(fp, "rb") as f:
    raw = bytearray(f.read())

changes = []

# 1) URL token login - add loadConversations()
# Pattern: showToast("\u767b\u5f55\u6210\u529f"); }
pattern1 = b'showToast("\\u767b\\u5f55\\u6210\\u529f"); }'
idx1 = raw.find(pattern1)
if idx1 >= 0:
    # Replace with: showToast("\u767b\u5f55\u6210\u529f"); loadConversations(); }
    replacement1 = b'showToast("\\u767b\\u5f55\\u6210\\u529f"); loadConversations(); }'
    raw[idx1:idx1+len(pattern1)] = replacement1
    changes.append("URL token login: added loadConversations()")
else:
    changes.append("URL token login: pattern NOT FOUND")

# 2) History refresh after stream completion
# Pattern: // Update history\n          state.history.push(
pattern2 = b'// Update history\r\n          state.history.push('
idx2 = raw.find(pattern2)
if idx2 >= 0:
    refresh_code = b'// Update history\r\n          if (authState.token) {\r\n            fetch("/api/conversations", { headers: { "Authorization": "Bearer " + authState.token } })\r\n              .then(function(r) { return r.json(); }).then(function(d) {\r\n                state.conversationHistory = d.conversations || [];\r\n                renderConversations();\r\n              }).catch(function() {});\r\n          }\r\n          state.history.push('
    raw[idx2:idx2+len(pattern2)] = refresh_code
    changes.append("History refresh: added after stream completion")
else:
    changes.append("History refresh: pattern NOT FOUND")

# Write back
with open(fp, "wb") as f:
    f.write(raw)

for c in changes:
    print(c)
