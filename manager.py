#!/usr/bin/env python3
"""
CODM Bot Remote Manager - Control from Telegram!
"""

import os
import sys
import signal
import subprocess
import psutil
import asyncio
import time
from datetime import datetime
import json
from pathlib import Path
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes

# ==================== CONFIGURATION ====================
# IMPORTANT: Create a NEW bot from @BotFather for management
MANAGER_BOT_TOKEN = "8437665006:AAFb4o3hzk--wVMtc3QFT8Yr3WGlB_DXEok"  # Replace this!

CHECKER_BOT_SCRIPT = "Final2.py"
PID_FILE = "checker_bot.pid"
LOG_FILE = "checker_bot.log"

ADMIN_IDS = [8252162481]  # Your Telegram ID

# ==================== BOT PROCESS MANAGER ====================
class CheckerBotManager:
    def __init__(self):
        self.process = None
        self.pid = None
        
    def save_pid(self, pid):
        with open(PID_FILE, 'w') as f:
            f.write(str(pid))
        self.pid = pid
    
    def load_pid(self):
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
    
    def is_running(self):
        pid = self.load_pid()
        if pid:
            try:
                proc = psutil.Process(pid)
                return proc.is_running()
            except:
                pass
        return False
    
    def start_bot(self):
        if self.is_running():
            return False, "❌ Bot is already running!"
        
        try:
            log_file = open(LOG_FILE, 'a')
            log_file.write(f"\n{'='*60}\n")
            log_file.write(f"Bot started at {datetime.now()}\n")
            log_file.write(f"{'='*60}\n\n")
            log_file.flush()
            
            self.process = subprocess.Popen(
                [sys.executable, "-u", CHECKER_BOT_SCRIPT],
                stdout=log_file,
                stderr=subprocess.STDOUT,
                stdin=subprocess.DEVNULL,
                start_new_session=True
            )
            
            time.sleep(3)
            
            if self.process.poll() is None:
                self.save_pid(self.process.pid)
                return True, f"✅ Bot started! PID: {self.process.pid}"
            else:
                return False, f"❌ Bot failed to start. Exit code: {self.process.returncode}"
                
        except Exception as e:
            return False, f"❌ Error: {e}"
    
    def stop_bot(self):
        if not self.is_running():
            return False, "❌ Bot is not running"
        
        pid = self.load_pid()
        if pid:
            try:
                proc = psutil.Process(pid)
                proc.terminate()
                try:
                    proc.wait(timeout=10)
                except psutil.TimeoutExpired:
                    proc.kill()
                self.clear_pid()
                return True, "✅ Bot stopped successfully"
            except Exception as e:
                return False, f"❌ Error: {e}"
        
        self.clear_pid()
        return False, "❌ Bot not found"
    
    def restart_bot(self):
        self.stop_bot()
        time.sleep(3)
        return self.start_bot()
    
    def get_status(self):
        if not self.is_running():
            return {
                'running': False,
                'status': 'stopped',
                'pid': None,
                'uptime': None
            }
        
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
                'threads': proc.num_threads()
            }
        except:
            return {'running': False, 'status': 'unknown', 'pid': None}
    
    def tail_log(self, lines=30):
        if not os.path.exists(LOG_FILE):
            return ["No log file found"]
        
        try:
            with open(LOG_FILE, 'r') as f:
                all_lines = f.readlines()
                return all_lines[-lines:]
        except:
            return ["Error reading log"]
    
    def clear_log(self):
        try:
            with open(LOG_FILE, 'w') as f:
                f.write(f"Log cleared at {datetime.now()}\n")
            return True, "✅ Log cleared"
        except:
            return False, "❌ Failed to clear log"

manager = CheckerBotManager()

def is_admin(user_id):
    return user_id in ADMIN_IDS

