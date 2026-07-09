import os

base = r"E:\AgentProjects\ai-solution-architect-lab\projects\foundry-knowledge-base"
js_file = os.path.join(base, "app", "app.js")

# Read the current app.js
with open(js_file, "rb") as f:
    b = bytearray(f.read())

# Add currentConvId to state
old = b"currentAssistantEl: null"
new = b"currentAssistantEl: null, currentConvId: null"
if old in b:
    b = b.replace(old, new, 1)
    print("Added currentConvId to state")
else:
    print("Could not find currentAssistantEl pattern")

# Append conversation history code
append_code = """

// ===== Conversation History =====
var _convHistory = [];
function loadConversations() {
    if (!authState.token) return;
    fetch('/api/conversations', { headers: { 'Authorization': 'Bearer ' + authState.token } })
    .then(function(r){return r.json()})
    .then(function(d){_convHistory = d.conversations || []; _renderConvList()})
    .catch(function(){});
}
function _renderConvList() {
    var list = document.getElementById('historyList');
    var sec = document.getElementById('historySection');
    if (!list || !sec) return;
    if (!authState.user) { sec.style.display = 'none'; return; }
    sec.style.display = 'block';
    if (_convHistory.length === 0) { list.innerHTML = '<div class="history-empty">暂无对话记录</div>'; return; }
    var h = '';
    for (var i = 0; i < _convHistory.length; i++) {
        var c = _convHistory[i];
        var t = c.title || '\u65b0\u5bf9\u8bdd';
        var a = state.currentConvId === c.id ? ' active' : '';
        h += '<div class="history-item' + a + '" data-id="' + c.id + '">'
            + '<span class="history-item-title">' + t.replace(/</g,'&lt;') + '</span>'
            + '</div>';
    }
    list.innerHTML = h;
    // Click handlers
    Array.from(list.querySelectorAll('.history-item')).forEach(function(el) {
        el.addEventListener('click', function() { _loadConversation(parseInt(this.dataset.id)); });
    });
}
function _loadConversation(id) {
    if (!authState.token) return;
    fetch('/api/conversations/' + id, { headers: { 'Authorization': 'Bearer ' + authState.token } })
    .then(function(r){return r.json()})
    .then(function(d){
        var conv = d.conversation;
        if (!conv) return;
        state.currentConvId = conv.id;
        document.getElementById('welcome').style.display = 'none';
        var msgs = document.getElementById('messages');
        msgs.style.display = 'block';
        msgs.innerHTML = '';
        state.history = [];
        for (var i = 0; i < conv.messages.length; i++) {
            var m = conv.messages[i];
            if (m.role === 'user') {
                addUserMessage(m.content);
                state.history.push({role:'user',content:m.content});
            } else if (m.role === 'assistant') {
                var cites = (m.metadata && m.metadata.citations) || [];
                addAssistantMessage(m.content, cites);
                state.history.push({role:'assistant',content:m.content, citations:cites});
            }
        }
        _renderConvList();
    })
    .catch(function(){ showToast('\u52a0\u8f7d\u5bf9\u8bdd\u5931\u8d25', 'error'); });
}
function _newConversation() {
    if (!authState.token) return;
    fetch('/api/conversations', { method: 'POST', headers: { 'Authorization': 'Bearer ' + authState.token } })
    .then(function(r){return r.json()})
    .then(function(d){
        state.currentConvId = d.conversation ? d.conversation.id : null;
        document.getElementById('welcome').style.display = 'block';
        document.getElementById('messages').style.display = 'none';
        document.getElementById('messages').innerHTML = '';
        state.history = [];
        loadConversations();
    })
    .catch(function(){ showToast('\u521b\u5efa\u5bf9\u8bdd\u5931\u8d25', 'error'); });
}

// Hook into updateAuthUI
var _origUpd = window.updateAuthUI;
window.updateAuthUI = function() {
    _origUpd.apply(this, arguments);
    if (authState.user) { loadConversations(); }
    else { var s=document.getElementById('historySection'); if(s) s.style.display='none'; }
};

// Create conversation before sending if logged in
var _sendBtnObs = document.getElementById('sendBtn');
if (_sendBtnObs) {
    _sendBtnObs.addEventListener('click', function() {
        if (authState.token && !state.currentConvId) {
            fetch('/api/conversations', { method:'POST', headers:{'Authorization':'Bearer '+authState.token} })
            .then(function(r){return r.json()})
            .then(function(d){ state.currentConvId = d.conversation ? d.conversation.id : null; })
            .catch(function(){});
        }
    });
}

// Listen for new chat button
document.addEventListener('DOMContentLoaded', function() {
    var nb = document.getElementById('newChatBtn');
    if (nb) nb.addEventListener('click', _newConversation);
    var hl = document.getElementById('historyList');
    if (hl) {
        hl.addEventListener('click', function(e) {
            var item = e.target.closest('.history-item');
            if (item) { _loadConversation(parseInt(item.dataset.id)); }
        });
    }
});

// Track and save messages
var _lastHistLen = 0;
function _saveLatestMsgs() {
    if (!state.currentConvId || !authState.token || state.history.length <= _lastHistLen) return;
    var newMsgs = state.history.slice(_lastHistLen);
    _lastHistLen = state.history.length;
    for (var i = 0; i < newMsgs.length; i++) {
        (function(msg) {
            fetch('/api/conversations/' + state.currentConvId + '/messages', {
                method:'POST',
                headers:{'Content-Type':'application/json','Authorization':'Bearer '+authState.token},
                body:JSON.stringify({role:msg.role, content:msg.content})
            }).catch(function(){});
        })(newMsgs[i]);
    }
}
setInterval(_saveLatestMsgs, 2000);
"""

b.extend(append_code.encode("utf-8"))

with open(js_file, "wb") as f:
    f.write(b)
print("Conversation history code appended")
print("Total size:", len(b), "bytes")
