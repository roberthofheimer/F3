import os
import time
from playwright.sync_api import sync_playwright
import gspread
from datetime import datetime

def scrape_f3_stats():
    url = "https://f3southcary-aohealth.streamlit.app/~/+/pax"
    
    with sync_playwright() as p:
        print("Launching Chromium browser...")
        browser = p.chromium.launch(headless=True)
        # Use a standard desktop viewport size so Streamlit renders fully
        page = browser.new_page(viewport={"width": 1280, "height": 800})
        
        print(f"Navigating to {url}...")
        page.goto(url, wait_until="networkidle", timeout=60000)
        
        # Wait for Streamlit to initialize completely
        time.sleep(5)
        
        print("Selecting 'shipyard' from the PAX dropdown...")
        try:
            # Target the Streamlit selectbox / combobox component
            combobox = page.locator('div[data-baseweb="select"]').first
            combobox.click()
            time.sleep(1)
            
            # Type 'shipyard' and hit Enter to filter stats for Shipyard
            page.keyboard.type("shipyard")
            page.keyboard.press("Enter")
            
            # Allow time for Streamlit to fetch data and re-render metrics
            print("Waiting for stats to update after selection...")
            time.sleep(6)
        except Exception as e:
            print(f"Warning during dropdown selection: {e}")
            
        posts, qs = None, None
        
        # Extract metrics from the page
        for attempt in range(5):
            metrics = page.locator('[data-testid="stMetric"]').all()
            if metrics:
                for metric in metrics:
                    text = metric.inner_text()
                    print(f"Found metric card text: {repr(text)}")
                    lines = [line.strip() for line in text.split('\n') if line.strip()]
                    
                    if len(lines) >= 2:
                        label = lines[0].lower()
                        val_str = lines[1]
                        if 'post' in label and val_str.isdigit():
                            posts = int(val_str)
                        elif 'q' in label and val_str.isdigit():
                            qs = int(val_str)
                            
                if posts is not None and qs is not None:
                    print(f"SUCCESS: Extracted Posts={posts}, Q's={qs}")
                    break
            time.sleep(2)
            
        browser.close()
        
        if posts is None or qs is None:
            raise ValueError(f"Failed to scrape values. Extracted Posts={posts}, Q's={qs}")
            
        return posts, qs

def update_google_sheet():
    try:
        posts, qs = scrape_f3_stats()
        
        print("Connecting to Google Sheets...")
        gc = gspread.service_account(filename='credentials.json')
        spreadsheet_id = "11eASIqkZB6Bs5lNf44K3GPZ9vStgzYATcqLDH9s3L4I"
        sheet = gc.open_by_key(spreadsheet_id)
        
        # 1. Update Sheet1 target cells (A4 for Posts, B4 for Q's)
        ws1 = sheet.worksheet("Sheet1")
        ws1.update('A4', [[posts]])
        ws1.update('B4', [[qs]])
        print(f"Updated Sheet1 A4 -> {posts}, B4 -> {qs}")
        
        # 2. Append history log to Main tab to match your tracking history
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
            print("Appended run log to Main sheet successfully.")
        except Exception as main_e:
            print(f"Main tab logging skipped: {main_e}")

    except Exception as e:
        print(f"ERROR in update_google_sheet: {e}")
        raise e

if __name__ == "__main__":
    update_google_sheet()
