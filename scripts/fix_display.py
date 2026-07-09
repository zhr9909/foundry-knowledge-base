import os

base = r"E:\AgentProjects\ai-solution-architect-lab\projects\foundry-knowledge-base"
fp = os.path.join(base, "app", "app.js")

with open(fp, "rb") as f:
    d = f.read()

# The issue: w.style.display='block' overrides CSS flex layout
# Fix: change to empty string so CSS default applies
replacements = [
    (b"w.style.display='block'", b"w.style.display=''"),
]

for old, new in replacements:
    if old in d:
        d = d.replace(old, new)
        print("Fixed:", old)

with open(fp, "wb") as f:
    f.write(d)

print("Braces:", d.count(b"{"), d.count(b"}"))
