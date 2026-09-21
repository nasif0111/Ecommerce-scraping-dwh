import os
import re
import time
import subprocess
import urllib.request
from urllib.parse import urljoin, urlparse, parse_qs

from openpyxl import Workbook
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By


START_URL = "https://www.jumia.com.eg/ar/all-products/?tag=B2S_9"

CHROME_PATH = r"C:\Program Files\Google\Chrome\Application\chrome.exe"

REMOTE_DEBUGGING_PORT = 9222

PROFILE_PATH = os.path.join(
    os.environ["LOCALAPPDATA"],
    "JumiaScrapingProfile"
)

OUTPUT_FILE = "jumia_products_pages_1_to_10.xlsx"

MAX_PAGE = 10


def start_chrome_remote_debugging():
    """Start a separate Chrome profile with Remote Debugging."""

    command = [
        CHROME_PATH,
        f"--remote-debugging-port={REMOTE_DEBUGGING_PORT}",
        f"--user-data-dir={PROFILE_PATH}",
        "--remote-debugging-address=127.0.0.1",
    ]

    subprocess.Popen(
        command,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )

    print("Starting Chrome with Remote Debugging...")

    endpoint = (
        f"http://127.0.0.1:"
        f"{REMOTE_DEBUGGING_PORT}/json/version"
    )

    for _ in range(30):

        try:

            with urllib.request.urlopen(
                endpoint,
                timeout=1
            ) as response:

                if response.status == 200:

                    print(
                        "Remote Debugging is ready."
                    )

                    return

        except Exception:

            time.sleep(0.5)

    raise RuntimeError(
        "Could not connect to Chrome "
        "Remote Debugging on port 9222."
    )


def connect_selenium():
    """Connect Selenium to Chrome Remote Debugging."""

    options = Options()

    options.add_experimental_option(
        "debuggerAddress",
        f"127.0.0.1:{REMOTE_DEBUGGING_PORT}",
    )

    print("Connecting Selenium to Chrome...")

    driver = webdriver.Chrome(
        options=options
    )

    print(
        "Selenium connected successfully."
    )

    return driver


def clean_text(text):
    """Clean text from extra spaces."""

    if not text:
        return None

    return " ".join(text.split()).strip()


def extract_number(text):
    """Extract the first numeric value from text."""

    if not text:
        return None

    text = text.replace(",", "")

    match = re.search(
        r"(\d+(?:\.\d+)?)",
        text
    )

    if match:
        return float(match.group(1))

    return None


def get_current_page_number(driver):
    """Get the current page number from the URL."""

    current_url = driver.current_url

    parsed_url = urlparse(current_url)

    query = parse_qs(parsed_url.query)

    page = query.get("page")

    if page:
        try:
            return int(page[0])
        except ValueError:
            pass

    return 1


def scroll_to_bottom(driver, duration=3):
    """
    Scroll from current position to bottom
    over approximately 3 seconds.
    """

    print("Scrolling to bottom...")

    start_position = driver.execute_script(
        "return window.pageYOffset;"
    )

    total_height = driver.execute_script(
        "return Math.max("
        "document.body.scrollHeight,"
        "document.documentElement.scrollHeight"
        ");"
    )

    steps = max(
        30,
        int(duration * 10)
    )

    for step in range(1, steps + 1):

        position = (
            start_position
            + (
                (total_height - start_position)
                * step
                / steps
            )
        )

        driver.execute_script(
            "window.scrollTo(0, arguments[0]);",
            position,
        )

        time.sleep(
            duration / steps
        )

    time.sleep(2)

    print("Reached bottom.")


