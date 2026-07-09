from playwright.sync_api import sync_playwright
import os, json, urllib.request

base = r"E:\AgentProjects\ai-solution-architect-lab\projects\foundry-knowledge-base"

# Register test user
data = json.dumps({"email":"hist2@test.com","username":"hist2","password":"test123456"}).encode()
req = urllib.request.Request("http://127.0.0.1:8000/api/auth/register", data=data, headers={"Content-Type":"application/json"})
resp = urllib.request.urlopen(req, timeout=5)
tok = json.loads(resp.read())["token"]

with sync_playwright() as p:
    browser = p.chromium.launch()
    page = browser.new_page()
    errors = []
    page.on("pageerror", lambda err: errors.append(str(err)))
    
    page.goto("http://127.0.0.1:8000/static/index.html", wait_until="load", timeout=5000)
    page.evaluate("localStorage.setItem('auth_token', '" + tok + "')")
    page.reload(wait_until="load", timeout=5000)
    page.wait_for_timeout(1000)
    
    # Send first message to create conversation
    page.fill("#queryInput", "铝合金6061")
    page.click("#sendBtn")
    page.wait_for_timeout(15000)
    
    # Check progress steps
    steps = page.evaluate("document.getElementById('progressSteps')?.querySelectorAll('.step').length || 0")
    # Check log entries
    logs = page.evaluate("document.querySelector('.log-panel-body')?.children.length || 0")
    # Check messages
    msgs = page.evaluate("document.getElementById('messages')?.children.length || 0")
    print("After first msg - Steps:", steps, "Logs:", logs, "Msgs:", msgs)
    
    # Load conversation from history
    page.evaluate("document.querySelector('.history-item')?.click()")
    page.wait_for_timeout(1000)
    
    # Send another message
    page.fill("#queryInput", "抗拉强度是多少")
    page.click("#sendBtn")
    page.wait_for_timeout(15000)
    
    # Check again
    steps2 = page.evaluate("document.querySelectorAll('.step').length || 0")
    steps_container = page.evaluate("document.getElementById('progressSteps')?.style.display || '?'")
    logs2 = page.evaluate("document.querySelector('.log-panel-body')?.children.length || 0")
    msgs2 = page.evaluate("document.getElementById('messages')?.children.length || 0")
    print("After second msg - Steps:", steps2, "Container:", steps_container, "Logs:", logs2, "Msgs:", msgs2)
    
    page.screenshot(path=os.path.join(base, "app", "debug6.png"))
    print("Errors:", len(errors))
    for e in errors[:3]: print("  %s" % e[:200])
    browser.close()
