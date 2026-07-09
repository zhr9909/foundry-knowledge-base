from playwright.sync_api import sync_playwright
import os, json, urllib.request

base = r"E:\AgentProjects\ai-solution-architect-lab\projects\foundry-knowledge-base"

# Register a test user
data = json.dumps({"email":"pwtest2@test.com","username":"pwtest2","password":"test123456"}).encode()
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
    
    # Login
    page.evaluate("localStorage.setItem('auth_token', '" + tok + "'); location.reload()")
    page.wait_for_load_state("load", timeout=5000)
    page.wait_for_timeout(1000)
    
    # Check state
    hist_sec = page.evaluate("document.getElementById('historySection')?.style.display || 'missing'")
    btn = page.evaluate("document.getElementById('newChatBtn') ? 'exists' : 'missing'")
    welcome = page.evaluate("document.getElementById('welcome')?.style.display || 'missing'")
    print("History:", hist_sec, "Btn:", btn, "Welcome:", welcome)
    
    # Click new chat
    page.evaluate("document.getElementById('newChatBtn').click()")
    page.wait_for_timeout(1000)
    
    # Check welcome after click
    welcome2 = page.evaluate("document.getElementById('welcome')?.style.display || 'missing'")
    print("Welcome after new:", welcome2)
    
    # Send message
    page.evaluate("document.getElementById('queryInput').value='test message'")
    page.evaluate("document.getElementById('sendBtn').click()")
    page.wait_for_timeout(3000)
    
    page.screenshot(path=os.path.join(base, "app", "debug3.png"))
    
    print("Errors:", len(errors))
    for e in errors[:10]:
        print("  %s" % e[:200])
    
    browser.close()
