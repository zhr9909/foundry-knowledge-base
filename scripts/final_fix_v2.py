import os

base = r"E:\AgentProjects\ai-solution-architect-lab\projects\foundry-knowledge-base"

# Fix 1: Add id="inputArea" to input-area div in HTML
html_path = os.path.join(base, "app", "index.html")
with open(html_path, "rb") as f:
    d = f.read()

old = b'class="input-area">\r\n        <div class="input-wrapper">'
new = b'class="input-area" id="inputArea">\r\n        <div class="input-wrapper">'
if old in d:
    d = d.replace(old, new)
    with open(html_path, "wb") as f:
        f.write(d)
    print("Added id=inputArea to HTML")
else:
    print("WARNING: Could not find input-area in HTML")

# Fix 2: Fix newConversation to not reference inputArea
js_path = os.path.join(base, "app", "app.js")
with open(js_path, "rb") as f:
    d = f.read()

# Remove inputArea reference from newConversation
old_js = b"var welcomeEl = document.getElementById('welcome');\r\n    var messagesEl = document.getElementById('messages');\r\n    var inputArea = document.getElementById('inputArea');\r\n    \r\n    if (welcomeEl) welcomeEl.style.display = 'block';\r\n    if (messagesEl) {\r\n      messagesEl.style.display = 'none';\r\n      messagesEl.innerHTML = '';\r\n    }\r\n    if (inputArea) inputArea.style.display = 'none';"
new_js = b"var welcomeEl = document.getElementById('welcome');\r\n    var messagesEl = document.getElementById('messages');\r\n    \r\n    if (welcomeEl) welcomeEl.style.display = 'block';\r\n    if (messagesEl) {\r\n      messagesEl.style.display = 'none';\r\n      messagesEl.innerHTML = '';\r\n    }"
if old_js in d:
    d = d.replace(old_js, new_js)
    with open(js_path, "wb") as f:
        f.write(d)
    print("Fixed newConversation in app.js")
else:
    print("WARNING: Could not find newConversation pattern in app.js")

# Fix 3: Clean residual patch scripts
for fname in ["patch_phase1.py", "patch_phase2.py", "patch_phase3.py", "patch_phase4.py", "patch_phase5.py", "fix_appjs.py", "fix_html.py", "fix_chinese.py", "fix_sql.py", "fix_sql2.py"]:
    fp = os.path.join(base, "scripts", fname)
    if os.path.exists(fp):
        os.remove(fp)
        print("Cleaned up:", fname)
