import os
import time
from playwright.sync_api import sync_playwright
import gspread
from datetime import datetime

def scrape_f3_stats():
    url = "https://f3southcary.com/stats/#/pax?range=month&name=Shipyard"
    
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.goto(url, wait_until="networkidle")
        
        # Wait for Streamlit components to fully render and hydrate
        print("Waiting for Streamlit components to load...")
        page.wait_for_selector('[data-testid="stMetric"]', timeout=20000)
        time.sleep(4) # Extra buffer for hash routing data fetch
        
        posts = None
        qs = None
        
        # Streamlit metric cards structure
        metrics = page.locator('[data-testid="stMetric"]').all()
        for metric in metrics:
            try:
                label = metric.locator('[data-testid="stMetricLabel"]').inner_text().strip().lower()
                value = metric.locator('[data-testid="stMetricValue"]').inner_text().strip()
                print(f"Found metric -> Label: '{label}', Value: '{value}'")
                
                if 'post' in label:
                    posts = int(value)
                elif 'q' in label:
                    qs = int(value)
            except Exception as e:
                print(f"Skipping a metric element: {e}")
                
        browser.close()
        
        if posts is None or qs is None:
            raise ValueError(f"Could not locate Posts ({posts}) or Q's ({qs}) on the Streamlit page.")
            
        return posts, qs

def update_google_sheet():
    try:
        posts, qs = scrape_f3_stats()
        print(f"Successfully scraped -> Posts: {posts}, Q's: {qs}")
        
        # Authenticate with Google Sheets using the GitHub Secret
        gc = gspread.service_account(filename='credentials.json')
        
        # Open your Google Sheet by its unique ID
        spreadsheet_id = "11eASIqkZB6Bs5lNf44K3GPZ9vStgzYATcqLDH9s3L4I"
        sheet = gc.open_by_key(spreadsheet_id)
        
        # 1. Update Sheet1 current values (A4 for Posts, B4 for Q's based on your sheet layout)
        worksheet_sheet1 = sheet.worksheet("Sheet1")
        worksheet_sheet1.update('A4', [[posts]])
        worksheet_sheet1.update('B4', [[qs]])
        print("Updated Sheet1 cells A4 and B4 successfully.")
        
        # 2. (Optional) Append history log to your 'Main' tab just like Browse.ai did
        try:
            worksheet_main = sheet.worksheet("Main")
            today_str = datetime.now().strftime("%Y-%m-%d %H:%M")
            date_only = datetime.now().strftime("%Y-%m-%d")
            worksheet_main.append_row([
                "https://f3southcary-aohealth.streamlit.app/~/+/pax",
                "shipyard",
                today_str,
                "Successful",
                posts,
                qs,
                date_only,
                "GitHub Actions Automated"
            ])
            print("Appended run history to 'Main' tab successfully.")
        except Exception as log_err:
            print(f"Main tab logging skipped: {log_err}")

    except Exception as e:
        print(f"Error during execution: {e}")
        raise e

if __name__ == "__main__":
    update_google_sheet()
