import os

base = r"E:\AgentProjects\ai-solution-architect-lab\projects\foundry-knowledge-base"
fp = os.path.join(base, "app", "app.js")

with open(fp, "r", encoding="utf-8") as f:
    d = f.read()

# Append fallback log function  
add = """

// Fix: addLogEntry with fallback
var _origLog = addLogEntry;
addLogEntry = function(msg, lvl) {
  var body, badge;
  if (state.currentAssistantEl) {
    body = state.currentAssistantEl.querySelector('.log-panel-body');
    badge = state.currentAssistantEl.querySelector('.log-panel-badge');
  }
  if (!body) {
    var ps = document.querySelectorAll('.log-panel-body');
    if (ps.length > 0) body = ps[ps.length - 1];
    var bs = document.querySelectorAll('.log-panel-badge');
    if (bs.length > 0) badge = bs[bs.length - 1];
  }
  if (!body) return;
  var now = new Date();
  var time = now.toLocaleTimeString('zh-CN', { hour12: false });
  var entry = document.createElement('div');
  entry.className = 'log-entry';
  entry.innerHTML = '<span class="log-time">[' + time + ']</span><span class="log-msg">' + escapeHtml(msg) + '</span>';
  body.appendChild(entry);
  body.scrollTop = body.scrollHeight;
  if (badge) badge.textContent = body.children.length;
};
"""

d += add

with open(fp, "w", encoding="utf-8") as f:
    f.write(d)

# Verify
with open(fp, "rb") as f:
    raw = f.read()
opens = raw.count(b"{")
closes = raw.count(b"}")
print(f"Braces: {opens} = {closes} {'OK' if opens == closes else 'MISMATCH!'}")
print(f"Has _origLog: {b'_origLog' in raw}")
print(f"Has fallback: {b'if (!body)' in raw}")
