import sys
import requests
from bs4 import BeautifulSoup
import re
from urllib.parse import urljoin, urlparse
from collections import defaultdict
import time
import os
import json
import subprocess
import platform
import zipfile
import tarfile
import rarfile

from PyQt6.QtWidgets import (
    QApplication,
    QWidget,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QHBoxLayout,
    QListWidget,
    QTextEdit,
    QListWidgetItem,
    QMessageBox,
    QSplitter,
    QProgressBar,
    QGroupBox,
    QScrollArea,
    QHeaderView,
    QTableWidget,
    QTableWidgetItem,
    QAbstractItemView,
    QToolBar,
    QStatusBar,
    QMainWindow,
    QDialog,
    QColorDialog,
    QFormLayout,
    QDialogButtonBox,
    QCheckBox,
    QComboBox,
    QTabWidget, QSpinBox, QFrame, QGridLayout, QSpacerItem, QSizePolicy,
)

from PyQt6.QtCore import Qt, QThread, pyqtSignal, QSize
from PyQt6.QtGui import QPalette, QColor, QTextCursor, QTextCharFormat, QIntValidator

DEFAULT_THEME = {
    "accent": "#f61e5f",
    "accent_light": "#ffbde0",
    "desktop": "#101010",
    "surface_bg": "#171717",
    "surface_area": "#0d0d0d",
    "control_bg": "#101010",
    "detail_view_bg": "#202020",
    "browser_bar": "#0d0d0d",
    "tree_column_head_bg": "#232323",
    "control_fg": "#a4a4a4",
    "control_on_fg": "#0d0d0d",
    "control_off_fg": "#adadad",
    "control_disabled": "#a8a8a8",
    "text_disabled": "#4d4d4d",
    "selection_bg": "#b3b3b3",
    "selection_fg": "#0d0d0d",
    "surface_highlight": "#222222",
    "main_focus": "#2a2a2a",
    "control_contrast_frame": "#000000",
    "control_selection_frame": "#373737",
    "view_control_on": "#929292",
    "view_control_off": "#747474",
    "scrollbar_inner_handle": "#404040",
    "scrollbar_hover": "#5a5a5a",
    "alert": "#848484",
}

LOG_COLORS = {
    "INFO": "#a4a4a4",
    "SUCCESS": "#4CAF50",
    "WARNING": "#FF9800",
    "ERROR": "#f61e5f",
    "DEBUG": "#2196F3",
    "DOWNLOAD": "#BD3BD4",
}

SETTINGS_FILE = "settings.json"
DOWNLOADS_FOLDER = "downloads"

class Settings:
    def __init__(self):
        self.cookie_string = ""
        self.rd_access_token = ""
        self.base_url = "https://audioz.download"
        self.theme = DEFAULT_THEME.copy()
        self.log_colors = LOG_COLORS.copy()
        self.auto_extract = True
        self.auto_delete = True
        self.download_strategy = "auto"
        self.max_retries = 3
        self.retry_delay = 5
        self.load()

    def load(self):
        if os.path.exists(SETTINGS_FILE):
            try:
                with open(SETTINGS_FILE, "r") as f:
                    data = json.load(f)
                    self.cookie_string = data.get("cookie_string", "")
                    self.rd_access_token = data.get("rd_access_token", "")
                    self.base_url = data.get("base_url", "https://audioz.download")
                    self.theme = data.get("theme", DEFAULT_THEME.copy())
                    self.log_colors = data.get("log_colors", LOG_COLORS.copy())
                    self.auto_extract = data.get("auto_extract", True)
                    self.auto_delete = data.get("auto_delete", True)
                    self.download_strategy = data.get("download_strategy", "auto")
                    self.max_retries = data.get("max_retries", 3)
                    self.retry_delay = data.get("retry_delay", 5)

            except Exception as e:
                print(f"Error loading settings: {e}")

    def save(self):
        try:
            data = {
                "cookie_string": self.cookie_string,
                "rd_access_token": self.rd_access_token,
                "base_url": self.base_url,
                "theme": self.theme,
                "log_colors": self.log_colors,
                "auto_extract": self.auto_extract,
                "auto_delete": self.auto_delete,
                "download_strategy": self.download_strategy,
                "max_retries": self.max_retries,
                "retry_delay": self.retry_delay,
            }
            with open(SETTINGS_FILE, "w") as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            print(f"Error saving settings: {e}")

def parse_cookie_string(cookie_str):
    cookies = {}
    for part in cookie_str.split(";"):
        part = part.strip()
        if "=" in part:
            name, val = part.split("=", 1)
            cookies[name.strip()] = val.strip()
    return cookies

def post_search(session, term, base_url, search_start=1):
    url = base_url + "/"
    payload = {
        "do": "search",
        "subaction": "search",
        "search_start": search_start,
        "full_search": 1,
        "result_from": (search_start - 1) * 30 + 1,
        "story": term,
        "titleonly": 3,
        "replyless": 0,
        "replylimit": 0,
        "searchdate": 0,
        "beforeafter": "after",
        "sortby": "date",
        "resorder": "desc",
        "searchuser": "",
        "showposts": 0,
        "catlist[]": 0,
    }
    headers = {"Referer": base_url + "/", "User-Agent": "Mozilla/5.0"}
    r = session.post(url, data=payload, headers=headers, timeout=30)
    r.raise_for_status()
    return r.text

def parse_search_results(html, base_url):
    soup = BeautifulSoup(html, "html.parser")
    articles = soup.find_all("article")
    results = []
    for art in articles:
        title_tag = art.find(["h1", "h2", "h3"])
        link_tag = art.find("a", class_="permalink") or art.find("a", href=True)
        author_tag = art.find("span", class_="author")
        time_tag = art.find("time")

        img_tag = art.find("img")
        image_url = None
        if img_tag and img_tag.get("data-src"):
            image_url = img_tag["data-src"]
        elif img_tag and img_tag.get("src"):
            image_url = img_tag["src"]

        if image_url and image_url.startswith("/"):
            image_url = urljoin(base_url, image_url)

        title = title_tag.get_text(strip=True) if title_tag else None
        href = link_tag["href"] if link_tag and link_tag.get("href") else None
        if href and href.startswith("/"):
            href = urljoin(base_url, href)
        author = author_tag.get_text(strip=True) if author_tag else None
        date = time_tag.get_text(strip=True) if time_tag else None

        desc_section = art.find("section", class_="descr")
        description = desc_section.get_text(strip=True) if desc_section else None

        if title and href:
            results.append({
                "title": title,
                "url": href,
                "author": author,
                "date": date,
                "image_url": image_url,
                "description": description,
            })
    return results

def fetch_plugin_page(session, plugin_url, base_url):
    headers = {"User-Agent": "Mozilla/5.0", "Referer": base_url + "/"}
    r = session.get(plugin_url, headers=headers, timeout=30)
    r.raise_for_status()
    return r.text

