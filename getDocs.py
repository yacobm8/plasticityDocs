import os
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
import time
import threading
import sys
from collections import deque
from requests.adapters import HTTPAdapter
from urllib3.util import Retry

BASE_URL = "https://doc.plasticity.xyz/"
DOCS_DIR = "docs"
FAILED_URLS_FILE = "failed_urls.txt"
PAUSE_FLAG = threading.Event()
PAUSE_FLAG.set()  # Start unpaused
VISITED = set()

def url_to_filename(url):
    parsed = urlparse(url)
    path = parsed.path.strip("/")
    if not path:
        path = "index"
    filename = path.replace("/", "_") + ".txt"
    return filename

def save_text(url, text):
    filename = url_to_filename(url)
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

def create_session(retries=3, backoff_factor=0.5, status_forcelist=(500, 502, 503, 504)):
    session = requests.Session()
    retry = Retry(
        total=retries,
        backoff_factor=backoff_factor,
        status_forcelist=status_forcelist,
        allowed_methods=frozenset(['GET', 'POST'])
    )
    adapter = HTTPAdapter(max_retries=retry)
    session.mount('http://', adapter)
    session.mount('https://', adapter)
    session.headers.update({'User-Agent': 'plasticity-docs-downloader/1.0 (+https://github.com)'})
    return session


def crawl_iterative(start_url, session=None, timeout=10, polite_delay=0.5):
    if session is None:
        session = create_session()
    queue = deque([start_url])
    while queue:
        url = queue.popleft()
        if url in VISITED:
            continue
        if is_non_english_url(url):
            print(f"Skipping non-English page: {url}")
            VISITED.add(url)
            continue
        VISITED.add(url)
        filename = url_to_filename(url)
        filepath = os.path.join(DOCS_DIR, filename)
        try:
            print(f"Fetching: {url}")
            resp = session.get(url, timeout=timeout)
            resp.raise_for_status()
        except Exception as e:
            print(f"Failed to fetch {url}: {e}")
            log_failed_url(url)
            continue
        soup = BeautifulSoup(resp.text, 'html.parser')
        main = soup.find('main') or soup.body
        text = main.get_text(separator='\n', strip=True) if main else soup.get_text()
        # Save if not already present
        os.makedirs(DOCS_DIR, exist_ok=True)
        if os.path.exists(filepath):
            print(f"Already downloaded: {url}")
        else:
            print(f"Saving: {url} -> {filepath}")
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(text)
        # Enqueue internal links
        for a in soup.find_all('a', href=True):
            link = urljoin(url, a['href'])
            if link.startswith(BASE_URL) and not any(x in link for x in ['#', '.pdf', '.png', '.jpg', '.jpeg', '.svg']):
                if link not in VISITED:
                    queue.append(link)
        # Respect pause flag
        while not PAUSE_FLAG.is_set():
            print('Paused. Press spacebar to resume...')
            time.sleep(0.5)
        time.sleep(polite_delay)

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
    session = create_session()
    try:
        crawl_iterative(BASE_URL, session=session)
    except KeyboardInterrupt:
        print('\nInterrupted by user. Stopping crawl.')
    except Exception as e:
        print(f'Unexpected error: {e}')

if __name__ == "__main__":
    main()