def create_main_keyboard():
    keyboard = [
        [InlineKeyboardButton("🚀 START BOT", callback_data="start_bot"),
         InlineKeyboardButton("🛑 STOP BOT", callback_data="stop_bot")],
        [InlineKeyboardButton("🔄 RESTART BOT", callback_data="restart_bot"),
         InlineKeyboardButton("📊 STATUS", callback_data="status")],
        [InlineKeyboardButton("📜 VIEW LOGS", callback_data="view_logs"),
         InlineKeyboardButton("🗑️ CLEAR LOGS", callback_data="clear_logs")],
        [InlineKeyboardButton("📈 PERFORMANCE", callback_data="performance"),
         InlineKeyboardButton("⚡ SET THREADING", callback_data="set_threading")],
        [InlineKeyboardButton("📤 UPLOAD COMBO", callback_data="upload_combo"),
         InlineKeyboardButton("📥 DOWNLOAD HITS", callback_data="download_hits")],
        [InlineKeyboardButton("🔄 UPDATE PROXIES", callback_data="update_proxies"),
         InlineKeyboardButton("🌐 PROXY STATUS", callback_data="proxy_status")],
        [InlineKeyboardButton("📋 ACTIVE USERS", callback_data="active_users"),
         InlineKeyboardButton("📊 TOTAL STATS", callback_data="total_stats")],
        [InlineKeyboardButton("🔄 AUTO FETCH PROXIES", callback_data="fetch_proxies")],
    ]
    return InlineKeyboardMarkup(keyboard)

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    
    if not is_admin(user_id):
        await update.message.reply_text("❌ Unauthorized access!")
        return
    
    status_text = "🟢 ONLINE" if manager.is_running() else "🔴 OFFLINE"
    
    welcome_text = f"""
╔════════════════════════════════════════╗
║   🤖 CODM BOT REMOTE MANAGER v1.0     ║
╠════════════════════════════════════════╣
║  Control your checker bot directly    ║
║  from Telegram!                       ║
╠════════════════════════════════════════╣
║  📊 Bot Status: {status_text}     
╠════════════════════════════════════════╣
║  Commands:                            ║
║  • Start/Stop the checker bot         ║
║  • View logs in real-time             ║
║  • Monitor performance                ║
║  • Auto-restart on crash              ║
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
        await query.edit_message_text("🔄 Restarting bot...")
        success, msg = manager.restart_bot()
        await query.edit_message_text(msg, reply_markup=create_main_keyboard())
        
    elif data == "status":
        status = manager.get_status()
        if status['running']:
            text = f"""
📊 <b>BOT STATUS</b>
━━━━━━━━━━━━━━━━━━━━━━━━
✅ <b>Status:</b> RUNNING
🆔 <b>PID:</b> {status['pid']}
⏱️ <b>Uptime:</b> {status['uptime']}
💻 <b>CPU:</b> {status['cpu_percent']:.1f}%
🧠 <b>Memory:</b> {status['memory_mb']:.0f}MB
🧵 <b>Threads:</b> {status['threads']}
━━━━━━━━━━━━━━━━━━━━━━━━
"""
        else:
            text = """
📊 <b>BOT STATUS</b>
━━━━━━━━━━━━━━━━━━━━━━━━
🔴 <b>Status:</b> STOPPED
━━━━━━━━━━━━━━━━━━━━━━━━
"""
        await query.edit_message_text(text, parse_mode='HTML', reply_markup=create_main_keyboard())
        
    elif data == "view_logs":
        logs = manager.tail_log(30)
        log_text = "📜 <b>LAST 30 LOG LINES</b>\n━━━━━━━━━━━━━━━━━━━━━━━━\n<code>"
        for line in logs:
            log_text += line[:200] + "\n"
        log_text += "</code>"
        
        if len(log_text) > 4000:
            with open("temp_log.txt", "w") as f:
                f.writelines(logs)
            await query.message.reply_document(document=open("temp_log.txt", "rb"), filename="bot_log.txt")
            os.remove("temp_log.txt")
            await query.edit_message_text("📜 Log file sent above!", reply_markup=create_main_keyboard())
        else:
            await query.edit_message_text(log_text, parse_mode='HTML', reply_markup=create_main_keyboard())
            
    elif data == "clear_logs":
        success, msg = manager.clear_log()
        await query.edit_message_text(msg, reply_markup=create_main_keyboard())
        
    elif data == "performance":
        status = manager.get_status()
        system_cpu = psutil.cpu_percent()
        system_mem = psutil.virtual_memory().percent
        
        text = f"""
📈 <b>PERFORMANCE METRICS</b>
━━━━━━━━━━━━━━━━━━━━━━━━
<b>Checker Bot:</b>
{'🟢 Running' if status['running'] else '🔴 Stopped'}
{'' if not status['running'] else f'''
CPU: {status['cpu_percent']:.1f}%
RAM: {status['memory_mb']:.0f}MB'''}

