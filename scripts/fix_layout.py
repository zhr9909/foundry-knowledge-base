import os

base = r"E:\AgentProjects\ai-solution-architect-lab\projects\foundry-knowledge-base"

# Fix: Add id="inputArea" to the HTML
html_path = os.path.join(base, "app", "index.html")
with open(html_path, "rb") as f:
    d = f.read()

old = b'class="input-area">\r\n        <div class="section-indicator"'
new = b'class="input-area" id="inputArea">\r\n        <div class="section-indicator"'
if old in d:
    d = d.replace(old, new)
    with open(html_path, "wb") as f:
        f.write(d)
    print("Added id=inputArea to HTML - OK")
else:
    print("Pattern NOT FOUND")
    print("Looking for:", old)
    i = d.find(b'class="input-area"')
    if i >= 0:
        print("Found at", i, ":", d[i:i+60])