def scrape_while_scrolling_up(driver):
    """
    Scrape unique products while moving
    upward from the bottom.
    """

    print(
        "Starting scraping while moving upward..."
    )

    selector = (
        "article.prd._fb.col.c-prd"
    )

    products = {}

    current_position = driver.execute_script(
        "return window.pageYOffset;"
    )

    viewport_height = driver.execute_script(
        "return window.innerHeight;"
    )

    step = max(
        200,
        int(viewport_height * 0.75)
    )

    while True:

        cards = driver.find_elements(
            By.CSS_SELECTOR,
            selector
        )

        for card in cards:

            try:

                product = extract_product(
                    card,
                    driver
                )

                unique_key = (
                    product["SKU"]
                    or product["Product URL"]
                    or product["Product Name"]
                )

                if (
                    unique_key
                    and unique_key not in products
                ):

                    products[unique_key] = product

            except Exception as error:

                print(
                    f"Skipping product: {error}"
                )

        if current_position <= 0:
            break

        next_position = max(
            0,
            current_position - step
        )

        driver.execute_script(
            "window.scrollTo(0, arguments[0]);",
            next_position,
        )

        time.sleep(0.6)

        current_position = next_position

    print(
        f"Products collected on page: "
        f"{len(products)}"
    )

    return list(products.values())


def extract_product(card, driver):
    """Extract product data from one card."""

    sku = card.get_attribute(
        "data-sku"
    )

    core_links = card.find_elements(
        By.CSS_SELECTOR,
        "a.core"
    )

    product_url = None

    if core_links:

        product_url = (
            core_links[0]
            .get_attribute("href")
        )

        if product_url:

            product_url = urljoin(
                START_URL,
                product_url
            )

        if not sku:

            sku = (
                core_links[0]
                .get_attribute("data-gtm-id")
            )

    images = card.find_elements(
        By.CSS_SELECTOR,
        "div.img-c img.img"
    )

    image_url = None

    if images:

        image_url = (
            images[0].get_attribute("src")
            or images[0].get_attribute("data-src")
        )

    names = card.find_elements(
        By.CSS_SELECTOR,
        "h3.name"
    )

    product_name = (
        clean_text(names[0].text)
        if names
        else None
    )

    prices = card.find_elements(
        By.CSS_SELECTOR,
        "div.prc"
    )

    current_price = (
        extract_number(prices[0].text)
        if prices
        else None
    )

    old_prices = card.find_elements(
        By.CSS_SELECTOR,
        "div.s-prc-w div.old"
    )

    old_price = (
        extract_number(old_prices[0].text)
        if old_prices
        else None
    )

    discounts = card.find_elements(
        By.CSS_SELECTOR,
        "div.bdg._dsct._sm"
    )

    discount_percentage = (
        extract_number(discounts[0].text)
        if discounts
        else None
    )

    rating = None

    rating_elements = card.find_elements(
        By.CSS_SELECTOR,
        "div.rev div.stars._s"
    )

    if rating_elements:

        rating_text = (
            clean_text(
                rating_elements[0].text
            )
            or ""
        )

        match = re.search(
            r"(\d+(?:\.\d+)?)\s*out of\s*5",
            rating_text,
            re.IGNORECASE,
        )

        if match:

            rating = float(
                match.group(1)
            )

    reviews_count = None

    review_elements = card.find_elements(
        By.CSS_SELECTOR,
        "div.rev"
    )

    if review_elements:

        review_text = (
            clean_text(
                review_elements[0].text
            )
            or ""
        )

        match = re.search(
            r"\((\d+)\)",
            review_text
        )

        if match:

            reviews_count = int(
                match.group(1)
            )

    return {

        "SKU": sku,

        "Product Name": product_name,

        "Image URL": image_url,

        "Product URL": product_url,

        "Current Price": current_price,

        "Old Price": old_price,

        "Discount %": discount_percentage,

        "Rating": rating,

        "Reviews Count": reviews_count,
    }


def get_next_page_url(driver):
    """
    Get the URL of the next page
    using the actual next-page button.
    """

    next_buttons = driver.find_elements(
        By.CSS_SELECTOR,
        'a.pg[aria-label="الصفحة التالية"]'
    )

    if not next_buttons:

        return None

    href = next_buttons[0].get_attribute(
        "href"
    )

    if not href:

        return None

    return urljoin(
        START_URL,
        href
    )


