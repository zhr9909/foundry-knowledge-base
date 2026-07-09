import os

base = r"E:\AgentProjects\ai-solution-architect-lab\projects\foundry-knowledge-base"
fp = os.path.join(base, "app", "app.js")

with open(fp, "r", encoding="utf-8") as f:
    d = f.read()

# Fix 1: Remove fetch from _nc - just reset state, don't create conversation
old_nc = "function _nc(){if(!authState.token)return;fetch('/api/conversations',{method:'POST',headers:{'Authorization':'Bearer '+authState.token}}).then(function(r){return r.json()}).then(function(d){_convId=d.conversation?d.conversation.id:null;var w=document.getElementById('welcome');var m=document.getElementById('messages');if(w)w.style.display='';if(m)m.innerHTML='';state.currentAssistantEl=null;state.history=[];_lca()}).catch(function(){showToast('\u521b\u5efa\u5931\u8d25','error')})}"
new_nc = "function _nc(){if(!authState.token)return;_convId=null;var w=document.getElementById('welcome');var m=document.getElementById('messages');if(w)w.style.display='';if(m)m.innerHTML='';state.currentAssistantEl=null;state.history=[];_lca()}"
if old_nc in d:
    d = d.replace(old_nc, new_nc)
    print("Fix 1: _nc simplified - no fetch")
else:
    print("Fix 1: _nc pattern not found")
    # Debug: find _nc
    i = d.find("function _nc")
    if i >= 0:
        print("  Current _nc:", d[i:i+400])

# Fix 2: Update sendBtn handler to update title and refresh
old_sb = "if (authState.token && !_convId) {\n            e.stopImmediatePropagation();\n            var q = document.getElementById('queryInput');\n            var qv = q ? q.value : '';\n            fetch('/api/conversations', { method:'POST', headers:{'Authorization':'Bearer ' + authState.token} })\n            .then(function(r){return r.json()})\n            .then(function(d){\n                state.currentConvId = d.conversation ? d.conversation.id : null;\n                if (qv && q) { q.value = qv; sendMessage(); }\n            })\n            .catch(function(){});\n        }"
new_sb = "if (authState.token && !_convId) {\n            e.stopImmediatePropagation();\n            var q = document.getElementById('queryInput');\n            var qv = q ? q.value : '';\n            fetch('/api/conversations', { method:'POST', headers:{'Authorization':'Bearer ' + authState.token} })\n            .then(function(r){return r.json()})\n            .then(function(d){\n                _convId = d.conversation ? d.conversation.id : null;\n                if (_convId && qv) {\n                    fetch('/api/conversations/' + _convId, { method:'PUT', headers:{'Content-Type':'application/json','Authorization':'Bearer ' + authState.token}, body:JSON.stringify({title:qv}) }).catch(function(){});\n                }\n                if (qv && q) { q.value = qv; sendMessage(); }\n                setTimeout(function() { _lca(); }, 3000);\n            })\n            .catch(function(){});\n        }"
if old_sb in d:
    d = d.replace(old_sb, new_sb)
    print("Fix 2: sendBtn handler updated")
else:
    print("Fix 2: sendBtn pattern not found")

# Write back
with open(fp, "w", encoding="utf-8") as f:
    f.write(d)

# Verify braces
with open(fp, "rb") as f:
    raw = f.read()
print("Braces:", raw.count(b"{"), raw.count(b"}'"))