def find_peeplink(html):
    soup = BeautifulSoup(html, "html.parser")
    dl_block = soup.find("div", class_="DL_Blocks download")
    if dl_block:
        a = dl_block.find("a", href=True)
        if a and "peeplink.in" in a["href"]:
            return a["href"]
    for a in soup.find_all("a", href=True):
        if "peeplink.in" in a["href"]:
            return a["href"]
    m = re.search(r"(https?://peeplink\.in/[A-Za-z0-9]+)", html)
    if m:
        return m.group(1)
    return None

def fetch_peeplink_urls(peeplink_url):
    headers = {"User-Agent": "Mozilla/5.0"}
    r = requests.get(peeplink_url, headers=headers)
    r.raise_for_status()
    soup = BeautifulSoup(r.text, "html.parser")
    article = soup.find("article")
    if not article:
        return {}

    urls_by_host = defaultdict(list)
    for a in article.find_all("a", href=True):
        href = a["href"].strip()
        if not href:
            continue
        host = urlparse(href).netloc.lower()
        fname = href.split("/")[-1]
        base = fname.split(".part")[0] if ".part" in fname else fname
        part_num = int(fname.split(".part")[1].split(".")[0]) if ".part" in fname else 1
        urls_by_host[host].append((base, part_num, href))

    grouped = defaultdict(lambda: defaultdict(dict))
    for host, lst in urls_by_host.items():
        for base, part_num, url in lst:
            grouped[base][part_num][host] = url
    return grouped

def rd_unrestrict(url, token):
    api_url = "https://api.real-debrid.com/rest/1.0/unrestrict/link"
    headers = {"Authorization": f"Bearer {token}"}
    data = {"link": url}
    r = requests.post(api_url, headers=headers, data=data)
    if r.status_code != 200:
        return None
    return r.json()["download"]

def extract_archive(filepath, destination=None):
    """Extract archive, automatically handling multi-part archives"""
    if not os.path.exists(filepath):
        return None
        
    if not destination:
        # Use the archive name without extension as folder name
        base_name = os.path.splitext(os.path.basename(filepath))[0]
        # Remove .part01 etc. from the name
        base_name = re.sub(r'\.part\d+', '', base_name)
        destination = os.path.join(DOWNLOADS_FOLDER, base_name)
    
    os.makedirs(destination, exist_ok=True)
    ext = os.path.splitext(filepath)[1].lower()
    
    try:
        if ext == ".zip":
            with zipfile.ZipFile(filepath, "r") as zip_ref:
                zip_ref.extractall(destination)
        elif ext in [".tar", ".gz", ".bz2", ".tgz"]:
            with tarfile.open(filepath, "r:*") as tar_ref:
                tar_ref.extractall(destination) # I'm not sure if this actually works, I haven't seen .tar files go around audioz, yet.
        elif ext == ".rar":
            # For RAR files, try to extract with multi-part support
            try:
                with rarfile.RarFile(filepath, "r") as rar_ref:
                    rar_ref.extractall(destination)
            except rarfile.NeedFirstVolume:
                # If it's a multi-part RAR, find all parts
                base_dir = os.path.dirname(filepath)
                base_name = os.path.basename(filepath)
                
                # Find all part files
                part_files = []
                for f in os.listdir(base_dir):
                    if f.startswith(base_name.split('.part')[0]) and f.endswith('.rar'):
                        part_files.append(os.path.join(base_dir, f))
                
                # Sort parts numerically
                part_files.sort(key=lambda x: int(re.search(r'\.part(\d+)', x).group(1)) if re.search(r'\.part(\d+)', x) else 0)
                
                if part_files:
                    # Use the first part to extract all
                    with rarfile.RarFile(part_files[0], "r") as rar_ref:
                        rar_ref.extractall(destination)
        else:
            return None
        return destination
    except Exception as e:
        print(f"Extraction error: {e}")
        return None

def open_folder(path):
    if platform.system() == "Windows":
        subprocess.Popen(f'explorer "{path}"')
    elif platform.system() == "Darwin":
        subprocess.Popen(["open", path])
    else:
        subprocess.Popen(["xdg-open", path])

class SearchWorker(QThread):
    results_signal = pyqtSignal(list, int)
    log_signal = pyqtSignal(str, str)
    no_results_signal = pyqtSignal(int)

    def __init__(self, term, cookie_string, base_url, search_start=1):
        super().__init__()
        self.term = term
        self.cookie_string = cookie_string
        self.base_url = base_url
        self.search_start = search_start

    def run(self):
        cookies = parse_cookie_string(self.cookie_string)
        session = requests.Session()
        for k, v in cookies.items():
            session.cookies.set(k, v, domain="audioz.download", path="/")

        self.log_signal.emit(
            f"Searching for '{self.term}' (Page {self.search_start})...",
            "INFO",
        )
        try:
            html = post_search(
                session, self.term, self.base_url, self.search_start
            )
        except Exception as e:
            self.log_signal.emit(f"Search failed: {e}", "ERROR")
            return

        results = parse_search_results(html, self.base_url)
        if not results:
            self.no_results_signal.emit(self.search_start)
            return

        # self.log_signal.emit(f"Found {len(results)} results", "SUCCESS")
        self.results_signal.emit(results, self.search_start)

