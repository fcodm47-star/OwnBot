#!/usr/bin/env python3
"""
CODM Bot Remote Manager v3.0 - Railway Compatible (FULLY WORKING)
Control your checker bot directly from Telegram!
"""

import os
import sys
import subprocess
import time
import re
import signal
import psutil
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

# ==================== CREATE DIRECTORIES ====================
for dir_name in ['combo', 'combo/hits', 'combo/clean', 'combo/processed', 
                  'proxy', 'proxy/working', 'proxy/bad', 'proxy/all', 'data']:
    Path(dir_name).mkdir(parents=True, exist_ok=True)

# ==================== TELEGRAM IMPORTS ====================
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes

# ==================== CONFIGURATION ====================
MANAGER_BOT_TOKEN = os.environ.get("MANAGER_BOT_TOKEN", "8382449923:AAEQqhF-gmdhzaFFXMCzkqQHjmwbKmAhZXE")
CHECKER_BOT_SCRIPT = "Final2.py"  # Your checker bot script name
PID_FILE = "checker_bot.pid"
LOG_FILE = "checker_bot.log"

# Admin IDs
ADMIN_IDS = [int(x) for x in os.environ.get("ADMIN_IDS", "8252162481").split(",")]

def sanitize_html(text: str) -> str:
    """Remove HTML/XML tags that break Telegram's parser"""
    # Remove XML/HTML tags
    text = re.sub(r'<[^>]+>', '', text)
    # Escape remaining special characters
    text = text.replace('&', '&amp;')
    text = text.replace('<', '&lt;')
    text = text.replace('>', '&gt;')
    return text

