import os
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
import time
import threading
import sys

BASE_URL = "https://doc.plasticity.xyz/"
DOCS_DIR = "docs"
FAILED_URLS_FILE = "failed_urls.txt"
PAUSE_FLAG = threading.Event()
PAUSE_FLAG.set()  # Start unpaused
VISITED = set()

def save_text(url, text):
    parsed = urlparse(url)
    path = parsed.path.strip("/")
    if not path:
        path = "index"
    filename = path.replace("/", "_") + ".txt"
    os.makedirs(DOCS_DIR, exist_ok=True)
    with open(os.path.join(DOCS_DIR, filename), "w", encoding="utf-8") as f:
        f.write(text)

def is_non_english_url(url):
    # Skip URLs with language codes like /de/, /ja/, /fr/, etc. after the base
    parsed = urlparse(url)
    path = parsed.path.lstrip("/")
    # List of known language codes to skip
    lang_codes = ["de", "ja", "fr", "es", "zh", "ko", "ru", "it", "pt", "pl", "nl", "tr", "cs", "ar", "sv", "fi", "no", "da", "el", "hu", "ro", "th", "vi", "id", "he"]
    if any(path.startswith(code + "/") or path == code for code in lang_codes):
        return True
    return False

def log_failed_url(url):
    with open(FAILED_URLS_FILE, "a", encoding="utf-8") as f:
        f.write(url + "\n")

def extract_and_save(url):
    if url in VISITED:
        return
    if is_non_english_url(url):
        print(f"Skipping non-English page: {url}")
        VISITED.add(url)
        return
    print(f"Downloading: {url}")
    VISITED.add(url)
    try:
        resp = requests.get(url)
        resp.raise_for_status()
    except Exception as e:
        print(f"Failed to fetch {url}: {e}")
        log_failed_url(url)
        return
    soup = BeautifulSoup(resp.text, "html.parser")
    # Extract main content (customize selector as needed)
    main = soup.find("main") or soup.body
    text = main.get_text(separator="\n", strip=True) if main else soup.get_text()
    save_text(url, text)
    # Find all internal doc links
    for a in soup.find_all("a", href=True):
        link = urljoin(url, a['href'])
        if link.startswith(BASE_URL) and not any(x in link for x in ["#", ".pdf", ".png", ".jpg", ".jpeg", ".svg"]):
            extract_and_save(link)
    # Pause if needed
    while not PAUSE_FLAG.is_set():
        print("Paused. Press spacebar to resume...")
        time.sleep(0.5)
    time.sleep(0.5)  # Be polite

def pause_listener():
    print("Press spacebar to pause/resume crawling.")
    while True:
        key = sys.stdin.read(1)
        if key == ' ':
            if PAUSE_FLAG.is_set():
                PAUSE_FLAG.clear()
                print("Paused.")
            else:
                PAUSE_FLAG.set()
                print("Resumed.")

def main():
    listener = threading.Thread(target=pause_listener, daemon=True)
    listener.start()
    extract_and_save(BASE_URL)

if __name__ == "__main__":
    main()