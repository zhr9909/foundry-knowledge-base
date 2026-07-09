import os

base = r"E:\AgentProjects\ai-solution-architect-lab\projects\foundry-knowledge-base"
fp = os.path.join(base, "app", "app.js")

with open(fp, "rb") as f:
    d = f.read()

lines = d.split(b"\n")
print("Total lines:", len(lines))

# Find the extra brace
for i, line in enumerate(lines):
    if line == b"}":
        next_line = lines[i+1] if i+1 < len(lines) else b""
        if next_line == b"":
            next2 = lines[i+2] if i+2 < len(lines) else b""
            if b"Listen" in next2:
                print("Found extra brace at line", i+1)
                print("Prev:", lines[i-1])
                print("This:", line)
                print("Next:", next_line)
                print("Next2:", next2)
                break