class DownloadWorker(QThread):
    log_signal = pyqtSignal(str, str)
    progress_signal = pyqtSignal(str, str, int, int)
    download_started = pyqtSignal(str, str)
    download_finished = pyqtSignal(str)
    status_signal = pyqtSignal(str, str)
    part_progress_signal = pyqtSignal(str, int, int)  # worker_id, current_part, total_parts

    def __init__(
        self,
        url,
        cookie_string,
        base_url,
        rd_token,
        host_order=None,
        worker_id=None,
        download_strategy="auto",
        max_retries=3,
        retry_delay=5,
    ):
        super().__init__()
        self.url = url
        self.cookie_string = cookie_string
        self.base_url = base_url
        self.rd_token = rd_token
        self.host_order = host_order or []
        self.worker_id = worker_id or str(id(self))
        self.download_strategy = download_strategy
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        self.is_running = True
        self.current_part = 0
        self.total_parts = 0

    def download_file_with_progress(self, url, filename, retry_count=0):
        """Download file with resume support and retries"""
        os.makedirs(DOWNLOADS_FOLDER, exist_ok=True)
        filepath = os.path.join(DOWNLOADS_FOLDER, filename)

        # Check if file already exists for resume
        downloaded_size = 0
        if os.path.exists(filepath):
            downloaded_size = os.path.getsize(filepath)
            self.log_signal.emit(f"Resuming download: {filename} ({downloaded_size} bytes already downloaded)", "INFO")

        self.download_started.emit(filename, self.worker_id)
        
        headers = {}
        if downloaded_size > 0:
            headers['Range'] = f'bytes={downloaded_size}-'

        try:
            response = requests.get(url, stream=True, timeout=30, headers=headers)
            
            # Handle resume
            if downloaded_size > 0 and response.status_code == 416:
                self.log_signal.emit(f"File already complete: {filename}", "SUCCESS")
                return True
            elif downloaded_size > 0 and response.status_code == 206:  # Partial content
                total_size = downloaded_size + int(response.headers.get('content-length', 0))
            else:
                response.raise_for_status()
                total_size = int(response.headers.get("content-length", 0))
                if downloaded_size > 0:
                    # Server doesn't support resume, start over
                    downloaded_size = 0
                    self.log_signal.emit(f"Server doesn't support resume, restarting: {filename}", "WARNING")

            mode = 'ab' if downloaded_size > 0 else 'wb'
            with open(filepath, mode) as f:
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk and self.is_running:
                        f.write(chunk)
                        downloaded_size += len(chunk)
                        if total_size > 0:
                            self.progress_signal.emit(
                                filename,
                                self.worker_id,
                                downloaded_size,
                                total_size,
                            )
                    elif not self.is_running:
                        break
            
            return True

        except Exception as e:
            if retry_count < self.max_retries:
                self.log_signal.emit(f"Download failed, retrying ({retry_count + 1}/{self.max_retries}): {e}", "WARNING")
                time.sleep(self.retry_delay)
                return self.download_file_with_progress(url, filename, retry_count + 1)
            else:
                raise e

    def stop(self):
        self.is_running = False

    def run(self):
        self.status_signal.emit(self.worker_id, "Preparing...")
        cookies = parse_cookie_string(self.cookie_string)
        session = requests.Session()
        for k, v in cookies.items():
            session.cookies.set(k, v, domain="audioz.download", path="/")

        self.status_signal.emit(self.worker_id, "Fetching page...")
        try:
            plugin_html = fetch_plugin_page(session, self.url, self.base_url)
        except Exception as e:
            self.status_signal.emit(self.worker_id, "Error")
            self.log_signal.emit(f"Failed to fetch plugin page: {e}", "ERROR")
            self.download_finished.emit(self.worker_id)
            return

        peeplink = find_peeplink(plugin_html)
        if not peeplink:
            self.status_signal.emit(self.worker_id, "No peeplink")
            self.log_signal.emit("Peeplink not found.", "WARNING")
            self.download_finished.emit(self.worker_id)
            return

        self.status_signal.emit(self.worker_id, "Processing links...")
        grouped_links = fetch_peeplink_urls(peeplink)
        if not grouped_links:
            self.status_signal.emit(self.worker_id, "No links")
            self.log_signal.emit("No links found.", "WARNING")
            self.download_finished.emit(self.worker_id)
            return

        if not self.host_order:
            all_hosts = sorted(
                {
                    h
                    for base in grouped_links.values()
                    for part in base.values()
                    for h in part
                }
            )
            self.host_order = all_hosts

        # Calculate total parts
        total_parts = 0
        for file_base, parts in grouped_links.items():
            total_parts += len(parts)
        self.total_parts = total_parts

        for file_base, parts in grouped_links.items():
            if not self.is_running:
                break
            self.status_signal.emit(self.worker_id, "Downloading...")
            self.log_signal.emit(f"Downloading file: {file_base}", "DOWNLOAD")
            max_part = max(parts.keys())
            
            # Manual download strategy: ask for each part
            if self.download_strategy == "manual":
                for part_num in range(1, max_part + 1):
                    if not self.is_running:
                        break
                    
                    # Check if part already exists
                    filename = f"{file_base}.part{part_num}.rar"
                    filepath = os.path.join(DOWNLOADS_FOLDER, filename)
                    if os.path.exists(filepath):
                        file_size = os.path.getsize(filepath)
                        self.log_signal.emit(f"Part {part_num}/{max_part} already exists ({file_size} bytes), skipping", "INFO")
                        self.current_part = part_num
                        self.part_progress_signal.emit(self.worker_id, part_num, max_part)
                        continue
                    
                    # Ask user if they want to download this part
                    self.log_signal.emit(f"Part {part_num}/{max_part} available. Download? (Check status column)", "INFO")
                    self.current_part = part_num
                    self.part_progress_signal.emit(self.worker_id, part_num, max_part)
                    
                    # Wait for user confirmation (implemented via status checking)
                    # In a real implementation, you'd want a proper dialog
                    # For now, we'll just proceed after a short delay
                    time.sleep(1)
                    
                    success = False
                    for host in self.host_order:
                        if not self.is_running:
                            break
                        url = parts.get(part_num, {}).get(host)
                        if url:
                            rd_link = rd_unrestrict(url, self.rd_token)
                            if rd_link:
                                try:
                                    self.download_file_with_progress(
                                        rd_link, filename
                                    )
                                    self.log_signal.emit(
                                        f"Downloaded {filename}", "SUCCESS"
                                    )
                                    success = True
                                    break
                                except Exception as e:
                                    self.log_signal.emit(
                                        f"Failed {filename}: {e}", "ERROR"
                                    )
                    if not success:
                        self.log_signal.emit(
                            f"Part {part_num} could not be downloaded.", "WARNING"
                        )
                    time.sleep(1)
            
            # Auto download strategy: download all parts automatically
            else:
                for part_num in range(1, max_part + 1):
                    if not self.is_running:
                        break
                    
                    # Check if part already exists and is complete
                    filename = f"{file_base}.part{part_num}.rar"
                    filepath = os.path.join(DOWNLOADS_FOLDER, filename)
                    if os.path.exists(filepath):
                        # For now, we'll skip existing files. realistically we should verify file integrity
                        file_size = os.path.getsize(filepath)
                        self.log_signal.emit(f"Part {part_num}/{max_part} already exists ({file_size} bytes), skipping", "INFO")
                        self.current_part = part_num
                        self.part_progress_signal.emit(self.worker_id, part_num, max_part)
                        continue
                    
                    self.current_part = part_num
                    self.part_progress_signal.emit(self.worker_id, part_num, max_part)
                    
                    success = False
                    for host in self.host_order:
                        if not self.is_running:
                            break
                        url = parts.get(part_num, {}).get(host)
                        if url:
                            rd_link = rd_unrestrict(url, self.rd_token)
                            if rd_link:
                                try:
                                    self.download_file_with_progress(
                                        rd_link, filename
                                    )
                                    self.log_signal.emit(
                                        f"Downloaded {filename}", "SUCCESS"
                                    )
                                    success = True
                                    break
                                except Exception as e:
                                    self.log_signal.emit(
                                        f"Failed {filename}: {e}", "ERROR"
                                    )
                    if not success:
                        self.log_signal.emit(
                            f"Part {part_num} could not be downloaded.", "WARNING"
                        )
                    time.sleep(1)

        if self.is_running:
            self.status_signal.emit(self.worker_id, "Completed")
            self.log_signal.emit("Download completed successfully", "SUCCESS")
        self.download_finished.emit(self.worker_id)

