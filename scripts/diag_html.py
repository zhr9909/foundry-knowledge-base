import os

base = r"E:\AgentProjects\ai-solution-architect-lab\projects\foundry-knowledge-base"

# Check what the actual pattern is around input-area
html_path = os.path.join(base, "app", "index.html")
with open(html_path, "rb") as f:
    d = f.read()

# Search for "input-area" (without class assignment)
i = d.find(b"input-area")
if i >= 0:
    print("input-area found at", i)
    print("Context:", d[i-30:i+60])
else:
    print("input-area NOT FOUND")
    # Search for "input-wrapper"
    i2 = d.find(b"input-wrapper")
    if i2 >= 0:
        print("input-wrapper found at", i2)
        print("Context:", d[i2-50:i2+30])
