import os, subprocess

base = r"E:\AgentProjects\ai-solution-architect-lab\projects\foundry-knowledge-base"

# Step 1: Restore all files from git
for fname in ["app/app.js", "app/index.html", "app/style.css"]:
    p = subprocess.run(["git", "show", "64957d7:" + fname], capture_output=True, cwd=base)
    with open(os.path.join(base, fname), "wb") as f:
        f.write(p.stdout)
    print("Restored:", fname, len(p.stdout), "bytes")

# Step 2: Verify index.html
with open(os.path.join(base, "app", "index.html"), "rb") as f:
    html = bytearray(f.read())
print("index.html has queryInput:", b"queryInput" in html)
print("index.html has sendBtn:", b"sendBtn" in html)

# Step 3: Add history section to sidebar
old = b'class="sidebar-header">\n        <h3'
new = b'class="sidebar-section" id="historySection" style="display:none">\n        <div class="sidebar-header" style="padding-top:12px;margin-top:8px">\n          <h3>\xe5\xaf\xb9\xe8\xaf\x9d\xe5\x8e\x86\xe5\x8f\xb2</h3>\n          <button class="btn-sm" id="newChatBtn">+ \xe6\x96\xb0\xe5\xbb\xba</button>\n        </div>\n        <div class="history-list" id="historyList"></div>\n        <div class="sidebar-divider"></div>\n      </div>\n      <div class="sidebar-header">\n        <h3'
html = html.replace(old, new, 1)
print("History section added")

# Step 4: Add id to input-area
html = html.replace(b'class="input-area">', b'class="input-area" id="inputArea">', 1)
print("inputArea id added")

# Step 5: Update version
html = html.replace(b'app.js?v=20260708', b'app.js?v=20260712')
print("Version updated")

with open(os.path.join(base, "app", "index.html"), "wb") as f:
    f.write(html)

# Step 6: Add CSS for history
with open(os.path.join(base, "app", "style.css"), "a", encoding="utf-8") as css:
    css.write("\n\n/* ===== Conversation History ===== */\n")
    css.write(".sidebar-section{padding:0 12px}\n")
    css.write(".sidebar-divider{height:1px;background:var(--border);margin:8px 0}\n")
    css.write(".history-list{max-height:300px;overflow-y:auto;margin-top:4px}\n")
    css.write(".history-item{display:flex;align-items:center;padding:8px 10px;border-radius:8px;cursor:pointer;font-size:13px;color:var(--text-secondary);transition:all .15s;gap:6px}\n")
    css.write(".history-item:hover{background:var(--bg-hover);color:var(--text-primary)}\n")
    css.write("#newChatBtn{font-size:12px;padding:4px 10px;background:var(--accent);color:var(--bg-surface);border:none;border-radius:6px;cursor:pointer;font-weight:500}\n")
    css.write(".history-empty{text-align:center;padding:20px;font-size:12px;color:var(--text-secondary)}\n")
print("CSS added")

print("\nAll done!")
