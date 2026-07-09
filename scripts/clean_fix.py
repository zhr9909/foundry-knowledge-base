import os, subprocess

base = r"E:\AgentProjects\ai-solution-architect-lab\projects\foundry-knowledge-base"

# Step 1: Restore all three files from git
for f in ["app/app.js", "app/index.html", "app/style.css"]:
    r = subprocess.run(["git", "show", "64957d7:" + f], capture_output=True, cwd=base)
    with open(os.path.join(base, f), "wb") as fh:
        fh.write(r.stdout)

# Step 2: Add history section to HTML
with open(os.path.join(base, "app", "index.html"), "rb") as f:
    h = bytearray(f.read())

# Add after sidebar opening
old = b'<div class="sidebar-header">'
insert = b'<div class="sidebar-section" id="historySection" style="display:none">\n        <div class="sidebar-header" style="padding-top:12px;margin-top:8px">\n          <h3>\xe5\xaf\xb9\xe8\xaf\x9d\xe5\x8e\x86\xe5\x8f\xb2</h3>\n          <button class="btn-sm" id="newChatBtn">+ \xe6\x96\xb0\xe5\xbb\xba</button>\n        </div>\n        <div class="history-list" id="historyList"></div>\n        <div class="sidebar-divider"></div>\n      </div>\n      <div class="sidebar-header">'

idx = h.find(old)
if idx >= 0:
    h[idx:idx+len(old)] = insert.encode()
    h = h.replace(b"app.js?v=20260708", b"app.js?v=20260715")
    with open(os.path.join(base, "app", "index.html"), "wb") as f:
        f.write(h)
    print("HTML: patched")
else:
    print("HTML: pattern not found")

# Step 3: Add CSS
css_add = "\n/* History */\n.sidebar-section{padding:0 12px}\n.sidebar-divider{height:1px;background:var(--border);margin:8px 0}\n.history-list{max-height:300px;overflow-y:auto;margin-top:4px}\n.history-item{display:flex;align-items:center;padding:8px 10px;border-radius:8px;cursor:pointer;font-size:13px;color:var(--text-secondary);transition:all .15s;gap:6px}\n.history-item:hover{background:var(--bg-hover);color:var(--text-primary)}\n#newChatBtn{font-size:12px;padding:4px 10px;background:var(--accent);color:var(--bg-surface);border:none;border-radius:6px;cursor:pointer;font-weight:500}\n.history-empty{text-align:center;padding:20px;font-size:12px;color:var(--text-secondary)}\n"
with open(os.path.join(base, "app", "style.css"), "a", encoding="utf-8") as css:
    css.write(css_add)
print("CSS: patched")

