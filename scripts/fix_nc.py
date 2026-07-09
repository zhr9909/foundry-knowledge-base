import os

base = r"E:\AgentProjects\ai-solution-architect-lab\projects\foundry-knowledge-base"
fp = os.path.join(base, "app", "app.js")

with open(fp, "rb") as f:
    d = f.read()

# Fix 1: Replace DOMContentLoaded with direct registration
old1 = b'document.addEventListener("DOMContentLoaded",function(){var n=document.getElementById("newChatBtn");if(n)n.addEventListener("click",_nc)})'
new1 = b'var ncBtn=document.getElementById("newChatBtn");if(ncBtn)ncBtn.addEventListener("click",_nc)'
if old1 in d:
    d = d.replace(old1, new1)
    print("Fix 1: DOMContentLoaded -> direct registration")
else:
    print("Fix 1: Pattern not found - checking with single quotes")
    old1b = b"document.addEventListener('DOMContentLoaded',function(){var n=document.getElementById('newChatBtn');if(n)n.addEventListener('click',_nc)})"
    if old1b in d:
        d = d.replace(old1b, new1)
        print("Fix 1 applied (single quote version)")

# Fix 2: Add state.currentAssistantEl = null to _nc
old2 = b"state.history=[];_lca()"
new2 = b"state.currentAssistantEl=null;state.history=[];_lca()"
if old2 in d:
    d = d.replace(old2, new2)
    print("Fix 2: Added currentAssistantEl reset")
else:
    print("Fix 2: Pattern not found")
    # Debug
    i = d.find(b"state.history=[]")
    if i >= 0:
        print("  Found at", i, ":", d[i:i+30])

# Write
with open(fp, "wb") as f:
    f.write(d)

# Verify braces
print("Braces:", d.count(b"{"), d.count(b"}"))
