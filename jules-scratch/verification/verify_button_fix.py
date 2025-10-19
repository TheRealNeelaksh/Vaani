from playwright.sync_api import sync_playwright, expect, Error

def run_verification():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()

        try:
            # Navigate to the app page
            page.goto("http://127.0.0.1:8000/app", wait_until="domcontentloaded")

            # Wait for the "Access Taara" button to be visible and enabled
            access_taara_button = page.locator('button[data-model="Taara"]')
            expect(access_taara_button).to_be_visible(timeout=10000) # Increased timeout
            expect(access_taara_button).to_be_enabled()

            # Take a screenshot to verify the button is active
            page.screenshot(path="jules-scratch/verification/verification.png")
            print("Verification successful, screenshot saved.")

        except Error as e:
            print(f"An error occurred: {e}")
            page.screenshot(path="jules-scratch/verification/error_screenshot.png")
            print("Error screenshot saved.")
            print("Page content at time of error:")
            print(page.content())

        finally:
            browser.close()

if __name__ == "__main__":
    run_verification()