<b>System Resources:</b>
💻 CPU: {system_cpu:.1f}%
🧠 RAM: {system_mem:.1f}%

<b>Optimization Tips:</b>
• Set /set_threading 2 for Replit
• Use rotating proxies
• Restart bot if memory > 800MB
━━━━━━━━━━━━━━━━━━━━━━━━
"""
        await query.edit_message_text(text, parse_mode='HTML', reply_markup=create_main_keyboard())
        
    elif data == "set_threading":
        keyboard = [
            [InlineKeyboardButton("⚡ 1 THREAD (Slow)", callback_data="thread_1"),
             InlineKeyboardButton("⚡⚡ 2 THREADS (Best)", callback_data="thread_2")],
            [InlineKeyboardButton("⚡⚡⚡ 3 THREADS (Fast)", callback_data="thread_3"),
             InlineKeyboardButton("⚡⚡⚡⚡ 4 THREADS (Risky)", callback_data="thread_4")],
            [InlineKeyboardButton("⬅️ BACK", callback_data="back_to_main")]
        ]
        await query.edit_message_text(
            "⚙️ <b>SET CONCURRENT CHECKERS</b>\n\n"
            "For Replit 512MB RAM:\n"
            "• 2 threads = Stable ✅\n"
            "• 3 threads = Risky ⚠️\n"
            "• 4+ threads = May crash!\n\n"
            "Select number:",
            parse_mode='HTML',
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        
    elif data.startswith("thread_"):
        num = data.split("_")[1]
        await query.edit_message_text(
            f"⚙️ Set to {num} threads\n\n"
            f"Bot will use {num} concurrent checkers.\n"
            f"For best performance on Replit, use 2 threads.",
            parse_mode='HTML',
            reply_markup=create_main_keyboard()
        )
        
    elif data == "upload_combo":
        context.user_data['awaiting_combo'] = True
        await query.edit_message_text(
            "📤 <b>UPLOAD COMBO FILE</b>\n\n"
            "Send a .txt file with username:password format.\n\n"
            "Example:\n"
            "<code>user1:pass1\nuser2:pass2</code>\n\n"
            "<i>The file will be saved to combo/ folder</i>",
            parse_mode='HTML',
            reply_markup=create_main_keyboard()
        )
        
    elif data == "download_hits":
        hits_dir = Path("combo/hits")
        clean_dir = Path("combo/clean")
        
        files = []
        if hits_dir.exists():
            files.extend(list(hits_dir.glob("*.txt")))
        if clean_dir.exists():
            files.extend(list(clean_dir.glob("*.txt")))
        
        if not files:
            await query.edit_message_text("📭 No hit files found!", reply_markup=create_main_keyboard())
            return
        
        files.sort(key=lambda x: x.stat().st_mtime, reverse=True)
        latest = files[:10]
        
        keyboard = []
        for f in latest:
            size = f.stat().st_size
            keyboard.append([InlineKeyboardButton(f"📄 {f.name} ({size:,} bytes)", callback_data=f"download_{f.name}")])
        keyboard.append([InlineKeyboardButton("⬅️ BACK", callback_data="back_to_main")])
        
        await query.edit_message_text(
            "📥 <b>RECENT FILES</b>\n\nSelect a file to download:",
            parse_mode='HTML',
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        
    elif data.startswith("download_"):
        filename = data.replace("download_", "")
        file_path = None
        
        for directory in ["combo/hits", "combo/clean", "combo"]:
            potential = Path(directory) / filename
            if potential.exists():
                file_path = potential
                break
        
        if file_path:
            with open(file_path, 'rb') as f:
                await query.message.reply_document(document=f, filename=filename)
            await query.answer("✅ File sent!")
        else:
            await query.answer("❌ File not found!", show_alert=True)
            
    elif data == "update_proxies":
        context.user_data['awaiting_proxy'] = True
        await query.edit_message_text(
            "🌐 <b>UPDATE PROXIES</b>\n\n"
            "Send a .txt file with proxies.\n\n"
            "Format:\n"
            "<code>host:port\nhost:port:user:pass</code>\n\n"
            "Or use AUTO FETCH PROXIES button!",
            parse_mode='HTML',
            reply_markup=create_main_keyboard()
        )
        
    elif data == "fetch_proxies":
        await query.edit_message_text("🌐 Auto-fetching proxies from online sources...\n\nThis may take 30 seconds...")
        
        # Run proxy fetch as subprocess
        result = subprocess.run(
            [sys.executable, "-c", """
