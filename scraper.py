import os
import time
from playwright.sync_api import sync_playwright
import gspread

def scrape_f3_stats():
    url = "https://f3southcary.com/stats/#/pax?range=month&name=Shipyard"
    
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.goto(url, wait_until="networkidle")
        
        # Allow extra time for the SPA framework and hash routing to fully render the DOM
        page.wait_for_timeout(6000)
        
        # TODO: Adjust these selectors to target the exact HTML elements for Posts and Q's 
        # (Right-click the element on the stats page -> Inspect to find the class or ID)
        posts = page.locator(".posts-class-or-selector").inner_text() 
        qs = page.locator(".qs-class-or-selector").inner_text()
        
        browser.close()
        return int(posts), int(qs)

def update_google_sheet():
    try:
        posts, qs = scrape_f3_stats()
        
        # Authenticate with Google Sheets using the JSON key file
        gc = gspread.service_account(filename='credentials.json')
        
        # Replace with your exact Google Sheet name
        sheet = gc.open("Your Google Sheet Name").worksheet("Sheet1")
        
        # Update your target cells (e.g., B2 for Posts, B3 for Q's)
        sheet.update('B2', [[posts]])
        sheet.update('B3', [[qs]])
        
        print(f"Successfully updated sheet -> Posts: {posts}, Q's: {qs}")
    except Exception as e:
        print(f"Error during scraping or sheet update: {e}")
        raise e

if __name__ == "__main__":
    update_google_sheet()
