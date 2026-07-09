import os

base = r"E:\AgentProjects\ai-solution-architect-lab\projects\foundry-knowledge-base"
fp = os.path.join(base, "app", "app.js")

with open(fp, "rb") as f:
    d = bytearray(f.read())

# Find the sendBtn handler section
marker = b"if (_sendBtnObs) {"
idx = d.find(marker)
if idx >= 0:
    # Find the end of this block
    end = d.find(b"\n}\n", idx)
    if end >= 0:
        old_block = d[idx:end+1]
        
        # Build new block (avoiding single quotes by using hex)
        new_block = b"if (_sendBtnObs) {\n    _sendBtnObs.addEventListener('click', function(e) {\n        if (authState.token && !state.currentConvId) {\n            e.stopImmediatePropagation();\n            var q = document.getElementById('queryInput');\n            var qv = q ? q.value : '';\n            fetch('/api/conversations', { method:'POST', headers:{'Authorization':'Bearer ' + authState.token} })\n            .then(function(r){return r.json()})\n            .then(function(d){\n                state.currentConvId = d.conversation ? d.conversation.id : null;\n                if (qv && q) { q.value = qv; sendMessage(); }\n            })\n            .catch(function(){});\n        }\n    });\n}"
        
        d[idx:end+1] = new_block
        
        with open(fp, "wb") as f:
            f.write(d)
        
        print("Fixed sendBtn handler to use stopImmediatePropagation")
    else:
        print("Could not find end of sendBtn block")
else:
    print("Could not find sendBtn marker")
