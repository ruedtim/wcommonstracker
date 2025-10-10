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
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from bs4 import BeautifulSoup
import time
import json
import re

# Configuration
GLAMTOOLS_URL = "https://glamtools.toolforge.org/glamorgan.html"
CATEGORY = "Media supplied by Universitätsarchiv St. Gallen"
DEPTH = "12"
# Use previous month to ensure data is available


def previous_month(year: int, month: int) -> Tuple[int, int]:
    if month == 1:
        return year - 1, 12
    return year, month - 1


current_date = datetime.now(timezone.utc)
target_year, target_month = previous_month(current_date.year, current_date.month)
YEAR = f"{target_year}"
MONTH = f"{target_month:02d}"
MONTH_FOR_FORM = str(target_month)
IS_FIRST_DAY_OF_MONTH = current_date.day == 1
PREVIOUS_DATASET_YEAR, PREVIOUS_DATASET_MONTH = previous_month(target_year, target_month)
BASE_OUTPUT_DIR = Path("reports")
TIMEOUT = 120  # 2 minutes max wait time (GLAM Tools can take time to load)


def parse_int(value: str) -> Optional[int]:
    """Convert a numeric string with separators to int."""
    if value is None:
        return None
    digits = re.sub(r"[^0-9-]", "", value)
    if not digits:
        return None
    try:
        return int(digits)
    except ValueError:
        return None


def extract_summary_stats_from_html(html: str) -> Dict[str, Optional[int]]:
    """Extract summary statistics (files, pages, views) from the HTML."""
    soup = BeautifulSoup(html, "html.parser")
    stats: Dict[str, Optional[int]] = {
        "files_viewed": None,
        "files_used": None,
        "pages_used": None,
        "wikis": None,
        "views": None,
    }

    files_pattern = re.compile(
        r"([\d,]+)\s+files were viewed,\s*out of\s*([\d,]+)\s+used",
        re.IGNORECASE,
    )
    pages_pattern = re.compile(
        r"([\d,]+)\s+pages on\s+([\d,]+)\s+wikis", re.IGNORECASE
    )
    views_pattern = re.compile(r"([\d,]+)\s+file views", re.IGNORECASE)

    for div in soup.find_all("div"):
        text = div.get_text(" ", strip=True)
        if not text:
            continue

        if stats["files_viewed"] is None:
            match = files_pattern.search(text)
            if match:
                stats["files_viewed"] = parse_int(match.group(1))
                stats["files_used"] = parse_int(match.group(2))

        if stats["pages_used"] is None:
            match = pages_pattern.search(text)
            if match:
                stats["pages_used"] = parse_int(match.group(1))
                stats["wikis"] = parse_int(match.group(2))

        if stats["views"] is None:
            match = views_pattern.search(text)
            if match:
                stats["views"] = parse_int(match.group(1))

    return stats


def extract_file_entries_from_html(html: str) -> List[Dict[str, Any]]:
    """Extract media entries (title, url, views) from the HTML table."""
    soup = BeautifulSoup(html, "html.parser")
    table = soup.select_one("#output table.table-striped")
    files: List[Dict[str, Any]] = []

    if not table:
        return files

    for row in table.find_all("tr"):
        file_link = row.find(
            "a", href=lambda href: href and "commons.wikimedia.org/wiki/File" in href
        )
        if not file_link:
            continue

        cells = row.find_all(["td", "th"])
        views: Optional[int] = None
        if len(cells) >= 3:
            views = parse_int(cells[2].get_text(strip=True))

        files.append(
            {
                "title": file_link.get_text(strip=True),
                "url": file_link.get("href"),
                "views": views,
            }
        )

    return files


def load_report_data(report_dir: Path) -> Optional[Dict[str, Any]]:
    """Load stored metadata and derived data for a report directory."""
    if not report_dir.is_dir():
        return None

    metadata_path = next(iter(sorted(report_dir.glob("metadata_*.json"))), None)
    metadata: Dict[str, Any] = {}
    if metadata_path and metadata_path.exists():
        try:
            with metadata_path.open("r", encoding="utf-8") as f:
                metadata = json.load(f)
        except (json.JSONDecodeError, OSError):
            metadata = {}

    html_path = next(iter(sorted(report_dir.glob("glamtools_results_*.html"))), None)
    html_content = ""
    if html_path and html_path.exists():
        try:
            html_content = html_path.read_text(encoding="utf-8")
        except OSError:
            html_content = ""

    summary = metadata.get("summary")
    files = metadata.get("files")

    if html_content:
        if not summary:
            summary = extract_summary_stats_from_html(html_content)
        if not files:
            files = extract_file_entries_from_html(html_content)

    timestamp = metadata.get("timestamp")
    if not timestamp:
        try:
            timestamp = datetime.fromtimestamp(
                (html_path or report_dir).stat().st_mtime, timezone.utc
            ).isoformat()
        except OSError:
            timestamp = None

    return {
        "path": report_dir,
        "metadata": metadata,
        "summary": summary or {},
        "files": files or [],
        "timestamp": timestamp,
    }