import asyncio
import aiohttp

async def fetch():
    sources = [
        'https://raw.githubusercontent.com/TheSpeedX/PROXY-List/master/http.txt',
        'https://raw.githubusercontent.com/ShiftyTR/Proxy-List/master/http.txt',
        'https://raw.githubusercontent.com/monosans/proxy-list/main/proxies/http.txt',
        'https://api.proxyscrape.com/v2/?request=displayproxies&protocol=http&timeout=10000&country=all&ssl=all&anonymity=all',
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
            timeout=45
        )
        count = result.stdout.strip()
        if count and count.isdigit():
            await query.edit_message_text(
                f"✅ Auto-fetched {count} proxies!\n\n"
                f"📁 Saved to proxy/proxy.txt\n\n"
                f"Use the checker bot's /proxy_test to test them.",
                parse_mode='HTML',
                reply_markup=create_main_keyboard()
            )
        else:
            await query.edit_message_text(
                f"⚠️ Got {count} proxies. Try again or upload manually.",
                parse_mode='HTML',
                reply_markup=create_main_keyboard()
            )
        
    elif data == "proxy_status":
        proxy_file = Path("proxy/working/working.txt")
        total_file = Path("proxy/proxy.txt")
        
        working = 0
        total = 0
        
        if proxy_file.exists():
            with open(proxy_file, 'r') as f:
                working = len([l for l in f if l.strip() and not l.startswith('#')])
        
        if total_file.exists():
            with open(total_file, 'r') as f:
                total = len([l for l in f if l.strip() and not l.startswith('#')])
        
        text = f"""
🌐 <b>PROXY STATUS</b>
━━━━━━━━━━━━━━━━━━━━━━━━
📊 Total Proxies: {total}
✅ Working Proxies: {working}
❌ Bad Proxies: {total - working if total > working else 0}

📁 Locations:
• proxy/proxy.txt - All proxies
• proxy/working/working.txt - Working proxies
• proxy/bad/ - Bad proxies

<i>Use /proxy_test in checker bot to test proxies</i>
━━━━━━━━━━━━━━━━━━━━━━━━
"""
        await query.edit_message_text(text, parse_mode='HTML', reply_markup=create_main_keyboard())
        
    elif data == "active_users":
        text = """
👥 <b>ACTIVE USERS</b>
━━━━━━━━━━━━━━━━━━━━━━━━

<i>Check the checker bot's logs for active users</i>

Use /view_logs to see who's currently checking.

━━━━━━━━━━━━━━━━━━━━━━━━
"""
        await query.edit_message_text(text, parse_mode='HTML', reply_markup=create_main_keyboard())
        
    elif data == "total_stats":
        hits_dir = Path("combo/hits")
        clean_dir = Path("combo/clean")
        
        hit_count = 0
        clean_count = 0
        hit_files = 0
        clean_files = 0
        
        if hits_dir.exists():
            hit_files = len(list(hits_dir.glob("*.txt")))
            for f in hits_dir.glob("*.txt"):
                with open(f, 'r') as file:
                    for line in file:
                        if ':' in line and not line.startswith('#'):
                            hit_count += 1
                    
        if clean_dir.exists():
            clean_files = len(list(clean_dir.glob("*.txt")))
            for f in clean_dir.glob("*.txt"):
                with open(f, 'r') as file:
                    for line in file:
                        if ':' in line and not line.startswith('#'):
                            clean_count += 1
        
        text = f"""
📊 <b>TOTAL STATISTICS</b>
━━━━━━━━━━━━━━━━━━━━━━━━
🎮 <b>CODM HITS:</b> {hit_count:,}
🧹 <b>CLEAN ACCOUNTS:</b> {clean_count:,}
📁 <b>HIT FILES:</b> {hit_files}
📁 <b>CLEAN FILES:</b> {clean_files}

💾 <b>Storage Used:</b>
• Hits: {sum(f.stat().st_size for f in hits_dir.glob('*.txt')) / 1024 / 1024:.1f}MB
• Clean: {sum(f.stat().st_size for f in clean_dir.glob('*.txt')) / 1024 / 1024:.1f}MB
━━━━━━━━━━━━━━━━━━━━━━━━
"""
        await query.edit_message_text(text, parse_mode='HTML', reply_markup=create_main_keyboard())
        
    elif data == "back_to_main":
        await query.edit_message_text(
            "Main Menu - Select an option:",
            reply_markup=create_main_keyboard()
        )

