import os

base = r"E:\AgentProjects\ai-solution-architect-lab\projects\foundry-knowledge-base"
fp = os.path.join(base, "app", "app.js")

with open(fp, "r", encoding="utf-8") as f:
    d = f.read()

# Find and remove the old fallback
old = "var _origLog = addLogEntry;\naddLogEntry = function(msg, lvl) {\n  var body, badge;\n  if (state.currentAssistantEl) {\n    body = state.currentAssistantEl.querySelector('.log-panel-body');\n    badge = state.currentAssistantEl.querySelector('.log-panel-badge');\n  }\n  if (!body) {\n    var ps = document.querySelectorAll('.log-panel-body');\n    if (ps.length > 0) body = ps[ps.length - 1];\n    var bs = document.querySelectorAll('.log-panel-badge');\n    if (bs.length > 0) badge = bs[bs.length - 1];\n  }\n  if (!body) return;\n  var now = new Date();\n  var time = now.toLocaleTimeString('zh-CN', { hour12: false });\n  var entry = document.createElement('div');\n  entry.className = 'log-entry';\n  entry.innerHTML = '<span class=\"log-time\">[' + time + ']</span><span class=\"log-msg\">' + escapeHtml(msg) + '</span>';\n  body.appendChild(entry);\n  body.scrollTop = body.scrollHeight;\n  if (badge) badge.textContent = body.children.length;\n};\n"

new = "var _origLog = addLogEntry;\naddLogEntry = function(msg, lvl) {\n  var body, badge;\n  if (state.currentAssistantEl) {\n    body = state.currentAssistantEl.querySelector('.log-panel-body');\n    badge = state.currentAssistantEl.querySelector('.log-panel-badge');\n  }\n  if (!body) {\n    var ps = document.querySelectorAll('.log-panel-body');\n    var bs = document.querySelectorAll('.log-panel-badge');\n    if (ps.length > 0) {\n      body = ps[ps.length - 1];\n      state.currentAssistantEl = body.closest('.message.assistant');\n    }\n    if (bs.length > 0) badge = bs[bs.length - 1];\n  }\n  if (!body || !_origLog) return;\n  _origLog(msg, lvl);\n};\n"

if old in d:
    d = d.replace(old, new)
    with open(fp, "w", encoding="utf-8") as f:
        f.write(d)
    print("Fixed: addLogEntry now calls original function")
else:
    print("Old pattern not found")
    i = d.find("var _origLog")
    if i >= 0:
        print("Found at", i)
        print(d[i:i+50])

# Verify
with open(fp, "rb") as f:
    raw = f.read()
print(f"Braces: {raw.count(b'{')} = {raw.count(b'}')}")
print(f"Has wrapper: {b'if (!body || !_origLog) return' in raw}")
