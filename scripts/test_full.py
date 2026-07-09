from playwright.sync_api import sync_playwright
import os, json, urllib.request

base = r"E:\AgentProjects\ai-solution-architect-lab\projects\foundry-knowledge-base"

# Register test user
data = json.dumps({"email":"t10@test.com","username":"t10","password":"test123456"}).encode()
req = urllib.request.Request("http://127.0.0.1:8000/api/auth/register", data=data, headers={"Content-Type":"application/json"})
resp = urllib.request.urlopen(req, timeout=5)
tok = json.loads(resp.read())["token"]
print("Token obtained")

with sync_playwright() as p:
    browser = p.chromium.launch()
    page = browser.new_page()
    errors = []
    page.on("pageerror", lambda err: errors.append(str(err)))
    
    page.goto("http://127.0.0.1:8000/static/index.html", wait_until="load", timeout=5000)
    
    # Login
    page.evaluate("localStorage.setItem('auth_token', '" + tok + "')")
    page.reload(wait_until="load", timeout=10000)
    page.wait_for_timeout(1000)
    
    # Click new chat
    page.evaluate("document.getElementById('newChatBtn').click()")
    page.wait_for_timeout(500)
    
    # Send a message
    page.fill("#queryInput", "铝合金6061的力学性能")
    page.click("#sendBtn")
    
    # Wait for completion
    page.wait_for_timeout(15000)
    
    # Check result
    msgs = page.evaluate("document.getElementById('messages')?.children.length || 0")
    wel = page.evaluate("document.getElementById('welcome')?.style.display || '?'")
    steps = page.evaluate("document.getElementById('progressSteps')?.children.length || 0")
    page.screenshot(path=os.path.join(base, "app", "debug4.png"))
    
    print("Messages:", msgs)
    print("Welcome:", wel)
    print("Progress steps:", steps)
    print("Errors:", len(errors))
    for e in errors[:5]:
        print("  %s" % e[:200])
    
    browser.close()