def parse_timestamp(timestamp: Optional[str]) -> Optional[datetime]:
    if not timestamp:
        return None
    try:
        return datetime.fromisoformat(timestamp)
    except ValueError:
        try:
            return datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
        except ValueError:
            return None


def get_latest_report() -> Optional[Dict[str, Any]]:
    """Return information about the most recent report directory."""
    if not BASE_OUTPUT_DIR.exists():
        return None

    latest_report: Optional[Dict[str, Any]] = None
    latest_timestamp: Optional[datetime] = None

    for entry in BASE_OUTPUT_DIR.iterdir():
        if not entry.is_dir():
            continue

        data = load_report_data(entry)
        if not data:
            continue

        ts = parse_timestamp(data.get("timestamp"))
        if ts is None:
            try:
                ts = datetime.fromtimestamp(entry.stat().st_mtime, timezone.utc)
            except OSError:
                ts = None

        if ts is None:
            continue

        if latest_timestamp is None or ts > latest_timestamp:
            latest_timestamp = ts
            latest_report = data

    return latest_report


def get_report_datetime(report: Dict[str, Any]) -> Optional[datetime]:
    """Return a timezone-aware datetime for a report, if possible."""
    ts = parse_timestamp(report.get("timestamp"))
    if ts:
        return ts

    metadata = report.get("metadata") or {}
    metadata_ts = parse_timestamp(metadata.get("timestamp"))
    if metadata_ts:
        return metadata_ts

    path = report.get("path")
    if isinstance(path, Path):
        try:
            return datetime.fromtimestamp(path.stat().st_mtime, timezone.utc)
        except OSError:
            return None

    return None


def find_earliest_report_for_month(year: int, month: int) -> Optional[Dict[str, Any]]:
    """Return the earliest stored report for the given dataset month."""
    if not BASE_OUTPUT_DIR.exists():
        return None

    candidates: List[Dict[str, Any]] = []

    for entry in BASE_OUTPUT_DIR.iterdir():
        if not entry.is_dir():
            continue

        data = load_report_data(entry)
        if not data:
            continue

        metadata = data.get("metadata") or {}

        try:
            metadata_year = int(metadata.get("year"))
            metadata_month = int(metadata.get("month"))
        except (TypeError, ValueError):
            continue

        if metadata_year == year and metadata_month == month:
            candidates.append(data)

    if not candidates:
        return None

    far_future = datetime.max.replace(tzinfo=timezone.utc)
    candidates.sort(key=lambda item: get_report_datetime(item) or far_future)
    return candidates[0]


def format_diff(value: int) -> str:
    if value > 0:
        return f"[+{value}]"
    if value < 0:
        return f"[{value}]"
    return "[0]"


def compute_pages_diff_label(
    current_summary: Dict[str, Any], previous_report: Optional[Dict[str, Any]]
) -> str:
    current_pages = current_summary.get("pages_used")
    previous_pages = (
        (previous_report or {}).get("summary", {}).get("pages_used")
        if previous_report
        else None
    )

    if current_pages is None or previous_pages is None:
        return "[0]"

    diff_value = int(current_pages) - int(previous_pages)
    return format_diff(diff_value)


def format_signed(value: int) -> str:
    return f"+{value}" if value > 0 else str(value)


def calculate_summary_differences(
    current_summary: Dict[str, Any], previous_summary: Dict[str, Any]
) -> Dict[str, int]:
    diffs: Dict[str, int] = {}
    for key in ("files_used", "pages_used", "views"):
        current_value = current_summary.get(key)
        previous_value = previous_summary.get(key)
        if current_value is None or previous_value is None:
            continue
        diffs[key] = int(current_value) - int(previous_value)
    return diffs