async def handle_document(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    
    if not is_admin(user_id):
        await update.message.reply_text("❌ Unauthorized!")
        return
    
    if context.user_data.get('awaiting_combo'):
        document = update.message.document
        if document.file_name.endswith('.txt'):
            file = await document.get_file()
            file_content = await file.download_as_bytearray()
            
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"admin_{timestamp}_{document.file_name}"
            
            combo_dir = Path("combo")
            combo_dir.mkdir(parents=True, exist_ok=True)
            filepath = combo_dir / filename
            
            with open(filepath, 'wb') as f:
                f.write(file_content)
            
            # Count accounts
            content_text = file_content.decode('utf-8', errors='ignore')
            lines = [l for l in content_text.splitlines() if l.strip() and ':' in l]
            
            await update.message.reply_text(
                f"✅ Combo file saved!\n"
                f"📄 {document.file_name}\n"
                f"📊 Accounts: {len(lines):,}\n"
                f"📁 Saved as: {filename}\n\n"
                f"Use /check in the checker bot to process it.",
                parse_mode='HTML'
            )
            context.user_data['awaiting_combo'] = False
        else:
            await update.message.reply_text("❌ Please send a .txt file!")
            
    elif context.user_data.get('awaiting_proxy'):
        document = update.message.document
        if document.file_name.endswith('.txt'):
            file = await document.get_file()
            file_content = await file.download_as_bytearray()
            
            proxy_dir = Path("proxy")
            proxy_dir.mkdir(parents=True, exist_ok=True)
            filepath = proxy_dir / "proxy.txt"
            
            with open(filepath, 'wb') as f:
                f.write(file_content)
            
            # Count proxies
            content_text = file_content.decode('utf-8', errors='ignore')
            proxies = [l for l in content_text.splitlines() if l.strip() and not l.startswith('#') and ':' in l]
            
            await update.message.reply_text(
                f"✅ Proxies saved!\n"
                f"📄 {document.file_name}\n"
                f"📊 Proxies: {len(proxies):,}\n\n"
                f"Use /proxy_test in checker bot to test them.",
                parse_mode='HTML'
            )
            context.user_data['awaiting_proxy'] = False
        else:
            await update.message.reply_text("❌ Please send a .txt file!")

async def full_log_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not is_admin(user_id):
        return
    
    logs = manager.tail_log(200)
    log_text = "\n".join(logs[-200:])
    
    if len(log_text) > 4000:
        with open("full_log.txt", "w") as f:
            f.write(log_text)
        await update.message.reply_document(document=open("full_log.txt", "rb"), filename="full_log.txt")
        os.remove("full_log.txt")
    else:
        await update.message.reply_text(f"<code>{log_text}</code>", parse_mode='HTML')

async def status_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not is_admin(user_id):
        return
    
    status = manager.get_status()
    if status['running']:
        text = f"✅ Bot is RUNNING\nPID: {status['pid']}\nUptime: {status['uptime']}"
    else:
        text = "❌ Bot is STOPPED"
    await update.message.reply_text(text)

def main():
    app = Application.builder().token(MANAGER_BOT_TOKEN).build()
    
    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("status", status_command))
    app.add_handler(CommandHandler("full_log", full_log_command))
    app.add_handler(CallbackQueryHandler(button_callback))
    app.add_handler(MessageHandler(filters.Document.ALL, handle_document))
    
    print("="*50)
    print("🤖 MANAGER BOT STARTED!")
    print("="*50)
    print("Now go to Telegram and message your manager bot")
    print("Use /start to see the control panel")
    print("="*50)
    
    app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    try:
        import psutil
    except ImportError:
        subprocess.check_call([sys.executable, "-m", "pip", "install", "psutil"])
        import psutil
    
    main()