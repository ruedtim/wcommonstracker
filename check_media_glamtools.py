#!/usr/bin/env python3
"""
Script to fetch media usage statistics via GLAM Tools (glamorgan)
Uses browser automation to interact with https://glamtools.toolforge.org/glamorgan.html
"""

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from datetime import datetime, timezone
import time
import os
import json

# Configuration
GLAMTOOLS_URL = "https://glamtools.toolforge.org/glamorgan.html"
CATEGORY = "Media supplied by Universitätsarchiv St. Gallen"
DEPTH = "12"
# Use previous month to ensure data is available
current_date = datetime.now(timezone.utc)
# Go back one month
if current_date.month == 1:
    YEAR = str(current_date.year - 1)
    MONTH = "12"
else:
    YEAR = str(current_date.year)
    MONTH = str(current_date.month - 1)
BASE_OUTPUT_DIR = "reports"
TIMEOUT = 600  # 10 minutes max wait time (GLAM Tools can take time to load)


def setup_driver(headless=True):
    """Setup Chrome driver with options"""
    chrome_options = Options()
    if headless:
        chrome_options.add_argument("--headless")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--window-size=1920,1080")
    
    driver = webdriver.Chrome(options=chrome_options)
    return driver


def fill_form_and_submit(driver):
    """Fill the GLAM Tools form and submit"""
    print(f"Opening {GLAMTOOLS_URL}")
    driver.get(GLAMTOOLS_URL)
    
    # Wait for page to load
    wait = WebDriverWait(driver, 30)
    
    # Fill in the category
    print(f"Filling category: {CATEGORY}")
    category_input = wait.until(
        EC.presence_of_element_located((By.ID, "category"))
    )
    category_input.clear()
    category_input.send_keys(CATEGORY)
    
    # Fill in the depth
    print(f"Setting depth: {DEPTH}")
    depth_input = driver.find_element(By.ID, "depth")
    depth_input.clear()
    depth_input.send_keys(DEPTH)
    
    # Fill in year (it's an input, not a select)
    print(f"Setting year: {YEAR}")
    year_input = driver.find_element(By.ID, "year")
    year_input.clear()
    year_input.send_keys(YEAR)
    
    # Fill in month (it's an input, not a select)
    print(f"Setting month: {MONTH}")
    month_input = driver.find_element(By.ID, "month")
    month_input.clear()
    month_input.send_keys(MONTH)
    
    # Submit the form
    print("Submitting form...")
    submit_button = driver.find_element(By.CSS_SELECTOR, "input[type='submit']")
    submit_button.click()
    
    print("Form submitted, waiting for results...")


def wait_for_results(driver):
    """Wait for the results to load"""
    print("Waiting for results to load (this can take 1-2 minutes)...")
    
    # Initial wait for JavaScript to process and API calls to start
    time.sleep(10)
    
    # Wait for results to be fully populated
    max_wait = TIMEOUT
    start_time = time.time()
    last_content_length = 0
    stable_count = 0
    found_results = False
    
    while time.time() - start_time < max_wait:
        try:
            # Get current page content
            current_content = driver.page_source
            current_length = len(current_content)
            elapsed = int(time.time() - start_time)
            
            # Look for key result indicators
            has_category_msg = "files in category tree" in current_content.lower()
            has_table = "<table class='table table-striped'>" in current_content or "<table class=\"table table-striped\">" in current_content
            has_views_data = "file views in" in current_content.lower()
            
            if has_category_msg and not found_results:
                print(f"✓ Found 'files in category tree' message ({elapsed}s)")
                found_results = True
            
            # Check if data is complete (has table with views)
            if has_table and has_views_data:
                print(f"✓ Found table with view data ({elapsed}s)")
                # Wait for content to stabilize
                if current_length == last_content_length:
                    stable_count += 1
                    if stable_count >= 5:  # Content stable for 5 checks (5 seconds)
                        print(f"✓ Content stabilized ({elapsed}s)")
                        time.sleep(3)  # Final buffer
                        break
                else:
                    stable_count = 0
                    last_content_length = current_length
                    if elapsed % 10 == 0:  # Log every 10 seconds
                        print(f"  Still loading... ({current_length} bytes, {elapsed}s)")
            elif found_results:
                if elapsed % 10 == 0:
                    print(f"  Loading view data... ({elapsed}s)")
                
        except Exception as e:
            print(f"  Checking... ({int(time.time() - start_time)}s) - {e}")
        
        time.sleep(1)
    
    elapsed_final = int(time.time() - start_time)
    print(f"Results loading complete after {elapsed_final} seconds!")