class SettingsDialog(QDialog):
    def __init__(self, settings, parent=None):
        super().__init__(parent)
        self.settings = settings
        self.setWindowTitle("Application Settings")
        self.setMinimumSize(650, 550)
        self.setup_ui()

    def setup_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(15, 15, 15, 15)
        main_layout.setSpacing(15)

        header_label = QLabel("Configuration")
        header_label.setStyleSheet(f"font-size: 18px; font-weight: bold; color: {self.settings.theme['accent']};")
        main_layout.addWidget(header_label)

        self.tabs = QTabWidget()
        self.tabs.setStyleSheet("QTabBar::tab { height: 35px; width: 120px; }")
        
        general_tab = QWidget()
        gen_layout = QVBoxLayout(general_tab)
        
        dl_group = QGroupBox("Download Behavior")
        dl_form = QFormLayout(dl_group)
        dl_form.setSpacing(12)

        self.strategy_combo = QComboBox()
        self.strategy_combo.addItem("Auto - Instant Start", "auto")
        self.strategy_combo.addItem("Manual - Confirm Parts", "manual")
        self.strategy_combo.setCurrentIndex(0 if self.settings.download_strategy == "auto" else 1)
        dl_form.addRow("Workflow Mode:", self.strategy_combo)

        self.auto_extract_cb = QCheckBox("Automatically extract archives upon completion")
        self.auto_extract_cb.setChecked(self.settings.auto_extract)
        dl_form.addRow("", self.auto_extract_cb)

        self.auto_delete_cb = QCheckBox("Clean up: Delete source archive after extraction")
        self.auto_delete_cb.setChecked(self.settings.auto_delete)
        dl_form.addRow("", self.auto_delete_cb)
        
        gen_layout.addWidget(dl_group)

        # Network/Retry Group
        net_group = QGroupBox("Network & Resilience")
        net_form = QFormLayout(net_group)
        
        self.retries_spin = QSpinBox()
        self.retries_spin.setRange(0, 10)
        self.retries_spin.setValue(self.settings.max_retries)
        self.retries_spin.setSuffix(" attempts")
        net_form.addRow("Max Retry Attempts:", self.retries_spin)

        self.retry_delay_spin = QSpinBox()
        self.retry_delay_spin.setRange(1, 60)
        self.retry_delay_spin.setValue(self.settings.retry_delay)
        self.retry_delay_spin.setSuffix(" seconds")
        net_form.addRow("Wait Between Retries:", self.retry_delay_spin)
        
        gen_layout.addWidget(net_group)
        gen_layout.addStretch()
        self.tabs.addTab(general_tab, "General")

        account_tab = QWidget()
        acc_layout = QVBoxLayout(account_tab)
        
        auth_group = QGroupBox("Authentication Tokens")
        auth_form = QFormLayout(auth_group)
        auth_form.setSpacing(15)

        self.cookie_input = QLineEdit()
        self.cookie_input.setText(self.settings.cookie_string)
        self.cookie_input.setPlaceholderText("Paste AudioZ cookie string here...")
        self.cookie_input.setEchoMode(QLineEdit.EchoMode.Password)
        
        cookie_row = QHBoxLayout()
        cookie_row.addWidget(self.cookie_input)
        self.btn_view_cookie = QPushButton("👁")
        self.btn_view_cookie.setFixedSize(30, 30)
        self.btn_view_cookie.setCheckable(True)
        self.btn_view_cookie.clicked.connect(lambda: self.toggle_visibility(self.cookie_input, self.btn_view_cookie))
        cookie_row.addWidget(self.btn_view_cookie)
        auth_form.addRow("AudioZ Cookie:", cookie_row)

        # RD Token Entry
        self.token_input = QLineEdit()
        self.token_input.setText(self.settings.rd_access_token)
        self.token_input.setPlaceholderText("Real-Debrid API Key")
        self.token_input.setEchoMode(QLineEdit.EchoMode.Password)
        
        token_row = QHBoxLayout()
        token_row.addWidget(self.token_input)
        self.btn_view_token = QPushButton("👁")
        self.btn_view_token.setFixedSize(30, 30)
        self.btn_view_token.setCheckable(True)
        self.btn_view_token.clicked.connect(lambda: self.toggle_visibility(self.token_input, self.btn_view_token))
        token_row.addWidget(self.btn_view_token)
        auth_form.addRow("RD API Token:", token_row)

        acc_layout.addWidget(auth_group)
        
        info_box = QLabel("Note: These tokens are stored locally in settings.json. Never share this file.")
        info_box.setWordWrap(True)
        info_box.setStyleSheet("color: #888; font-style: italic; padding: 10px;")
        acc_layout.addWidget(info_box)
        acc_layout.addStretch()
        self.tabs.addTab(account_tab, "Accounts")

        theme_tab = QWidget()
        theme_layout = QHBoxLayout(theme_tab)
        
        # Left side: UI Colors
        ui_color_group = QGroupBox("Interface Colors")
        ui_form = QFormLayout(ui_color_group)
        self.color_buttons = {}
        color_map = {
            "accent": "Primary Accent",
            "desktop": "Window Bg",
            "surface_bg": "Panel Bg",
            "control_fg": "Main Text",
        }
        for key, label in color_map.items():
            btn = self._create_color_btn(key, self.settings.theme.get(key))
            self.color_buttons[key] = btn
            ui_form.addRow(f"{label}:", btn)
        
        reset_ui = QPushButton("Reset UI")
        reset_ui.clicked.connect(self.reset_theme)
        ui_form.addRow("", reset_ui)
        theme_layout.addWidget(ui_color_group)

        # Right side: Log Colors
        log_color_group = QGroupBox("Log Levels")
        log_form = QFormLayout(log_color_group)
        self.log_color_buttons = {}
        for level, default_color in LOG_COLORS.items():
            btn = self._create_log_color_btn(level, self.settings.log_colors.get(level, default_color))
            self.log_color_buttons[level] = btn
            log_form.addRow(f"{level}:", btn)
        
        reset_logs = QPushButton("Reset Logs")
        reset_logs.clicked.connect(self.reset_log_colors)
        log_form.addRow("", reset_logs)
        theme_layout.addWidget(log_color_group)

        self.tabs.addTab(theme_tab, "Appearance")

        main_layout.addWidget(self.tabs)

        # Final Action Buttons
        button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel)
        button_box.accepted.connect(self.save_settings)
        button_box.rejected.connect(self.reject)
        main_layout.addWidget(button_box)

    def _create_color_btn(self, key, color_hex):
        btn = QPushButton()
        btn.setFixedSize(60, 24)
        btn.setStyleSheet(f"background-color: {color_hex}; border: 2px solid #555; border-radius: 4px;")
        btn.clicked.connect(lambda: self.choose_color(key, btn))
        return btn

    def _create_log_color_btn(self, level, color_hex):
        btn = QPushButton()
        btn.setFixedSize(60, 24)
        btn.setStyleSheet(f"background-color: {color_hex}; border: 2px solid #555; border-radius: 4px;")
        btn.clicked.connect(lambda: self.choose_log_color(level, btn))
        return btn

    def toggle_visibility(self, line_edit, button):
        line_edit.setEchoMode(QLineEdit.EchoMode.Normal if button.isChecked() else QLineEdit.EchoMode.Password)

    def choose_color(self, key, button):
        color = QColorDialog.getColor(QColor(self.settings.theme.get(key)), self)
        if color.isValid():
            self.settings.theme[key] = color.name()
            button.setStyleSheet(f"background-color: {color.name()}; border: 2px solid #555; border-radius: 4px;")

    def choose_log_color(self, level, button):
        color = QColorDialog.getColor(QColor(self.settings.log_colors.get(level)), self)
        if color.isValid():
            self.settings.log_colors[level] = color.name()
            button.setStyleSheet(f"background-color: {color.name()}; border: 2px solid #555; border-radius: 4px;")

    def reset_theme(self):
        self.settings.theme = DEFAULT_THEME.copy()
        for key, btn in self.color_buttons.items():
            btn.setStyleSheet(f"background-color: {DEFAULT_THEME[key]}; border: 2px solid #555; border-radius: 4px;")

    def reset_log_colors(self):
        self.settings.log_colors = LOG_COLORS.copy()
        for level, btn in self.log_color_buttons.items():
            btn.setStyleSheet(f"background-color: {LOG_COLORS[level]}; border: 2px solid #555; border-radius: 4px;")

    def save_settings(self):
        self.settings.cookie_string = self.cookie_input.text().strip()
        self.settings.rd_access_token = self.token_input.text().strip()
        self.settings.auto_extract = self.auto_extract_cb.isChecked()
        self.settings.auto_delete = self.auto_delete_cb.isChecked()
        self.settings.download_strategy = self.strategy_combo.currentData()
        self.settings.max_retries = self.retries_spin.value()
        self.settings.retry_delay = self.retry_delay_spin.value()
        self.settings.save()
        self.accept()

