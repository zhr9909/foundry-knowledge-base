from playwright.sync_api import sync_playwright
import os

base = r"E:\AgentProjects\ai-solution-architect-lab\projects\foundry-knowledge-base"

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page(viewport={"width": 1440, "height": 900})
    
    errors = []
    page.on("console", lambda msg: errors.append(("console", msg.text)))
    page.on("pageerror", lambda err: errors.append(("error", str(err))))
    
    page.goto("http://127.0.0.1:8000/static/index.html", wait_until="networkidle")
    
    page.screenshot(path=os.path.join(base, "app", "debug.png"))
    
    welcome = page.evaluate("""() => {
        var e = document.getElementById("welcome");
        return e ? "display=" + e.style.display + " height=" + e.offsetHeight : "NOT FOUND"
    }""")
    
    history_sec = page.evaluate("""() => {
        var e = document.getElementById("historySection");
        return e ? "display=" + e.style.display + " ch=" + e.children.length : "NOT FOUND"
    }""")
    
    messages_sec = page.evaluate("""() => {
        var e = document.getElementById("messages");
        return e ? "display=" + e.style.display + " ch=" + e.children.length : "NOT FOUND"
    }""")
    
    version = page.evaluate("""() => {
        var s = document.querySelector("script[src*=app.js]");
        return s ? s.src : "NOT FOUND"
    }""")
    
    print("Welcome:", welcome)
    print("History:", history_sec)
    print("Messages:", messages_sec)
    print("JS version:", version)
    print("")
    print("Errors:", len(errors))
    for t, msg in errors[:10]:
        print("  [%s] %s" % (t, msg[:200]))
    
    browser.close()