# ==================== BOT MANAGER CLASS ====================
class CheckerBotManager:
    def __init__(self):
        self.process = None
        self.pid = None
        self.checker_script = CHECKER_BOT_SCRIPT
        
    def save_pid(self, pid: int):
        with open(PID_FILE, 'w') as f:
            f.write(str(pid))
        self.pid = pid
    
    def load_pid(self) -> Optional[int]:
        if os.path.exists(PID_FILE):
            with open(PID_FILE, 'r') as f:
                try:
                    return int(f.read().strip())
                except:
                    return None
        return None
    
    def clear_pid(self):
        if os.path.exists(PID_FILE):
            os.remove(PID_FILE)
        self.pid = None
    
    def is_running(self) -> bool:
        pid = self.load_pid()
        if pid:
            try:
                proc = psutil.Process(pid)
                return proc.is_running() and proc.status() != psutil.STATUS_ZOMBIE
            except:
                pass
        return False
    
    def start_bot(self) -> tuple:
        if self.is_running():
            return False, "❌ Bot is already running!"
        
        try:
            if not os.path.exists(self.checker_script):
                return False, f"❌ {self.checker_script} not found!"
            
            # Open log file
            log_file = open(LOG_FILE, 'a')
            log_file.write(f"\n{'='*60}\n")
            log_file.write(f"Bot started at {datetime.now()}\n")
            log_file.write(f"{'='*60}\n\n")
            log_file.flush()
            
            # Set environment variables for the checker bot
            env = os.environ.copy()
            env['THREADS'] = '4'  # Force 4 threads for Railway
            env['PYTHONUNBUFFERED'] = '1'  # Ensure real-time logging
            
            # Start the checker bot process
            self.process = subprocess.Popen(
                [sys.executable, "-u", self.checker_script],
                stdout=log_file,
                stderr=subprocess.STDOUT,
                stdin=subprocess.DEVNULL,
                start_new_session=True,
                env=env,
                cwd=os.getcwd()
            )
            
            time.sleep(3)
            
            # Check if process started successfully
            if self.process.poll() is None:
                self.save_pid(self.process.pid)
                return True, f"✅ Bot started!\n📋 PID: {self.process.pid}\n🧵 Threads: 4\n📁 Log: {LOG_FILE}"
            else:
                # Read error from log
                error_msg = ""
                if os.path.exists(LOG_FILE):
                    with open(LOG_FILE, 'r') as f:
                        lines = f.readlines()
                        if lines:
                            error_msg = lines[-1][:200]
                return False, f"❌ Bot failed to start. Exit code: {self.process.returncode}\n{error_msg}"
                
        except Exception as e:
            return False, f"❌ Error: {str(e)}"
    
    def stop_bot(self) -> tuple:
        if not self.is_running():
            return False, "❌ Bot is not running"
        
        pid = self.load_pid()
        if pid:
            try:
                proc = psutil.Process(pid)
                # Try graceful termination first
                proc.terminate()
                try:
                    proc.wait(timeout=10)
                except psutil.TimeoutExpired:
                    proc.kill()
                    proc.wait(timeout=5)
                self.clear_pid()
                return True, "✅ Bot stopped successfully"
            except Exception as e:
                return False, f"❌ Error: {str(e)}"
        
        self.clear_pid()
        return False, "❌ Bot process not found"
    
    def restart_bot(self) -> tuple:
        self.stop_bot()
        time.sleep(3)
        return self.start_bot()
    
    def get_status(self) -> Dict:
        if not self.is_running():
            return {'running': False, 'status': 'stopped', 'pid': None, 'uptime': None}
        
        pid = self.load_pid()
        try:
            proc = psutil.Process(pid)
            create_time = datetime.fromtimestamp(proc.create_time())
            uptime = str(datetime.now() - create_time).split('.')[0]
            
            return {
                'running': True,
                'status': 'running',
                'pid': pid,
                'uptime': uptime,
                'cpu_percent': proc.cpu_percent(interval=0.5),
                'memory_mb': proc.memory_info().rss / 1024 / 1024,
                'threads': proc.num_threads(),
                'memory_percent': proc.memory_percent()
            }
        except:
            return {'running': False, 'status': 'unknown', 'pid': None}
    
    def tail_log(self, lines: int = 30) -> List[str]:
        if not os.path.exists(LOG_FILE):
            return ["No log file found"]
        
        try:
            with open(LOG_FILE, 'r', encoding='utf-8', errors='ignore') as f:
                all_lines = f.readlines()
                # Get last N lines and sanitize
                sanitized = [sanitize_html(line.strip()) for line in all_lines[-lines:]]
                return sanitized
        except Exception as e:
            return [f"Error reading log: {str(e)}"]
    
    def clear_log(self) -> tuple:
        try:
            with open(LOG_FILE, 'w', encoding='utf-8') as f:
                f.write(f"Log cleared at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            return True, "✅ Log cleared"
        except Exception as e:
            return False, f"❌ Failed to clear log: {str(e)}"

# ==================== PROXY HELPER FUNCTIONS ====================
def count_proxies() -> Dict:
    """Count proxies in different directories"""
    stats = {'working': 0, 'total': 0, 'bad': 0}
    
    working_file = Path("proxy/working/working.txt")
    if working_file.exists():
        with open(working_file, 'r') as f:
            stats['working'] = len([l for l in f if l.strip() and not l.startswith('#')])
    
    proxy_file = Path("proxy/proxy.txt")
    if proxy_file.exists():
        with open(proxy_file, 'r') as f:
            stats['total'] = len([l for l in f if l.strip() and not l.startswith('#')])
    
    bad_dir = Path("proxy/bad")
    if bad_dir.exists():
        stats['bad'] = len(list(bad_dir.glob("*.txt")))
    
    return stats

def list_combo_files() -> List[Path]:
    """List all combo files"""
    files = []
    hits_dir = Path("combo/hits")
    clean_dir = Path("combo/clean")
    processed_dir = Path("combo/processed")
    
    if hits_dir.exists():
        files.extend(list(hits_dir.glob("*.txt")))
    if clean_dir.exists():
        files.extend(list(clean_dir.glob("*.txt")))
    if processed_dir.exists():
        files.extend(list(processed_dir.glob("*.txt")))
    
    files.sort(key=lambda x: x.stat().st_mtime, reverse=True)
    return files[:20]

def run_proxy_test() -> str:
    """Run proxy test and return results"""
    try:
        result = subprocess.run(
            [sys.executable, "-c", """
import requests
from concurrent.futures import ThreadPoolExecutor, as_completed
import time

def test_proxy(proxy):
    try:
        start = time.time()
        proxies = {"http": proxy, "https": proxy}
        r = requests.get("http://httpbin.org/ip", proxies=proxies, timeout=5)
        if r.status_code == 200:
            return proxy, time.time() - start
    except:
        pass
    return None, None

proxies = []
with open('proxy/proxy.txt', 'r') as f:
    for line in f:
        line = line.strip()
        if line and not line.startswith('#'):
            proxies.append(line)

working = []
with ThreadPoolExecutor(max_workers=20) as executor:
    futures = {executor.submit(test_proxy, p): p for p in proxies[:100]}
    for future in as_completed(futures):
        proxy, resp_time = future.result()
        if proxy:
            working.append(proxy)

with open('proxy/working/working.txt', 'w') as f:
    f.write(f"# Working proxies: {len(working)}\\n")
    for p in working:
        f.write(f"{p}\\n")

print(len(working))
"""],
            capture_output=True,
            text=True,
            timeout=60
        )
        count = result.stdout.strip()
        if count.isdigit():
            return f"✅ Test complete! Working proxies: {count}"
        else:
            return f"⚠️ Test completed but unable to parse results"
    except subprocess.TimeoutExpired:
        return "❌ Proxy test timed out"
    except Exception as e:
        return f"❌ Error testing proxies: {str(e)}"

# ==================== TELEGRAM UI ====================
def create_main_keyboard() -> InlineKeyboardMarkup:
    """Create main menu keyboard"""
    keyboard = [
        [InlineKeyboardButton("🚀 START BOT", callback_data="start_bot"),
         InlineKeyboardButton("🛑 STOP BOT", callback_data="stop_bot")],
        [InlineKeyboardButton("🔄 RESTART BOT", callback_data="restart_bot"),
         InlineKeyboardButton("📊 STATUS", callback_data="status")],
        [InlineKeyboardButton("📜 VIEW LOGS", callback_data="view_logs"),
         InlineKeyboardButton("🗑️ CLEAR LOGS", callback_data="clear_logs")],
        [InlineKeyboardButton("📈 PERFORMANCE", callback_data="performance"),
         InlineKeyboardButton("📤 UPLOAD COMBO", callback_data="upload_combo")],
        [InlineKeyboardButton("📥 DOWNLOAD FILES", callback_data="download_files"),
         InlineKeyboardButton("🔄 UPDATE PROXIES", callback_data="update_proxies")],
        [InlineKeyboardButton("🌐 PROXY STATUS", callback_data="proxy_status"),
         InlineKeyboardButton("💾 CHECK MEMORY", callback_data="check_memory")],
        [InlineKeyboardButton("🌐 AUTO FETCH PROXIES", callback_data="fetch_proxies"),
         InlineKeyboardButton("✅ TEST PROXIES", callback_data="test_proxies")],
        [InlineKeyboardButton("⚙️ SYSTEM INFO", callback_data="system_info")],
    ]
    return InlineKeyboardMarkup(keyboard)

def create_back_button() -> InlineKeyboardMarkup:
    """Create back button keyboard"""
    keyboard = [[InlineKeyboardButton("⬅️ BACK TO MENU", callback_data="back_to_main")]]
    return InlineKeyboardMarkup(keyboard)

# ==================== COMMAND HANDLERS ====================
def is_admin(user_id: int) -> bool:
    return user_id in ADMIN_IDS

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    
    if not is_admin(user_id):
        await update.message.reply_text("❌ Unauthorized access! You are not an admin.")
        return
    
    status_text = "🟢 ONLINE" if manager.is_running() else "🔴 OFFLINE"
    proxy_stats = count_proxies()
    
    welcome_text = f"""
╔════════════════════════════════════════╗
║   🤖 CODM BOT REMOTE MANAGER v3.0     ║
╠════════════════════════════════════════╣
║  📊 Bot Status: {status_text}     
║  🌐 Platform: Railway.app
║  🧵 Threads: 4 (Optimized)
║  🌍 Proxies: {proxy_stats['working']} working / {proxy_stats['total']} total
╠════════════════════════════════════════╣
║  Use buttons below to control the bot  ║
╚════════════════════════════════════════╝
"""
    await update.message.reply_text(welcome_text, parse_mode='HTML', reply_markup=create_main_keyboard())

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = update.effective_user.id
    
    if not is_admin(user_id):
        await query.answer("Unauthorized!", show_alert=True)
        return
    
    await query.answer()
    data = query.data
    
    if data == "start_bot":
        success, msg = manager.start_bot()
        await query.edit_message_text(msg, reply_markup=create_main_keyboard())
        
    elif data == "stop_bot":
        success, msg = manager.stop_bot()
        await query.edit_message_text(msg, reply_markup=create_main_keyboard())
        
    elif data == "restart_bot":
        await query.edit_message_text("🔄 Restarting bot... Please wait...")
        success, msg = manager.restart_bot()
        await query.edit_message_text(msg, reply_markup=create_main_keyboard())
        
    elif data == "status":
        status = manager.get_status()
        if status['running']:
            text = f"""
📊 <b>BOT STATUS</b>
━━━━━━━━━━━━━━━━━━
✅ Status: <b>RUNNING</b>
🆔 PID: <code>{status['pid']}</code>
⏱️ Uptime: <b>{status['uptime']}</b>
💻 CPU: {status['cpu_percent']:.1f}%
🧠 Memory: {status['memory_mb']:.0f} MB ({status['memory_percent']:.1f}%)
🧵 Threads: {status['threads']}
📁 Log: {LOG_FILE}
"""
        else:
            text = """
📊 <b>BOT STATUS</b>
━━━━━━━━━━━━━━━━
🔴 Status: <b>STOPPED</b>

Start the bot using the button below.
"""
        await query.edit_message_text(text, parse_mode='HTML', reply_markup=create_main_keyboard())
        
    elif data == "view_logs":
        await query.edit_message_text("📜 Fetching logs...")
        logs = manager.tail_log(30)
        
        if not logs or logs == ["No log file found"]:
            await query.edit_message_text("📜 No logs found. Start the bot first.", reply_markup=create_main_keyboard())
            return
        
        log_text = "📜 <b>LAST 30 LOG LINES</b>\n━━━━━━━━━━━━━━━━\n<code>"
        for line in logs:
            # Truncate long lines
            clean_line = line[:150] if len(line) > 150 else line
            log_text += clean_line + "\n"
        log_text += "</code>"
        
        # Check if message is too long
        if len(log_text) > 4000:
            # Send as file instead
            with open("temp_log.txt", "w", encoding='utf-8') as f:
                for line in logs:
                    f.write(line + "\n")
            await query.message.reply_document(
                document=open("temp_log.txt", "rb"), 
                filename="bot_log.txt",
                caption="📜 Log file (too large for inline display)"
            )
            os.remove("temp_log.txt")
            await query.edit_message_text("📜 Log file sent!", reply_markup=create_main_keyboard())
        else:
            await query.edit_message_text(log_text, parse_mode='HTML', reply_markup=create_main_keyboard())
            
    elif data == "clear_logs":
        success, msg = manager.clear_log()
        await query.edit_message_text(msg, reply_markup=create_main_keyboard())
        
    elif data == "check_memory":
        status = manager.get_status()
        system_mem = psutil.virtual_memory()
        disk_usage = psutil.disk_usage('/')
        
        text = f"""
💾 <b>MEMORY STATUS</b>
━━━━━━━━━━━━━━━━
<b>System Memory:</b>
• Total: {system_mem.total / 1024 / 1024 / 1024:.1f} GB
• Used: {system_mem.used / 1024 / 1024:.0f} MB
• Available: {system_mem.available / 1024 / 1024:.0f} MB
• Usage: {system_mem.percent:.1f}%

<b>Disk Usage:</b>
• Total: {disk_usage.total / 1024 / 1024 / 1024:.1f} GB
• Used: {disk_usage.used / 1024 / 1024 / 1024:.1f} GB
• Free: {disk_usage.free / 1024 / 1024 / 1024:.1f} GB
• Usage: {disk_usage.percent:.1f}%

<b>Bot Memory:</b>
{'' if not status['running'] else f'• RAM: {status["memory_mb"]:.0f} MB\n• CPU: {status["cpu_percent"]:.1f}%'}
"""
        await query.edit_message_text(text, parse_mode='HTML', reply_markup=create_main_keyboard())
        
    elif data == "performance":
        status = manager.get_status()
        system_cpu = psutil.cpu_percent(interval=0.5)
        system_mem = psutil.virtual_memory()
        proxy_stats = count_proxies()
        
        text = f"""
📈 <b>PERFORMANCE METRICS</b>
━━━━━━━━━━━━━━━━
<b>Checker Bot:</b>
{'🟢 Running' if status['running'] else '🔴 Stopped'}

<b>System Resources:</b>
💻 CPU: {system_cpu:.1f}%
🧠 RAM: {system_mem.percent:.1f}%

<b>Proxy Status:</b>
🌍 Working: {proxy_stats['working']}
📁 Total: {proxy_stats['total']}

<b>Optimization for Railway:</b>
• Threads: 4 (optimized for 512MB RAM)
• Using working proxies only
• Auto proxy rotation
• Memory limit: 420MB
"""
        await query.edit_message_text(text, parse_mode='HTML', reply_markup=create_main_keyboard())
        
    elif data == "upload_combo":
        context.user_data['awaiting_combo'] = True
        await query.edit_message_text(
            "📤 <b>UPLOAD COMBO FILE</b>\n\n"
            "Send a .txt file with <code>username:password</code> format\n\n"
            "<b>Example:</b>\n"
            "<code>user1:pass1</code>\n"
            "<code>user2:pass2</code>\n\n"
            "The file will be saved to the combo directory.",
            parse_mode='HTML',
            reply_markup=create_back_button()
        )
        
    elif data == "download_files":
        files = list_combo_files()
        
        if not files:
            await query.edit_message_text("📭 No hit/clean files found!", reply_markup=create_main_keyboard())
            return
        
        keyboard = []
        for f in files[:15]:  # Limit to 15 files
            size_kb = f.stat().st_size / 1024
            keyboard.append([InlineKeyboardButton(
                f"📄 {f.name} ({size_kb:.1f} KB)", 
                callback_data=f"download_{f.name}"
            )])
        keyboard.append([InlineKeyboardButton("⬅️ BACK TO MENU", callback_data="back_to_main")])
        
        await query.edit_message_text(
            "📥 <b>SELECT FILE TO DOWNLOAD</b>\n\n"
            f"Total files: {len(files)}\n"
            "Click on a file to download it.",
            parse_mode='HTML',
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        
    elif data.startswith("download_"):
        filename = data.replace("download_", "")
        file_path = None
        
        # Search in all combo directories
        for directory in ["combo/hits", "combo/clean", "combo/processed", "combo"]:
            potential = Path(directory) / filename
            if potential.exists():
                file_path = potential
                break
        
        if file_path and file_path.exists():
            try:
                with open(file_path, 'rb') as f:
                    await query.message.reply_document(
                        document=f, 
                        filename=filename,
                        caption=f"📄 {filename}\n📅 Modified: {datetime.fromtimestamp(file_path.stat().st_mtime).strftime('%Y-%m-%d %H:%M:%S')}"
                    )
                await query.answer("✅ File sent!")
            except Exception as e:
                await query.answer(f"❌ Error: {str(e)[:50]}", show_alert=True)
        else:
            await query.answer("❌ File not found!", show_alert=True)
            
    elif data == "update_proxies":
        context.user_data['awaiting_proxy'] = True
        await query.edit_message_text(
            "🌐 <b>UPDATE PROXIES</b>\n\n"
            "Send a .txt file with proxies.\n\n"
            "<b>Supported formats:</b>\n"
            "• <code>host:port</code>\n"
            "• <code>host:port:user:pass</code>\n"
            "• <code>http://host:port</code>\n\n"
            "<b>Example:</b>\n"
            "<code>192.168.1.1:8080</code>\n"
            "<code>proxy.example.com:3128:user:pass</code>",
            parse_mode='HTML',
            reply_markup=create_back_button()
        )
        
    elif data == "fetch_proxies":
        await query.edit_message_text("🌐 <b>Auto-fetching proxies...</b>\n\nThis may take 30-60 seconds...", parse_mode='HTML')
        
        try:
            result = subprocess.run(
                [sys.executable, "-c", """
import asyncio
import aiohttp

async def fetch():
    sources = [
        'https://raw.githubusercontent.com/TheSpeedX/PROXY-List/master/http.txt',
        'https://raw.githubusercontent.com/ShiftyTR/Proxy-List/master/http.txt',
        'https://raw.githubusercontent.com/monosans/proxy-list/main/proxies/http.txt',
        'https://api.proxyscrape.com/v2/?request=displayproxies&protocol=http',
    ]
    proxies = set()
    async with aiohttp.ClientSession() as session:
        for url in sources:
            try:
                async with session.get(url, timeout=10) as resp:
                    text = await resp.text()
                    for line in text.splitlines():
                        line = line.strip()
                        if line and ':' in line and not line.startswith('#'):
                            proxies.add(line)
            except:
                pass
    return proxies

proxies = asyncio.run(fetch())
with open('proxy/proxy.txt', 'w') as f:
    f.write(f'# Auto-fetched: {len(proxies)} proxies\\n')
    f.write(f'# Date: {__import__("datetime").datetime.now()}\\n\\n')
    for p in sorted(proxies):
        f.write(f'{p}\\n')
print(len(proxies))
"""],
                capture_output=True,
                text=True,
                timeout=60
            )
            count = result.stdout.strip()
            if count and count.isdigit():
                await query.edit_message_text(
                    f"✅ <b>Auto-fetched {count} proxies!</b>\n\n"
                    f"📁 Saved to: <code>proxy/proxy.txt</code>\n\n"
                    f"Now use 'Test Proxies' to validate them.",
                    parse_mode='HTML',
                    reply_markup=create_main_keyboard()
                )
            else:
                await query.edit_message_text(
                    f"⚠️ Got {count if count else '0'} proxies.\n\nTry again later or upload manually.",
                    parse_mode='HTML',
                    reply_markup=create_main_keyboard()
                )
        except subprocess.TimeoutExpired:
            await query.edit_message_text("❌ Proxy fetch timed out. Try again.", reply_markup=create_main_keyboard())
        except Exception as e:
            await query.edit_message_text(f"❌ Error: {str(e)[:100]}", reply_markup=create_main_keyboard())
        
    elif data == "test_proxies":
        await query.edit_message_text("🔍 <b>Testing proxies...</b>\n\nThis may take 1-2 minutes...", parse_mode='HTML')
        
        result = run_proxy_test()
        
        await query.edit_message_text(
            f"{result}\n\n"
            f"💡 Working proxies saved to <code>proxy/working/working.txt</code>\n\n"
            f"The checker bot will now use only working proxies.",
            parse_mode='HTML',
            reply_markup=create_main_keyboard()
        )
        
    elif data == "proxy_status":
        stats = count_proxies()
        
        # Get working proxies list preview
        working_preview = ""
        working_file = Path("proxy/working/working.txt")
        if working_file.exists():
            with open(working_file, 'r') as f:
                proxies = [l.strip() for l in f if l.strip() and not l.startswith('#')]
                if proxies:
                    working_preview = "\n<b>Sample working proxies:</b>\n"
                    for p in proxies[:5]:
                        working_preview += f"• <code>{p[:50]}</code>\n"
        
        text = f"""
🌐 <b>PROXY STATUS</b>
━━━━━━━━━━━━━━━━
📊 <b>Statistics:</b>
• Working proxies: <b>{stats['working']}</b> ✅
• Total proxies: {stats['total']}
• Bad proxy files: {stats['bad']}

💡 <b>How it works:</b>
• Checker uses ONLY working proxies
• Proxies rotate automatically
• Bad proxies are removed
{working_preview}
"""
        await query.edit_message_text(text, parse_mode='HTML', reply_markup=create_main_keyboard())
        
    elif data == "system_info":
        status = manager.get_status()
        proxy_stats = count_proxies()
        
        # Get log file size safely
        log_size = "N/A"
        if os.path.exists(LOG_FILE):
            log_size = f"{os.path.getsize(LOG_FILE) / 1024:.1f} KB"
        
        # Get process info
        process_info = ""
        if status['running']:
            try:
                proc = psutil.Process(status['pid'])
                children = proc.children(recursive=True)
                process_info = f"\n• Child processes: {len(children)}"
            except:
                pass
        
        text = f"""
⚙️ <b>SYSTEM INFORMATION</b>
━━━━━━━━━━━━━━━━
<b>Bot Manager:</b>
• Version: 3.0
• Platform: Railway
• Python: {sys.version.split()[0]}

<b>Checker Bot:</b>
• Status: {'🟢 Running' if status['running'] else '🔴 Stopped'}
• PID: {status['pid'] if status['pid'] else 'N/A'}
• Uptime: {status['uptime'] if status['uptime'] else 'N/A'}{process_info}

<b>Proxy System:</b>
• Working proxies: {proxy_stats['working']}
• Total proxies: {proxy_stats['total']}
• Auto-rotation: Enabled

<b>Directories:</b>
• combo/: {len(list(Path('combo').glob('*.txt')))} files
• hits/: {len(list(Path('combo/hits').glob('*.txt')))} files
• clean/: {len(list(Path('combo/clean').glob('*.txt')))} files
• logs: {LOG_FILE} ({log_size})
"""
        await query.edit_message_text(text, parse_mode='HTML', reply_markup=create_main_keyboard())
        
    elif data == "back_to_main":
        status_text = "🟢 ONLINE" if manager.is_running() else "🔴 OFFLINE"
        proxy_stats = count_proxies()
        
        welcome_text = f"""
╔════════════════════════════════════════╗
║   🤖 CODM BOT REMOTE MANAGER v3.0     ║
╠════════════════════════════════════════╣
║  📊 Bot Status: {status_text}     
║  🌐 Platform: Railway.app
║  🧵 Threads: 4 (Optimized)
║  🌍 Proxies: {proxy_stats['working']} working / {proxy_stats['total']} total
╠════════════════════════════════════════╣
║  Use buttons below to control the bot  ║
╚════════════════════════════════════════╝
"""
        await query.edit_message_text(welcome_text, parse_mode='HTML', reply_markup=create_main_keyboard())

async def handle_document(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    
    if not is_admin(user_id):
        await update.message.reply_text("❌ Unauthorized!")
        return
    
    if context.user_data.get('awaiting_combo'):
        document = update.message.document
        if not document.file_name.endswith('.txt'):
            await update.message.reply_text("❌ Please send a .txt file!")
            return
        
        status_msg = await update.message.reply_text("📥 Downloading combo file...")
        
        try:
            file = await document.get_file()
            file_content = await file.download_as_bytearray()
            
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"combo_{timestamp}_{document.file_name}"
            
            combo_dir = Path("combo")
            combo_dir.mkdir(parents=True, exist_ok=True)
            filepath = combo_dir / filename
            
            with open(filepath, 'wb') as f:
                f.write(file_content)
            
            # Count valid lines
            content_text = file_content.decode('utf-8', errors='ignore')
            lines = [l for l in content_text.splitlines() if l.strip() and ':' in l]
            
            await status_msg.delete()
            await update.message.reply_text(
                f"✅ <b>Combo saved!</b>\n\n"
                f"📄 Filename: {document.file_name}\n"
                f"💾 Saved as: {filename}\n"
                f"📊 Accounts: {len(lines):,}\n\n"
                f"Use the checker bot to process this file.",
                parse_mode='HTML',
                reply_markup=create_main_keyboard()
            )
            context.user_data['awaiting_combo'] = False
        except Exception as e:
            await update.message.reply_text(f"❌ Error saving file: {str(e)[:100]}")
            
    elif context.user_data.get('awaiting_proxy'):
        document = update.message.document
        if not document.file_name.endswith('.txt'):
            await update.message.reply_text("❌ Please send a .txt file!")
            return
        
        status_msg = await update.message.reply_text("📥 Processing proxy file...")
        
        try:
            file = await document.get_file()
            file_content = await file.download_as_bytearray()
            
            proxy_dir = Path("proxy")
            proxy_dir.mkdir(parents=True, exist_ok=True)
            filepath = proxy_dir / "proxy.txt"
            
            with open(filepath, 'wb') as f:
                f.write(file_content)
            
            # Count valid proxies
            content_text = file_content.decode('utf-8', errors='ignore')
            proxies = [l for l in content_text.splitlines() if l.strip() and not l.startswith('#') and ':' in l]
            
            await status_msg.delete()
            await update.message.reply_text(
                f"✅ <b>Proxies saved!</b>\n\n"
                f"📄 Filename: {document.file_name}\n"
                f"📊 Proxies: {len(proxies):,}\n\n"
                f"Now use <b>'Test Proxies'</b> button to validate them.",
                parse_mode='HTML',
                reply_markup=create_main_keyboard()
            )
            context.user_data['awaiting_proxy'] = False
        except Exception as e:
            await update.message.reply_text(f"❌ Error saving proxies: {str(e)[:100]}")

async def status_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not is_admin(user_id):
        await update.message.reply_text("❌ Unauthorized!")
        return
    
    status = manager.get_status()
    proxy_stats = count_proxies()
    
    if status['running']:
        text = f"""
✅ <b>Bot is RUNNING</b>
━━━━━━━━━━━━━━━━
🆔 PID: {status['pid']}
⏱️ Uptime: {status['uptime']}
💻 CPU: {status['cpu_percent']:.1f}%
🧠 Memory: {status['memory_mb']:.0f} MB
🌍 Proxies: {proxy_stats['working']} working

Use /start for full menu
"""
    else:
        text = f"""
❌ <b>Bot is STOPPED</b>
━━━━━━━━━━━━━━━━
🌍 Proxies: {proxy_stats['working']} working

Use /start to control the bot
"""
    await update.message.reply_text(text, parse_mode='HTML')

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not is_admin(user_id):
        await update.message.reply_text("❌ Unauthorized!")
        return
    
    text = """
📚 <b>CODM BOT MANAGER - HELP</b>
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━<b>📋 Bot Control:</b>
• Start Bot - Launches the checker bot
• Stop Bot - Stops the checker bot
• Restart Bot - Restarts the checker bot
• Status - Shows current bot status

<b>📊 Monitoring:</b>
• View Logs - Shows last 30 log lines
• Clear Logs - Clears the log file
• Performance - Shows system metrics
• Check Memory - Detailed memory stats

<b>📁 File Management:</b>
• Upload Combo - Upload username:password file
• Download Files - Download hit/clean files
• Update Proxies - Upload proxy list

<b>🌐 Proxy Management:</b>
• Auto Fetch Proxies - Get proxies from online sources
• Test Proxies - Validate all proxies
• Proxy Status - Show proxy statistics

<b>⚙️ Features:</b>
• Uses ONLY working proxies
• Auto proxy rotation
• 4 threads (optimized for Railway)
• Memory limit: 420MB

<b>📝 Notes:</b>
• The checker bot must be running to process combos
• Test proxies after uploading or fetching
• Working proxies save to proxy/working/working.txt
"""
    await update.message.reply_text(text, parse_mode='HTML', reply_markup=create_main_keyboard())

# ==================== MAIN FUNCTION ====================
def main():
    global manager
    
    if not MANAGER_BOT_TOKEN:
        print("❌ MANAGER_BOT_TOKEN not set!")
        print("Please add it to Railway environment variables.")
        return
    
    manager = CheckerBotManager()
    
    print("=" * 60)
    print("🤖 CODM BOT MANAGER v3.0")
    print("=" * 60)
    print(f"Platform: Railway")
    print(f"Admin IDs: {ADMIN_IDS}")
    print(f"Bot Token: {'✅ Set' if MANAGER_BOT_TOKEN else '❌ Missing'}")
    print(f"Checker Script: {CHECKER_BOT_SCRIPT}")
    print(f"Log File: {LOG_FILE}")
    print("=" * 60)
    
    # Create application
    app = Application.builder().token(MANAGER_BOT_TOKEN).build()
    
    # Add handlers
    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("status", status_command))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CallbackQueryHandler(button_callback))
    app.add_handler(MessageHandler(filters.Document.ALL, handle_document))
    
    print("🚀 Starting manager bot...")
    print("✅ Bot is running! Message your bot on Telegram with /start")
    print("=" * 60)
    print("\n💡 Available commands:")
    print("   /start  - Show main menu")
    print("   /status - Quick status check")
    print("   /help   - Show help menu")
    print("\n" + "=" * 60)
    
    # Run the bot
    app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    manager = None
    
    # Signal handler for graceful shutdown
    def signal_handler(signum, frame):
        print("\n⚠️ Received shutdown signal...")
        if manager and manager.is_running():
            print("🛑 Stopping checker bot...")
            manager.stop_bot()
        print("👋 Goodbye!")
        sys.exit(0)
    
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    while True:
        try:
            main()
        except Exception as e:
            print(f"❌ Manager crashed: {e}")
            import traceback
            traceback.print_exc()
            print("🔄 Restarting in 10 seconds...")
            time.sleep(10)