class AudiozGUI(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Audioz Downloader")
        self.resize(1200, 700)
        self.active_downloads = {}
        self.download_workers = {}
        self.settings = Settings()
        self.search_cache = {}
        self.current_search_term = ""

        os.makedirs(DOWNLOADS_FOLDER, exist_ok=True)

        self.apply_theme()
        self.setup_ui()

    def apply_theme(self):
        app = QApplication.instance()
        app.setStyle("Fusion")

        t = self.settings.theme

        palette = QPalette()
        palette.setColor(QPalette.ColorRole.Window, QColor(t["desktop"]))
        palette.setColor(
            QPalette.ColorRole.WindowText, QColor(t["control_fg"])
        )
        palette.setColor(QPalette.ColorRole.Base, QColor(t["surface_bg"]))
        palette.setColor(
            QPalette.ColorRole.AlternateBase, QColor(t["detail_view_bg"])
        )
        palette.setColor(
            QPalette.ColorRole.ToolTipBase, QColor(t["surface_area"])
        )
        palette.setColor(QPalette.ColorRole.ToolTipText, Qt.GlobalColor.white)
        palette.setColor(QPalette.ColorRole.Text, QColor(t["control_fg"]))
        palette.setColor(
            QPalette.ColorRole.Button, QColor(t["surface_highlight"])
        )
        palette.setColor(
            QPalette.ColorRole.ButtonText, QColor(t["control_fg"])
        )
        palette.setColor(QPalette.ColorRole.BrightText, QColor(t["accent"]))
        palette.setColor(QPalette.ColorRole.Link, QColor(t["accent"]))
        palette.setColor(QPalette.ColorRole.Highlight, QColor(t["accent"]))
        palette.setColor(
            QPalette.ColorRole.HighlightedText, QColor(t["control_on_fg"])
        )

        app.setPalette(palette)

        stylesheet = """
            QMainWindow {
                background-color: """ + t["desktop"] + """;
                color: """ + t["control_fg"] + """;
            }
            QToolBar {
                background-color: """ + t["browser_bar"] + """;
                border: none;
                spacing: 5px;
                padding: 5px;
            }
            QToolBar QPushButton {
                background-color: """ + t["surface_highlight"] + """;
                border: 1px solid """ + t["control_selection_frame"] + """;
                border-radius: 3px;
                padding: 8px 12px;
                color: """ + t["control_fg"] + """;
            }
            QToolBar QPushButton:hover {
                background-color: """ + t["main_focus"] + """;
                border: 1px solid """ + t["accent"] + """;
            }
            QToolBar QPushButton:pressed {
                background-color: """ + t["accent"] + """;
                color: """ + t["control_on_fg"] + """;
            }
            QLineEdit {
                background-color: """ + t["surface_bg"] + """;
                border: 1px solid """ + t["control_selection_frame"] + """;
                border-radius: 3px;
                padding: 8px;
                color: """ + t["control_fg"] + """;
                font-size: 12px;
                selection-background-color: """ + t["accent"] + """;
                selection-color: """ + t["control_on_fg"] + """;
            }
            QLineEdit:focus {
                border: 1px solid """ + t["accent"] + """;
            }
            QTableWidget {
                background-color: """ + t["surface_bg"] + """;
                border: none;
                gridline-color: """ + t["control_selection_frame"] + """;
                color: """ + t["control_fg"] + """;
                font-size: 11px;
            }
            QTableWidget::item {
                padding: 4px;
                border-bottom: 1px solid """ + t["control_selection_frame"] + """;
            }
            QTableWidget::item:selected {
                background-color: """ + t["surface_highlight"] + """;
                color: """ + t["control_fg"] + """;
            }
            QHeaderView::section {
                background-color: """ + t["tree_column_head_bg"] + """;
                color: """ + t["control_fg"] + """;
                padding: 6px;
                border: none;
                font-weight: bold;
            }
            QProgressBar {
                border: none;
                background-color: """ + t["surface_highlight"] + """;
                border-radius: 3px;
                text-align: center;
                color: """ + t["control_fg"] + """;
            }
            QProgressBar::chunk {
                background-color: """ + t["accent"] + """;
                border-radius: 3px;
            }
            QProgressBar:disabled {
                background-color: """ + t["text_disabled"] + """;
                color: """ + t["control_disabled"] + """;
            }
            QProgressBar::chunk:disabled {
                background-color: """ + t["control_disabled"] + """;
            }
            QTextEdit {
                background-color: """ + t["surface_bg"] + """;
                border: none;
                color: """ + t["control_fg"] + """;
                font-family: 'Courier New', monospace;
                font-size: 10px;
            }
            QSplitter::handle {
                background-color: """ + t["control_selection_frame"] + """;
            }
            QLabel {
                color: """ + t["control_fg"] + """;
            }
            QGroupBox {
                color: """ + t["control_fg"] + """;
                border: 1px solid """ + t["control_selection_frame"] + """;
                border-radius: 3px;
                margin-top: 10px;
                padding-top: 10px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                subcontrol-position: top left;
                padding: 0 5px;
            }
            QCheckBox {
                color: """ + t["control_fg"] + """;
                spacing: 5px;
            }
            QCheckBox::indicator {
                width: 13px;
                height: 13px;
            }
            QCheckBox::indicator:unchecked {
                border: 1px solid """ + t["control_selection_frame"] + """;
                background-color: """ + t["surface_bg"] + """;
            }
            QCheckBox::indicator:checked {
                border: 1px solid """ + t["accent"] + """;
                background-color: """ + t["accent"] + """;
            }
            QComboBox {
                background-color: """ + t["surface_bg"] + """;
                border: 1px solid """ + t["control_selection_frame"] + """;
                border-radius: 3px;
                padding: 5px;
                color: """ + t["control_fg"] + """;
                min-width: 120px;
            }
            QComboBox::drop-down {
                border: none;
            }
            QComboBox::down-arrow {
                image: none;
                border-left: 5px solid transparent;
                border-right: 5px solid transparent;
                border-top: 5px solid """ + t["control_fg"] + """;
                width: 0px;
                height: 0px;
            }
            QComboBox QAbstractItemView {
                background-color: """ + t["surface_bg"] + """;
                border: 1px solid """ + t["control_selection_frame"] + """;
                color: """ + t["control_fg"] + """;
                selection-background-color: """ + t["accent"] + """;
                selection-color: """ + t["control_on_fg"] + """;
            }
        """

        self.setStyleSheet(stylesheet)

    def setup_ui(self):
        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        toolbar = QToolBar()
        toolbar.setIconSize(QSize(16, 16))
        toolbar.setMovable(False)
        self.addToolBar(toolbar)

        toolbar.addWidget(QLabel("Search:"))
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Search Audioz...")
        self.search_input.setMinimumWidth(300)
        self.search_input.returnPressed.connect(self.start_search)
        toolbar.addWidget(self.search_input)

        self.search_btn = QPushButton("Search")
        self.search_btn.clicked.connect(self.start_search)
        toolbar.addWidget(self.search_btn)

        self.settings_btn = QPushButton("Settings")
        self.settings_btn.clicked.connect(self.open_settings)
        toolbar.addWidget(self.settings_btn)

        self.clear_logs_btn = QPushButton("Clear Log")
        self.clear_logs_btn.clicked.connect(self.clear_logs)
        toolbar.addWidget(self.clear_logs_btn)

        content_splitter = QSplitter(Qt.Orientation.Vertical)
        main_layout.addWidget(content_splitter)

        self.downloads_table = QTableWidget()
        self.downloads_table.setColumnCount(5)
        self.downloads_table.setHorizontalHeaderLabels(
            ["Name", "Status", "Progress", "Speed", "Actions"]
        )
        self.downloads_table.setSelectionBehavior(
            QAbstractItemView.SelectionBehavior.SelectRows
        )
        self.downloads_table.setEditTriggers(
            QAbstractItemView.EditTrigger.NoEditTriggers
        )
        self.downloads_table.setAlternatingRowColors(True)
        self.downloads_table.verticalHeader().setVisible(False)
        self.downloads_table.verticalHeader().setDefaultSectionSize(40)

        header = self.downloads_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.Fixed)
        header.resizeSection(3, 100)
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.Fixed)
        header.resizeSection(4, 120)

        content_splitter.addWidget(self.downloads_table)

        self.log_area = QTextEdit()
        self.log_area.setMaximumHeight(200)
        self.log_area.setReadOnly(True)
        content_splitter.addWidget(self.log_area)

        content_splitter.setSizes([500, 200])

        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.status_label = QLabel("Ready")
        self.status_bar.addWidget(self.status_label)

    def open_settings(self):
        dialog = SettingsDialog(self.settings, self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.apply_theme()
            self.log("Settings saved and theme updated", "SUCCESS")

    def clear_logs(self):
        self.log_area.clear()
        self.downloads_table.setRowCount(0)
        self.active_downloads.clear()
        self.download_workers.clear()
        self.search_cache.clear()
        self.log("Logs cleared", "INFO")

    def log(self, message, level="INFO"):
        timestamp = time.strftime("%H:%M:%S")
        full_message = f"[{timestamp}] {message}"

        text_format = QTextCharFormat()
        text_format.setForeground(
            QColor(self.settings.log_colors.get(level, LOG_COLORS["INFO"]))
        )

        cursor = self.log_area.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)
        cursor.insertText(full_message + "\n", text_format)

        self.log_area.ensureCursorVisible()

        self.status_label.setText(message)

    def start_search(self):
        if not self.settings.cookie_string:
            QMessageBox.warning(
                self,
                "Configuration Required",
                "Please configure your cookie string in Settings first.",
            )
            self.open_settings()
            return

        term = self.search_input.text().strip()
        if not term:
            QMessageBox.warning(
                self, "Input Error", "Please enter a search term"
            )
            return

        self.current_search_term = term
        self.search_cache.clear()
        self.load_search_page(term, 1)

    def load_search_page(self, term, page):
        cache_key = f"{term}_{page}"
        if cache_key in self.search_cache:
            self.log(f"Loading page {page} from cache...", "INFO")
            results = self.search_cache[cache_key]
            self.show_search_dialog(results, page)
            return

        # self.log_area.clear()
        self.status_label.setText(f"Searching for '{term}' (Page {page})...")

        self.search_worker = SearchWorker(
            term, self.settings.cookie_string, self.settings.base_url, page
        )
        self.search_worker.log_signal.connect(self.log)
        self.search_worker.results_signal.connect(self.show_search_dialog)
        self.search_worker.no_results_signal.connect(self.handle_no_results)
        self.search_worker.start()

    def handle_no_results(self, failed_page):
        self.log(f"No results found on page {failed_page}", "WARNING")

        if failed_page > 1:
            previous_page = failed_page - 1
            cache_key = f"{self.current_search_term}_{previous_page}"
            if cache_key in self.search_cache:
                self.log(f"Returning to page {previous_page} (cached)", "INFO")
                results = self.search_cache[cache_key]
                self.show_search_dialog(results, previous_page)
            else:
                self.log(f"Loading previous page {previous_page}", "INFO")
                self.load_search_page(self.current_search_term, previous_page)
        else:
            self.show_search_dialog([], 1)

    def show_search_dialog(self, results, current_page=1):
        cache_key = f"{self.current_search_term}_{current_page}"
        self.search_cache[cache_key] = results

        self.log(
            f"Found {len(results)} results on page {current_page}", "SUCCESS"
        )

        dialog = QDialog(self)
        dialog.setWindowTitle(f"Search Results - Page {current_page}")
        dialog.resize(800, 600)

        t = self.settings.theme

        dialog_style = """
            QDialog { 
                background-color: """ + t["desktop"] + """; 
                color: """ + t["control_fg"] + """; 
            }
            QListWidget { 
                background-color: """ + t["surface_bg"] + """; 
                border: 1px solid """ + t["control_selection_frame"] + """; 
                color: """ + t["control_fg"] + """;
                font-size: 11px;
            }
            QListWidget::item { 
                padding: 10px; 
                border-bottom: 1px solid """ + t["control_selection_frame"] + """;
                margin-top: 3px;
                margin-bottom: 3px;
            }
            QListWidget::item:selected { 
                background-color: """ + t["surface_highlight"] + """;
                color: """ + t["control_fg"] + """;
            }
            QListWidget::item:hover { 
                background-color: """ + t["surface_highlight"] + """; 
            }
            QPushButton {
                background-color: """ + t["surface_highlight"] + """;
                border: 1px solid """ + t["control_selection_frame"] + """;
                border-radius: 3px;
                padding: 10px 18px;
                color: """ + t["control_fg"] + """;
                font-size: 12px;
            }
            QPushButton:hover {
                background-color: """ + t["main_focus"] + """;
                border: 1px solid """ + t["accent"] + """;
            }
            QPushButton:pressed {
                background-color: """ + t["accent"] + """;
                color: """ + t["control_on_fg"] + """;
            }
            QPushButton:disabled {
                background-color: """ + t["text_disabled"] + """;
                color: """ + t["surface_area"] + """;
                border: 1px solid """ + t["control_selection_frame"] + """;
            }
        """

        dialog.setStyleSheet(dialog_style)

        layout = QVBoxLayout(dialog)
        layout.setSpacing(15)

        results_list = QListWidget()
        results_list.setWordWrap(True)

        if results:
            for result in results:
                lines = [result["title"]]
                if result.get("author"):
                    lines.append(f"By: {result['author']}")
                if result.get("date"):
                    lines.append(result["date"])
                item_text = "\n".join(lines)
                item = QListWidgetItem(item_text)
                item.setData(Qt.ItemDataRole.UserRole, result)
                results_list.addItem(item)
        else:
            item = QListWidgetItem("No results found on this page")
            item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEnabled)
            results_list.addItem(item)

        layout.addWidget(results_list)

        pagination_layout = QHBoxLayout()
        pagination_layout.setSpacing(10)

        prev_btn = QPushButton("Previous Page")
        next_btn = QPushButton("Next Page")

        small_btn_style = """
            QPushButton {
                background-color: """ + t["surface_highlight"] + """;
                color: """ + t["control_fg"] + """;
                border: 1px solid """ + t["control_selection_frame"] + """;
                border-radius: 2px;
                padding: 2px 6px;
                font-size: 10px;
                min-height: 20px;
            }
            QPushButton:hover {
                background-color: """ + t["main_focus"] + """;
                border: 1px solid """ + t["accent"] + """;
            }
            QPushButton:pressed {
                background-color: """ + t["accent"] + """;
                color: """ + t["control_on_fg"] + """;
            }
            QPushButton:disabled {
                background-color: """ + t["text_disabled"] + """;
                color: """ + t["surface_area"] + """;
                border: 1px solid """ + t["control_selection_frame"] + """;
            }
        """

        if current_page <= 1:
            prev_btn.setEnabled(False)

        prev_btn.setStyleSheet(small_btn_style)
        next_btn.setStyleSheet(small_btn_style)

        pagination_layout.addWidget(prev_btn)
        pagination_layout.addStretch()
        pagination_layout.addWidget(next_btn)

        layout.addLayout(pagination_layout)

        button_layout = QHBoxLayout()
        button_layout.setSpacing(20)

        download_btn = QPushButton("Download Selected")
        cancel_btn = QPushButton("Close")

        download_btn.setStyleSheet(small_btn_style)
        cancel_btn.setStyleSheet(small_btn_style)

        pagination_layout.addWidget(download_btn)
        pagination_layout.addWidget(cancel_btn)

        layout.addLayout(pagination_layout)

        download_btn.clicked.connect(
            lambda: self.download_from_search(
                dialog, results_list.currentItem()
            )
        )
        cancel_btn.clicked.connect(dialog.close)

        if not results:
            download_btn.setEnabled(False)

        def load_previous_page():
            dialog.accept()
            self.load_search_page(self.current_search_term, current_page - 1)

        def load_next_page():
            dialog.accept()
            self.load_search_page(self.current_search_term, current_page + 1)

        prev_btn.clicked.connect(load_previous_page)
        next_btn.clicked.connect(load_next_page)

        button_layout.addWidget(download_btn)
        button_layout.addStretch()
        button_layout.addWidget(cancel_btn)

        layout.addLayout(button_layout)

        dialog.exec()

    def download_from_search(self, dialog, item):
        if not item:
            QMessageBox.warning(
                dialog, "No Selection", "Please select a result to download"
            )
            return

        if not self.settings.rd_access_token:
            QMessageBox.warning(
                dialog,
                "Configuration Required",
                "Please configure your Real-Debrid API token in Settings first.",
            )
            return

        result = item.data(Qt.ItemDataRole.UserRole)
        dialog.accept()
        self.start_download_with_result(result)

    def start_download_with_result(self, result):
        url = result["url"]
        title = result["title"]

        row = self.downloads_table.rowCount()
        self.downloads_table.insertRow(row)
        self.downloads_table.setRowHeight(row, 40)

        name_item = QTableWidgetItem(title)
        self.downloads_table.setItem(row, 0, name_item)

        status_item = QTableWidgetItem("Queued")
        self.downloads_table.setItem(row, 1, status_item)

        progress_widget = QWidget()
        progress_layout = QVBoxLayout(progress_widget)
        progress_layout.setContentsMargins(2, 2, 2, 2)

        progress_bar = QProgressBar()
        progress_bar.setMinimum(0)
        progress_bar.setMaximum(100)
        progress_bar.setTextVisible(True)
        progress_layout.addWidget(progress_bar)

        self.downloads_table.setCellWidget(row, 2, progress_widget)

        speed_item = QTableWidgetItem("")
        speed_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        self.downloads_table.setItem(row, 3, speed_item)

        action_widget = QWidget()
        action_layout = QHBoxLayout(action_widget)
        action_layout.setContentsMargins(4, 2, 4, 6)

        t = self.settings.theme

        cancel_btn = QPushButton("Cancel")
        cancel_style = """
            QPushButton {
                background-color: """ + t["surface_highlight"] + """;
                color: """ + t["control_fg"] + """;
                border: 1px solid """ + t["control_selection_frame"] + """;
                border-radius: 2px;
                padding: 0px;
                font-size: 10px;
                min-height: 20px;
            }
            QPushButton:hover {
                background-color: """ + t["main_focus"] + """;
                border: 1px solid """ + t["accent"] + """;
            }
            QPushButton:pressed {
                background-color: """ + t["accent"] + """;
                color: """ + t["control_on_fg"] + """;
            }
            QPushButton:disabled {
                background-color: """ + t["text_disabled"] + """;
                color: """ + t["surface_area"] + """;
                border: 1px solid """ + t["control_selection_frame"] + """;
            }
        """
        cancel_btn.setStyleSheet(cancel_style)
        action_layout.addWidget(cancel_btn)

        self.downloads_table.setCellWidget(row, 4, action_widget)

        worker_id = f"worker_{int(time.time() * 1000)}_{row}"

        download_worker = DownloadWorker(
            url,
            self.settings.cookie_string,
            self.settings.base_url,
            self.settings.rd_access_token,
            None,
            worker_id,
            self.settings.download_strategy,
            self.settings.max_retries,
            self.settings.retry_delay,
        )
        self.download_workers[worker_id] = download_worker
        self.active_downloads[worker_id] = {
            "row": row,
            "progress_bar": progress_bar,
            "status_item": status_item,
            "speed_item": speed_item,
            "start_time": time.time(),
            "last_bytes": 0,
        }

        download_worker.log_signal.connect(self.log)
        download_worker.progress_signal.connect(
            lambda f, wid, c, t: self.update_progress(wid, c, t)
        )
        download_worker.status_signal.connect(self.update_status)
        download_worker.part_progress_signal.connect(self.update_part_progress)
        download_worker.download_finished.connect(self.on_download_finished)

        cancel_btn.clicked.connect(lambda: self.cancel_download(worker_id))

        self.log(f"Starting download: {title}", "DOWNLOAD")
        download_worker.start()

    def update_status(self, worker_id, status):
        if worker_id in self.active_downloads:
            download_info = self.active_downloads[worker_id]
            # Don't override part progress display
            if not status.startswith("Downloading..."):
                download_info["status_item"].setText(status)

    def update_part_progress(self, worker_id, current_part, total_parts):
        if worker_id in self.active_downloads:
            download_info = self.active_downloads[worker_id]
            status_text = f"Downloading... {current_part}/{total_parts}"
            download_info["status_item"].setText(status_text)

    def update_progress(self, worker_id, current, total):
        if worker_id in self.active_downloads:
            download_info = self.active_downloads[worker_id]
            progress_bar = download_info["progress_bar"]

            if total > 0:
                progress = int((current / total) * 100)
                progress_bar.setValue(progress)

                current_time = time.time()
                elapsed = current_time - download_info["start_time"]
                if elapsed > 0:
                    speed = current / elapsed
                    if speed > 1024 * 1024:
                        speed_text = f"{speed / (1024 * 1024):.1f} MB/s"
                    elif speed > 1024:
                        speed_text = f"{speed / 1024:.1f} KB/s"
                    else:
                        speed_text = f"{speed:.1f} B/s"
                    download_info["speed_item"].setText(speed_text)

    def on_download_finished(self, worker_id):
        if worker_id in self.active_downloads:
            download_info = self.active_downloads[worker_id]
            download_info["status_item"].setText("Completed")
            download_info["speed_item"].setText("")
            action_widget = self.downloads_table.cellWidget(download_info["row"], 4)
            if action_widget:
                cancel_btn = action_widget.layout().itemAt(0).widget()
                cancel_btn.setEnabled(False)
                cancel_btn.setText("Done")
                download_info["progress_bar"].setEnabled(False)

            # if self.settings.auto_extract:
            #     self.auto_extract_download(worker_id)

        if worker_id in self.download_workers:
            del self.download_workers[worker_id]

    def auto_extract_download(self, worker_id):
        """Simplified auto-extraction that handles multi-part archives"""
        if worker_id not in self.active_downloads:
            return
            
        download_info = self.active_downloads[worker_id]
        row_name = self.downloads_table.item(download_info["row"], 0).text()
        
        # Look for archive files in downloads folder
        archive_files = []
        for filename in os.listdir(DOWNLOADS_FOLDER):
            if any(filename.endswith(ext) for ext in ['.zip', '.rar', '.tar', '.gz', '.7z']):
                archive_files.append(filename)
        
        if not archive_files:
            self.log("No archive files found for extraction", "INFO")
            return
        
        # Try to extract each archive file
        extracted_any = False
        for filename in archive_files:
            archive_path = os.path.join(DOWNLOADS_FOLDER, filename)
            self.log(f"Auto-extracting: {filename}", "INFO")
            
            try:
                extracted_folder = extract_archive(archive_path)
                if extracted_folder:
                    self.log(f"Successfully extracted to: {os.path.basename(extracted_folder)}", "SUCCESS")
                    extracted_any = True
                    
                    if self.settings.auto_delete:
                        # Only delete if extraction was successful
                        os.remove(archive_path)
                        self.log(f"Deleted archive: {filename}", "INFO")
                    
                    # Open the folder
                    open_folder(extracted_folder)
                else:
                    self.log(f"Failed to extract: {filename}", "ERROR")
            except Exception as e:
                self.log(f"Error extracting {filename}: {e}", "ERROR")
        
        if not extracted_any:
            self.log("No archives could be extracted", "WARNING")

    def cancel_download(self, worker_id):
        if worker_id in self.download_workers:
            worker = self.download_workers[worker_id]
            worker.stop()
            self.log(f"Cancelled download: {worker_id}", "WARNING")

        if worker_id in self.active_downloads:
            download_info = self.active_downloads[worker_id]
            download_info["status_item"].setText("Cancelled")
            download_info["speed_item"].setText("")
            download_info["progress_bar"].setEnabled(False)

            action_widget = self.downloads_table.cellWidget(
                download_info["row"], 4
            )
            if action_widget:
                cancel_btn = action_widget.layout().itemAt(0).widget()
                cancel_btn.setEnabled(False)
                cancel_btn.setText("Cancelled")

    def start_download(self):
        self.start_search()

if __name__ == "__main__":
    app = QApplication(sys.argv)
    gui = AudiozGUI()
    gui.show()
    sys.exit(app.exec())