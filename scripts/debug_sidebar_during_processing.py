from playwright.sync_api import sync_playwright


def main():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1200, "height": 820})
        page.add_init_script(
            """
            (() => {
              class MockEventSource {
                constructor(url) {
                  this.url = url;
                  this.readyState = 1;
                  window.__mockEventSourceUrl = url;
                  setTimeout(() => {
                    this.onmessage && this.onmessage({
                      data: JSON.stringify({ type: 'log', message: 'mock slow stream started' })
                    });
                  }, 80);
                  setTimeout(() => {
                    this.onmessage && this.onmessage({
                      data: JSON.stringify({
                        step: 'rewritten',
                        queries: ['aluminum alloy tensile strength'],
                        retrieval: { original_query: 'test', search_queries: ['aluminum alloy tensile strength'] }
                      })
                    });
                  }, 180);
                  // Keep the stream open long enough to click the sidebar while isProcessing=true.
                  this._timer = setTimeout(() => {
                    this.onmessage && this.onmessage({
                      data: JSON.stringify({
                        type: 'result',
                        data: { answer: 'mock answer', citations: [], retrieval: {}, graph: {}, structured_output: {} }
                      })
                    });
                  }, 5000);
                }
                close() {
                  this.readyState = 2;
                  clearTimeout(this._timer);
                  window.__mockEventSourceClosed = true;
                }
              }
              window.EventSource = MockEventSource;
            })();
            """
        )
        page.goto("http://127.0.0.1:8000/static/index.html#/")
        page.wait_for_load_state("networkidle")

        page.locator(".suggestion-chip").first.click()
        page.wait_for_function("window.__mockEventSourceUrl && document.querySelectorAll('.message').length >= 2")

        before = page.evaluate(
            """() => ({
              processingTextDisabled: document.querySelector('.chat-input textarea')?.disabled,
              messageCount: document.querySelectorAll('.message').length,
              newChatBox: document.querySelector('.new-chat-btn')?.getBoundingClientRect().toJSON?.()
            })"""
        )
        page.locator(".new-chat-btn").click()
        page.wait_for_timeout(250)
        after_click = page.evaluate(
            """() => ({
              messageCount: document.querySelectorAll('.message').length,
              welcomeVisible: !!document.querySelector('#welcome'),
              streamClosed: !!window.__mockEventSourceClosed
            })"""
        )
        page.wait_for_timeout(5200)
        after_stream = page.evaluate(
            """() => ({
              messageCount: document.querySelectorAll('.message').length,
              welcomeVisible: !!document.querySelector('#welcome'),
              streamClosed: !!window.__mockEventSourceClosed
            })"""
        )
        print({"before": before, "after_click": after_click, "after_stream": after_stream})
        browser.close()


if __name__ == "__main__":
    main()
