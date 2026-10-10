import os
import time
from playwright.sync_api import sync_playwright
import gspread
from datetime import datetime

def scrape_f3_stats():
    # Direct Streamlit app URL to avoid outer iframe wrapper delays
    url = "https://f3southcary-aohealth.streamlit.app/~/+/pax?range=month&name=Shipyard"
    
    with sync_playwright() as p:
        print("Launching Chromium browser...")
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
        page = context.new_page()
        
        print(f"Navigating to {url}...")
        page.goto(url, wait_until="domcontentloaded", timeout=60000)
        
        # Streamlit websocket connection load wait
        print("Waiting for Streamlit app to render content...")
        
        # Try both direct page selector or nested frame selector
        posts, qs = None, None
        
        for attempt in range(15): # Loop up to ~30 seconds waiting for data
            time.sleep(2)
            try:
                # Target all metric elements on the page or inside frames
                metrics = page.locator('[data-testid="stMetric"]').all()
                if not metrics:
                    # Look inside iframe if nested
                    for frame in page.frames:
                        metrics = frame.locator('[data-testid="stMetric"]').all()
                        if metrics:
                            break
                            
                if metrics:
                    for metric in metrics:
                        text = metric.inner_text()
                        print(f"Found card text: {repr(text)}")
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
            except Exception as e:
                print(f"Attempt {attempt + 1} checking DOM failed: {e}")
                
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
        
        # 1. Update Sheet1
        ws1 = sheet.worksheet("Sheet1")
        ws1.update('A4', [[posts]])
        ws1.update('B4', [[qs]])
        print(f"Updated Sheet1 A4 -> {posts}, B4 -> {qs}")
        
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
                "GitHub Actions"
            ])
            print("Appended log row to Main sheet.")
        except Exception as main_e:
            print(f"Could not write log to Main sheet: {main_e}")

    except Exception as e:
        print(f"ERROR in update_google_sheet: {e}")
        raise e

if __name__ == "__main__":
    update_google_sheet()