# Step 4: Append JS code at the end
js_add = '''
var _convHist = [];
var _convId = null;

function loadConversations() {
    if (!authState.token) return;
    fetch("/api/conversations", { headers: {"Authorization": "Bearer " + authState.token} })
    .then(function(r){return r.json()})
    .then(function(d){_convHist = d.conversations || []; _renderConvList()})
    .catch(function(){});
}
function _renderConvList() {
    var list = document.getElementById("historyList");
    var sec = document.getElementById("historySection");
    if (!list || !sec) return;
    if (!authState.user) { sec.style.display = "none"; return; }
    sec.style.display = "block";
    if (_convHist.length === 0) { list.innerHTML = "<div class=\\\"history-empty\\">\\u6682\\u65e0\\u5bf9\\u8bdd\\u8bb0\\u5f55</div>"; return; }
    var h = "";
    for (var i = 0; i < _convHist.length; i++) {
        var c = _convHist[i];
        var t = c.title || "\\u65b0\\u5bf9\\u8bdd";
        var a = _convId === c.id ? " active" : "";
        h += "<div class=\\"history-item" + a + "\\" data-id=\\"" + c.id + "\\">"
            + "<span class=\\"history-item-title\\">" + t.replace(/</g, "&lt;") + "</span>"
            + "</div>";
    }
    list.innerHTML = h;
    Array.from(list.querySelectorAll(".history-item")).forEach(function(el) {
        el.addEventListener("click", function() { _loadConversation(parseInt(this.dataset.id)); });
    });
}
function _loadConversation(id) {
    if (!authState.token) return;
    fetch("/api/conversations/" + id, { headers: {"Authorization": "Bearer " + authState.token} })
    .then(function(r){return r.json()})
    .then(function(d){
        var conv = d.conversation;
        if (!conv) return;
        _convId = conv.id;
        var wel = document.getElementById("welcome");
        var msgs = document.getElementById("messages");
        if (wel) wel.style.display = "none";
        if (msgs) { msgs.style.display = "block"; msgs.innerHTML = ""; }
        state.history = [];
        for (var i = 0; i < conv.messages.length; i++) {
            var m = conv.messages[i];
            if (m.role === "user") {
                addUserMessage(m.content);
                state.history.push({role:"user",content:m.content});
            } else if (m.role === "assistant") {
                var cites = (m.metadata && m.metadata.citations) || [];
                addAssistantMessage(m.content, cites);
                state.history.push({role:"assistant",content:m.content, citations:cites});
            }
        }
        _renderConvList();
    })
    .catch(function(){window.showToast("\\u52a0\\u8f7d\\u5bf9\\u8bdd\\u5931\\u8d25","error")});
}
function _newConversation() {
    if (!authState.token) return;
    fetch("/api/conversations", { method:"POST", headers: {"Authorization": "Bearer " + authState.token} })
    .then(function(r){return r.json()})
    .then(function(d){
        _convId = d.conversation ? d.conversation.id : null;
        var wel = document.getElementById("welcome");
        var msgs = document.getElementById("messages");
        if (wel) wel.style.display = "block";
        if (msgs) { msgs.style.display = "none"; msgs.innerHTML = ""; }
        state.history = [];
        document.getElementById("progressSteps").innerHTML = "";
        loadConversations();
    })
    .catch(function(){window.showToast("\\u521b\\u5efa\\u5bf9\\u8bdd\\u5931\\u8d25","error")});
}
// Hook into auth
var _origUpd = window.updateAuthUI;
window.updateAuthUI = function() {
    _origUpd.apply(this, arguments);
    if (authState.user) { loadConversations(); }
    else { var s = document.getElementById("historySection"); if (s) s.style.display = "none"; }
};
// Create conversation before send if logged in
document.addEventListener("DOMContentLoaded", function() {
    var sb = document.getElementById("sendBtn");
    if (sb && authState.token) {
        sb.addEventListener("click", function(e) {
            if (authState.token && !_convId) {
                e.stopImmediatePropagation();
                var q = document.getElementById("queryInput");
                var qv = q ? q.value : "";
                fetch("/api/conversations", { method:"POST", headers:{"Authorization":"Bearer "+authState.token} })
                .then(function(r){return r.json()})
                .then(function(d){
                    _convId = d.conversation ? d.conversation.id : null;
                    if (qv && q) { q.value = qv; sendMessage(); }
                })
                .catch(function(){});
            }
        });
    }
    var nb = document.getElementById("newChatBtn");
    if (nb) nb.addEventListener("click", _newConversation);
});
// Periodically save messages
var _lastLen = 0;
setInterval(function() {
    if (!_convId || !authState.token || state.history.length <= _lastLen) return;
    var newMsgs = state.history.slice(_lastLen);
    _lastLen = state.history.length;
    for (var i = 0; i < newMsgs.length; i++) {
        (function(msg) {
            fetch("/api/conversations/" + _convId + "/messages", {
                method:"POST",
                headers:{"Content-Type":"application/json","Authorization":"Bearer "+authState.token},
                body:JSON.stringify({role:msg.role, content:typeof msg.content === "string" ? msg.content : ""})
            }).catch(function(){});
        })(newMsgs[i]);
    }
}, 3000);
'''

with open(os.path.join(base, "app", "app.js"), "a", encoding="utf-8") as js:
    js.write(js_add)
print("JS: appended")

# Verify
with open(os.path.join(base, "app", "app.js"), "rb") as f:
    d = f.read()
opens = d.count(b"{")
closes = d.count(b"}")
print("Braces: open=%d close=%d %s" % (opens, closes, "OK" if opens == closes else "MISMATCH!"))
print("Done!")