def save_results(driver):
    """Save the results in various formats"""
    # Create timestamped output directory
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    OUTPUT_DIR = os.path.join(BASE_OUTPUT_DIR, f"{YEAR}-{MONTH.zfill(2)}_{timestamp}")
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    
    # Save full HTML
    html_file = os.path.join(OUTPUT_DIR, f"glamtools_results_{timestamp}.html")
    with open(html_file, "w", encoding="utf-8") as f:
        f.write(driver.page_source)
    print(f"Saved HTML: {html_file}")
    
    # Save screenshot
    screenshot_file = os.path.join(OUTPUT_DIR, f"glamtools_screenshot_{timestamp}.png")
    driver.save_screenshot(screenshot_file)
    print(f"Saved screenshot: {screenshot_file}")
    
    # Try to extract table data
    try:
        tables = driver.find_elements(By.TAG_NAME, "table")
        if tables:
            # Extract text content
            table_data = []
            for table in tables:
                rows = table.find_elements(By.TAG_NAME, "tr")
                for row in rows:
                    cells = row.find_elements(By.TAG_NAME, "td")
                    if not cells:
                        cells = row.find_elements(By.TAG_NAME, "th")
                    row_data = [cell.text for cell in cells]
                    if row_data:
                        table_data.append(row_data)
            
            # Save as JSON
            json_file = os.path.join(OUTPUT_DIR, f"glamtools_data_{timestamp}.json")
            with open(json_file, "w", encoding="utf-8") as f:
                json.dump({
                    "category": CATEGORY,
                    "depth": DEPTH,
                    "year": YEAR,
                    "month": MONTH,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "table_data": table_data
                }, f, indent=2, ensure_ascii=False)
            print(f"Saved JSON data: {json_file}")
    except Exception as e:
        print(f"Note: Could not extract table data: {e}")
    
    # Save latest versions
    latest_html = os.path.join(OUTPUT_DIR, "latest.html")
    with open(latest_html, "w", encoding="utf-8") as f:
        f.write(driver.page_source)
    
    latest_screenshot = os.path.join(OUTPUT_DIR, "latest_screenshot.png")
    driver.save_screenshot(latest_screenshot)
    
    # Try to get the page URL (might have changed)
    current_url = driver.current_url
    print(f"Current URL: {current_url}")
    
    # Save metadata
    metadata_file = os.path.join(OUTPUT_DIR, f"metadata_{timestamp}.json")
    with open(metadata_file, "w", encoding="utf-8") as f:
        json.dump({
            "category": CATEGORY,
            "depth": DEPTH,
            "year": YEAR,
            "month": MONTH,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "url": current_url,
            "page_title": driver.title
        }, f, indent=2, ensure_ascii=False)
    print(f"Saved metadata: {metadata_file}")
    
    return OUTPUT_DIR


def main():
    """Main execution function"""
    driver = None
    try:
        print("Starting GLAM Tools browser automation...")
        print(f"Category: {CATEGORY}")
        print(f"Depth: {DEPTH}")
        print(f"Year/Month: {YEAR}/{MONTH}\n")
        
        driver = setup_driver(headless=True)
        fill_form_and_submit(driver)
        wait_for_results(driver)
        output_dir = save_results(driver)
        
        print("\n✓ Process completed successfully!")
        print(f"Results saved to {output_dir}/")
        
    except Exception as e:
        print(f"\n✗ Error occurred: {e}")
        if driver:
            # Save error screenshot
            os.makedirs(BASE_OUTPUT_DIR, exist_ok=True)
            error_screenshot = os.path.join(BASE_OUTPUT_DIR, f"error_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}.png")
            try:
                driver.save_screenshot(error_screenshot)
                print(f"Error screenshot saved: {error_screenshot}")
            except:
                pass
        raise
    finally:
        if driver:
            driver.quit()
            print("Browser closed")


if __name__ == "__main__":
    main()
