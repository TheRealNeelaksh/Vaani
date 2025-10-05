import re
from playwright.sync_api import sync_playwright, expect

def run(playwright):
    browser = playwright.chromium.launch(headless=True)
    context = browser.new_context()
    page = context.new_page()

    try:
        # 1. Navigate to the application's home page.
        page.goto("http://127.0.0.1:8000/")

        # 2. Expect the main model selection screen to be visible.
        expect(page.locator("#model-select-screen")).to_be_visible()

        # 3. Click the "Access Taara" button to initiate a call.
        # We handle the password prompt by overriding the prompt handler.
        page.on("dialog", lambda dialog: dialog.accept("testpassword"))
        page.get_by_role("button", name="Access Taara").click()

        # 4. Wait for the call screen to become active and visible.
        expect(page.locator("#call-screen")).to_be_visible(timeout=10000)

        # 5. Assert that the call interface elements are present.
        expect(page.locator("#call-name")).to_have_text("Taara")
        expect(page.locator("#mute-btn")).to_be_visible()
        expect(page.locator("#end-call-btn")).to_be_visible()

        # 6. Take a screenshot of the call screen for visual verification.
        page.screenshot(path="jules-scratch/verification/verification.png")
        print("Screenshot saved to jules-scratch/verification/verification.png")

    except Exception as e:
        print(f"An error occurred: {e}")
        page.screenshot(path="jules-scratch/verification/error.png")
    finally:
        browser.close()

with sync_playwright() as playwright:
    run(playwright)