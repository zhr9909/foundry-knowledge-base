from playwright.sync_api import sync_playwright
import os

base = r"E:\AgentProjects\ai-solution-architect-lab\projects\foundry-knowledge-base"

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page(viewport={"width": 1440, "height": 900})
    
    page.goto("http://127.0.0.1:8000/static/index.html", timeout=5000)
    page.wait_for_load_state("load", timeout=5000)
    
    page.screenshot(path=os.path.join(base, "app", "debug.png"))
    print("Screenshot saved")
    
    # Simple DOM checks
    result = page.evaluate("""() => {
        var o = {};
        var w = document.getElementById("welcome");
        o.welcome = w ? "ok h=" + w.offsetHeight : "missing";
        var h = document.getElementById("historySection");
        o.history = h ? "ok disp=" + h.style.display : "missing";
        var m = document.getElementById("messages");
        o.messages = m ? "ok disp=" + m.style.display + " kids=" + m.children.length : "missing";
        var s = document.querySelector("script[src*=app.js]");
        o.js = s ? s.src : "missing";
        var ps = document.getElementById("progressSteps");
        o.progress = ps ? "exists kids=" + ps.children.length : "missing";
        var input = document.getElementById("queryInput");
        o.input = input ? "ok ph=" + (input.placeholder || "none") : "missing";
        var sb = document.getElementById("sendBtn");
        o.sendBtn = sb ? "ok disabled=" + sb.disabled : "missing";
        return o;
    }""")
    
    for k, v in result.items():
        print("  %s: %s" % (k, v))
    
    browser.close()
