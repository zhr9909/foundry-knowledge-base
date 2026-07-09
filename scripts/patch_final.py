import os, subprocess

base = r"E:\AgentProjects\ai-solution-architect-lab\projects\foundry-knowledge-base"

# Restore files from git
for f in ["app/index.html", "app/app.js"]:
    r = subprocess.run(["git", "show", "64957d7:" + f], capture_output=True, cwd=base)
    path = os.path.join(base, f)
    # Verify content by checking encoding
    with open(path, "wb") as fh:
        fh.write(r.stdout)
    print("Restored:", f, len(r.stdout), "bytes")

# Patch HTML: add history section
path = os.path.join(base, "app", "index.html")
with open(path, "rb") as f:
    data = bytearray(f.read())

marker = b'<div class="sidebar-header">'
insert = bytearray()
insert.extend(b'<div class="sidebar-section" id="historySection" style="display:none">')
insert.extend(b'<div class="sidebar-header" style="padding-top:12px;margin-top:8px">')
insert.extend(b'<h3>')
insert.extend("对话历史".encode("utf-8"))
insert.extend(b'</h3>')
insert.extend(b'<button class="btn-sm" id="newChatBtn">+ ')
insert.extend("新建".encode("utf-8"))
insert.extend(b'</button></div>')
insert.extend(b'<div class="history-list" id="historyList"></div>')
insert.extend(b'<div class="sidebar-divider"></div></div>')
insert.extend(marker)

idx = data.find(marker)
if idx >= 0:
    data[idx:idx+len(marker)] = insert
    data = data.replace(b"app.js?v=20260708", b"app.js?v=20260718")
    with open(path, "wb") as f:
        f.write(data)
    print("HTML patched:", len(data), "bytes")
else:
    print("ERROR: marker not found")

# Verify encoding
with open(path, "rb") as f:
    d = f.read(100)
print("First bytes:", d[:30].hex())
