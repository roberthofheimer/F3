import os
import time
from playwright.sync_api import sync_playwright
import gspread
from datetime import datetime

def scrape_f3_stats():
    url = "https://f3southcary-aohealth.streamlit.app/~/+/pax"
    
    with sync_playwright() as p:
        print("Launching browser...")
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1280, "height": 800})
        
        print(f"Navigating to {url}...")
        page.goto(url, wait_until="networkidle", timeout=60000)
        time.sleep(5)
        
        print("Attempting to select 'shipyard'...")
        try:
            # Click the Streamlit combobox directly using standard Playwright selectors
            page.locator('[role="combobox"]').first.click(force=True, timeout=10000)
            time.sleep(1)
            page.keyboard.type("shipyard")
            page.keyboard.press("Enter")
            print("Successfully selected 'shipyard'.")
        except Exception as e:
            print(f"Primary combobox click note: {e}. Trying fallback selector...")
            try:
                page.locator('div[data-baseweb="select"]').first.click(force=True, timeout=5000)
                time.sleep(1)
                page.keyboard.type("shipyard")
                page.keyboard.press("Enter")
                print("Fallback selection successful.")
            except Exception as e2:
                print(f"Fallback selection note: {e2}")
            
        print("Waiting for stats to compute and render...")
        time.sleep(8)
        
        posts, qs = None, None
        
        # Scrape metrics cards with retry loop
        for attempt in range(10):
            metrics = page.locator('[data-testid="stMetric"]').all()
            if metrics:
                for metric in metrics:
                    try:
                        text = metric.inner_text()
                        lines = [l.strip() for l in text.split('\n') if l.strip()]
                        if len(lines) >= 2:
                            label = lines[0].lower()
                            val = lines[1]
                            if 'post' in label and val.isdigit():
                                posts = int(val)
                            elif 'q' in label and val.isdigit():
                                qs = int(val)
                    except Exception:
                        pass
                
                if posts is not None and qs is not None:
                    print(f"SUCCESS: Found stats -> Posts: {posts}, Q's: {qs}")
                    break
            time.sleep(2)
            
        browser.close()
        
        if posts is None or qs is None:
            raise ValueError(f"Could not find metric numbers on page. Posts={posts}, Q's={qs}")
            
        return posts, qs

def update_google_sheet():
    posts, qs = scrape_f3_stats()
    
    print("Connecting to Google Sheets...")
    gc = gspread.service_account(filename='credentials.json')
    sheet = gc.open_by_key("11eASIqkZB6Bs5lNf44K3GPZ9vStgzYATcqLDH9s3L4I")
    
    # 1. Update Sheet1 cells A4 (Posts) and B4 (Qs)
    ws1 = sheet.worksheet("Sheet1")
    ws1.update('A4', [[posts]])
    ws1.update('B4', [[qs]])
    print("Sheet1 cells A4 and B4 updated successfully.")
    
    # 2. Append history log to Main tab
    try:
        ws_main = sheet.worksheet("Main")
        now = datetime.now()
        ws_main.append_row([
            "https://f3southcary-aohealth.streamlit.app/~/+/pax",
            "shipyard",
            now.strftime("%Y-%m-%d %H:%M"),
            "Successful",
            posts,
            qs,
            now.strftime("%Y-%m-%d"),
            "GitHub Actions Automated"
        ])
        print("Main log row appended successfully.")
    except Exception as e:
        print(f"Main log warning: {e}")

if __name__ == "__main__":
    update_google_sheet()
