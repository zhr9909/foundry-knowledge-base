import os

base = r"E:\AgentProjects\ai-solution-architect-lab\projects\foundry-knowledge-base"
js_path = os.path.join(base, "app", "app.js")

with open(js_path, "rb") as f:
    d = f.read()

# Fix loadConversation error handling - add console error logging
# Find the .catch in loadConversation
old = b'.catch(function() { showToast(\"' 
# Check if specific pattern exists
patterns = [
    (b'.catch(function() { showToast(\xboste\xb0\xd7\xbb\xb0\xca\xa7\xb0\xdc', b'.catch(function(e) { console.error("loadConv error:", e); showToast(\xboste\xb0\xd7\xbb\xb0\xca\xa7\xb0\xdc'),
]
# Actually let me just check what the catch looks like
i = d.find(b"loadConversation")
if i >= 0:
    # Find the .catch
    j = d.find(b".catch", i)
    if j >= 0:
        k = d.find(b"function()", j)
        if k >= 0:
            print("Current catch at", k, ":")
            print(d[k:k+80])
        else:
            print("Could not find function() after .catch")