def wait_for_page_change(
    driver,
    old_url,
    timeout=15
):
    """Wait until the URL changes."""

    start_time = time.time()

    while time.time() - start_time < timeout:

        if driver.current_url != old_url:

            return True

        time.sleep(0.5)

    return False


def scrape_page(driver, page_number):
    """Scrape one complete page."""

    print()
    print("=" * 60)
    print(
        f"START PAGE {page_number}"
    )
    print("=" * 60)

    time.sleep(3)

    scroll_to_bottom(
        driver,
        duration=3
    )

    products = scrape_while_scrolling_up(
        driver
    )

    print(
        f"PAGE {page_number} DONE "
        f"→ {len(products)} products"
    )

    return products


def save_to_excel(products):
    """Save all scraped products to Excel."""

    print()
    print("Creating Excel file...")

    workbook = Workbook()

    sheet = workbook.active

    sheet.title = "Jumia Products"

    headers = [

        "SKU",

        "Product Name",

        "Image URL",

        "Product URL",

        "Current Price",

        "Old Price",

        "Discount %",

        "Rating",

        "Reviews Count",
    ]

    sheet.append(headers)

    for product in products:

        sheet.append(
            [
                product[header]
                for header in headers
            ]
        )

    sheet.freeze_panes = "A2"

    sheet.auto_filter.ref = (
        sheet.dimensions
    )

    widths = {

        "A": 28,

        "B": 70,

        "C": 90,

        "D": 90,

        "E": 18,

        "F": 18,

        "G": 15,

        "H": 12,

        "I": 15,
    }

    for column, width in widths.items():

        sheet.column_dimensions[
            column
        ].width = width

    workbook.save(
        OUTPUT_FILE
    )

    print(
        f"Excel saved: {OUTPUT_FILE}"
    )


def main():

    all_products = {}

    start_chrome_remote_debugging()

    driver = connect_selenium()

    try:

        print()
        print(
            "Opening Jumia starter URL..."
        )

        driver.get(
            START_URL
        )

        time.sleep(4)

        for page_number in range(
            1,
            MAX_PAGE + 1
        ):

            actual_page = (
                get_current_page_number(
                    driver
                )
            )

            if actual_page != page_number:

                print(
                    f"Warning: expected page "
                    f"{page_number}, "
                    f"but current page is "
                    f"{actual_page}"
                )

            page_products = scrape_page(
                driver,
                page_number
            )

            for product in page_products:

                unique_key = (
                    product["SKU"]
                    or product["Product URL"]
                    or product["Product Name"]
                )

                if (
                    unique_key
                    and unique_key not in all_products
                ):

                    all_products[
                        unique_key
                    ] = product

            print(
                f"TOTAL UNIQUE PRODUCTS: "
                f"{len(all_products)}"
            )

            if page_number == MAX_PAGE:

                print()
                print(
                    "Reached page 10."
                )

                break

            next_page_url = (
                get_next_page_url(
                    driver
                )
            )

            if not next_page_url:

                raise RuntimeError(
                    "Next page button was not found."
                )

            print()
            print(
                f"Moving from page "
                f"{page_number} "
                f"to page "
                f"{page_number + 1}..."
            )

            old_url = driver.current_url

            driver.get(
                next_page_url
            )

            changed = wait_for_page_change(
                driver,
                old_url
            )

            if not changed:

                print(
                    "URL did not change, "
                    "but navigation command "
                    "was sent."
                )

            time.sleep(3)

        save_to_excel(
            list(all_products.values())
        )

        print()
        print("=" * 60)
        print(
            "SCRAPING COMPLETED"
        )
        print(
            f"Total unique products: "
            f"{len(all_products)}"
        )
        print(
            f"Excel file: "
            f"{OUTPUT_FILE}"
        )
        print("=" * 60)

    finally:

        driver.quit()


if __name__ == "__main__":

    main()