def write_comparison_summary(
    output_dir: Path,
    current_summary: Dict[str, Any],
    previous_report: Dict[str, Any],
    current_files: List[Dict[str, Any]],
    *,
    filename: str,
    heading: str,
    require_views_change: bool,
) -> Optional[Path]:
    previous_summary = previous_report.get("summary", {})

    differences = calculate_summary_differences(current_summary, previous_summary)
    views_diff = differences.get("views")
    if require_views_change and (views_diff is None or views_diff == 0):
        return None

    current_files_used = current_summary.get("files_used")
    if current_files_used is None:
        current_files_used = len(current_files)
    else:
        current_files_used = int(current_files_used)

    previous_files_used = previous_summary.get("files_used")
    if previous_files_used is None:
        previous_files_used = len(previous_report.get("files", []))
    else:
        previous_files_used = int(previous_files_used)

    files_diff = int(current_files_used) - int(previous_files_used)

    pages_previous_value = previous_summary.get("pages_used")
    pages_current_value = current_summary.get("pages_used")

    pages_previous = int(pages_previous_value) if pages_previous_value is not None else 0
    pages_current = int(pages_current_value) if pages_current_value is not None else 0
    pages_diff = pages_current - pages_previous

    current_views_value = current_summary.get("views")
    current_views_display = current_views_value if current_views_value is not None else "unknown"

    views_diff_value = views_diff if views_diff is not None else 0

    previous_files_by_url = {
        item["url"]: item
        for item in previous_report.get("files", [])
        if item.get("url")
    }
    current_files_by_url = {
        item["url"]: item for item in current_files if item.get("url")
    }

    added_urls = sorted(set(current_files_by_url) - set(previous_files_by_url))
    removed_urls = sorted(set(previous_files_by_url) - set(current_files_by_url))

    lines = [
        heading,
        f"- Media files used: {format_signed(files_diff)} (current total: {current_files_used})",
        f"- Pages using media: {format_signed(pages_diff)} (current total: {current_summary.get('pages_used', 'unknown')})",
        f"- File views: {format_signed(views_diff_value)} (current total: {current_views_display})",
    ]

    if files_diff != 0:
        if added_urls:
            lines.append("  Added media files:")
            for url in added_urls:
                item = current_files_by_url[url]
                title = item.get("title") or url
                lines.append(f"    - {title} ({url})")
        if removed_urls:
            lines.append("  Removed media files:")
            for url in removed_urls:
                item = previous_files_by_url[url]
                title = item.get("title") or url
                lines.append(f"    - {title} ({url})")

    summary_path = output_dir / filename
    summary_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return summary_path


def create_changes_summary_file(
    output_dir: Path,
    current_summary: Dict[str, Any],
    previous_report: Dict[str, Any],
    current_files: List[Dict[str, Any]],
) -> None:
    heading = f"Changes compared to previous report ({previous_report['path'].name}):"
    write_comparison_summary(
        output_dir,
        current_summary,
        previous_report,
        current_files,
        filename="changes_summary.txt",
        heading=heading,
        require_views_change=True,
    )


def create_monthly_comparison_file(
    output_dir: Path,
    current_summary: Dict[str, Any],
    current_files: List[Dict[str, Any]],
    reference_report: Dict[str, Any],
    reference_label: str,
) -> None:
    heading = (
        "Month-over-month changes compared to earliest report from "
        f"{reference_label} ({reference_report['path'].name}):"
    )
    write_comparison_summary(
        output_dir,
        current_summary,
        reference_report,
        current_files,
        filename="previous_month_summary.txt",
        heading=heading,
        require_views_change=False,
    )


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
    print(f"Setting month: {MONTH_FOR_FORM}")
    month_input = driver.find_element(By.ID, "month")
    month_input.clear()
    month_input.send_keys(MONTH_FOR_FORM)
    
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


def expand_full_results(driver):
    """Attempt to expand the report to show all files."""
    try:
        if "Showing only the top" not in driver.page_source:
            return

        show_all_link = WebDriverWait(driver, 10).until(
            EC.element_to_be_clickable(
                (By.XPATH, "//a[contains(., 'show all')]")
            )
        )
        show_all_link.click()
        print("Expanding to show all files...")

        def expanded(driver_instance):
            return "Showing only the top" not in driver_instance.page_source

        WebDriverWait(driver, 30).until(expanded)
        time.sleep(2)
        print("✓ Expanded to full file list")
    except Exception as e:
        print(f"Note: Could not expand to full file list: {e}")


