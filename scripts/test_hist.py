from playwright.sync_api import sync_playwright
import os, json, urllib.request

base = r"E:\AgentProjects\ai-solution-architect-lab\projects\foundry-knowledge-base"

# Register user
data = json.dumps({"email":"hist@test.com","username":"hist","password":"test123456"}).encode()
req = urllib.request.Request("http://127.0.0.1:8000/api/auth/register", data=data, headers={"Content-Type":"application/json"})
resp = urllib.request.urlopen(req, timeout=5)
tok = json.loads(resp.read())["token"]
print("Token:", tok[:30])

with sync_playwright() as p:
    browser = p.chromium.launch()
    page = browser.new_page()
    errors = []
    page.on("pageerror", lambda err: errors.append(str(err)))
    
    page.goto("http://127.0.0.1:8000/static/index.html", wait_until="load", timeout=5000)
    page.evaluate("localStorage.setItem('auth_token', '" + tok + "')")
    page.reload(wait_until="load", timeout=5000)
    page.wait_for_timeout(1000)
    
    # Send a message to create a conversation
    page.fill("#queryInput", "铝合金6061的力学性能")
    page.click("#sendBtn")
    page.wait_for_timeout(20000)  # Wait for streaming
    
    # Check conversations
    convs = page.evaluate("_convHist.length")
    print("Conversations:", convs)
    
    if convs > 0:
        # Click first history item
        first_id = page.evaluate("_convHist[0].id")
        title = page.evaluate("_convHist[0].title")
        print("First conv id:", first_id, "title:", title)
        
        # Click it
        page.evaluate("document.querySelector('.history-item').click()")
        page.wait_for_timeout(1000)
        
        # Check if messages were loaded
        msgs = page.evaluate("document.getElementById('messages')?.children.length || 0")
        print("Messages loaded:", msgs)
    
    page.screenshot(path=os.path.join(base, "app", "debug5.png"))
    print("Errors:", len(errors))
    for e in errors[:3]: print("  %s" % e[:150])
    browser.close()