def save_results(driver, previous_report: Optional[Dict[str, Any]]):
    """Save the results in various formats and annotate with differences."""
    BASE_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    base_dir_name = f"{YEAR}-{MONTH.zfill(2)}_{timestamp}"

    page_source = driver.page_source
    summary_stats = extract_summary_stats_from_html(page_source)
    file_entries = extract_file_entries_from_html(page_source)

    diff_label = compute_pages_diff_label(summary_stats, previous_report)
    final_dir_name = f"{base_dir_name}_{diff_label}"
    output_dir = BASE_OUTPUT_DIR / final_dir_name
    output_dir.mkdir(parents=True, exist_ok=False)

    html_file = output_dir / f"glamtools_results_{timestamp}.html"
    html_file.write_text(page_source, encoding="utf-8")
    print(f"Saved HTML: {html_file}")

    screenshot_file = output_dir / f"glamtools_screenshot_{timestamp}.png"
    driver.save_screenshot(str(screenshot_file))
    print(f"Saved screenshot: {screenshot_file}")

    table_data = []
    try:
        tables = driver.find_elements(By.TAG_NAME, "table")
        for table in tables:
            rows = table.find_elements(By.TAG_NAME, "tr")
            for row in rows:
                cells = row.find_elements(By.TAG_NAME, "td")
                if not cells:
                    cells = row.find_elements(By.TAG_NAME, "th")
                row_data = [cell.text for cell in cells]
                if row_data:
                    table_data.append(row_data)
    except Exception as e:
        print(f"Note: Could not extract table data: {e}")

    if table_data:
        json_file = output_dir / f"glamtools_data_{timestamp}.json"
        json_file.write_text(
            json.dumps(
                {
                    "category": CATEGORY,
                    "depth": DEPTH,
                    "year": YEAR,
                    "month": MONTH,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "summary": summary_stats,
                    "files": file_entries,
                    "table_data": table_data,
                },
                indent=2,
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        print(f"Saved JSON data: {json_file}")

    latest_html = output_dir / "latest.html"
    latest_html.write_text(page_source, encoding="utf-8")

    latest_screenshot = output_dir / "latest_screenshot.png"
    driver.save_screenshot(str(latest_screenshot))

    current_url = driver.current_url
    print(f"Current URL: {current_url}")

    previous_summary = previous_report.get("summary", {}) if previous_report else {}
    summary_differences = calculate_summary_differences(summary_stats, previous_summary)

    metadata = {
        "category": CATEGORY,
        "depth": DEPTH,
        "year": YEAR,
        "month": MONTH,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "url": current_url,
        "page_title": driver.title,
        "summary": summary_stats,
        "files": file_entries,
        "report_directory": output_dir.name,
        "previous_report_directory": previous_report["path"].name
        if previous_report
        else None,
        "diff_label": diff_label,
        "summary_differences": summary_differences,
    }

    metadata_file = output_dir / f"metadata_{timestamp}.json"
    metadata_file.write_text(json.dumps(metadata, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Saved metadata: {metadata_file}")

    if previous_report:
        create_changes_summary_file(output_dir, summary_stats, previous_report, file_entries)

    if IS_FIRST_DAY_OF_MONTH:
        reference_report = find_earliest_report_for_month(
            PREVIOUS_DATASET_YEAR, PREVIOUS_DATASET_MONTH
        )
        if reference_report:
            reference_label = (
                f"{PREVIOUS_DATASET_YEAR}-{str(PREVIOUS_DATASET_MONTH).zfill(2)}"
            )
            create_monthly_comparison_file(
                output_dir, summary_stats, file_entries, reference_report, reference_label
            )
        else:
            print(
                "No stored report found for the previous dataset month; skipping monthly summary."
            )

    return output_dir


def main():
    """Main execution function"""
    driver = None
    try:
        print("Starting GLAM Tools browser automation...")
        print(f"Category: {CATEGORY}")
        print(f"Depth: {DEPTH}")
        print(f"Year/Month: {YEAR}/{MONTH}\n")
        
        driver = setup_driver(headless=True)
        previous_report = get_latest_report()
        fill_form_and_submit(driver)
        wait_for_results(driver)
        expand_full_results(driver)
        output_dir = save_results(driver, previous_report)

        print("\n✓ Process completed successfully!")
        print(f"Results saved to {output_dir}/")

    except Exception as e:
        print(f"\n✗ Error occurred: {e}")
        if driver:
            # Save error screenshot
            BASE_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
            error_screenshot = BASE_OUTPUT_DIR / f"error_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}.png"
            try:
                driver.save_screenshot(str(error_screenshot))
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
