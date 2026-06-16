import telebot
from telebot import types
import subprocess
import os
import psutil
import time
import threading
import logging
from datetime import datetime

# ======== الإعدادات ======== #
BOT_TOKEN = '8320084322:AAF2LShfDuk4-WBwKPsT9gsMadpy-Hgj4R0
ADMIN_ID = [1699299580]

bot = telebot.TeleBot(BOT_TOKEN)
UPLOAD_DIR = "uploaded_files"
os.makedirs(UPLOAD_DIR, exist_ok=True)

bot_scripts = {}
banned_users = set()
lock = threading.Lock()

# ======== دوال المساعدة ======== #
def is_admin(user_id):
    return user_id in ADMIN_ID

def get_status(script_path):
    for chat_id, data in bot_scripts.items():
        if data.get('path') == script_path:
            process = data.get('process')
            if process and psutil.pid_exists(process.pid):
                return "🟢 قيد التشغيل"
    return "⏹️ متوقف"

def stop_bot(script_path, chat_id, delete=False):
    try:
        script_name = os.path.basename(script_path)
        for chat_id, data in bot_scripts.items():
            if data.get('path') == script_path:
                process = data.get('process')
                if process and psutil.pid_exists(process.pid):
                    parent = psutil.Process(process.pid)
                    for child in parent.children(recursive=True):
                        child.terminate()
                    parent.terminate()
                    parent.wait()
                    data['process'] = None
                
                if delete:
                    os.remove(script_path)
                    bot.send_message(chat_id, f"🗑️ تم حذف {script_name}")
                else:
                    bot.send_message(chat_id, f"⏹️ تم إيقاف {script_name}")
                return True
        return False
    except Exception as e:
        bot.send_message(chat_id, f"❌ خطأ: {e}")
        return False

def run_script(script_path, chat_id):
    script_name = os.path.basename(script_path)
    try:
        p = subprocess.Popen([sys.executable, script_path], 
                           stdout=subprocess.PIPE, 
                           stderr=subprocess.PIPE)
        
        with lock:
            bot_scripts[chat_id] = {
                'path': script_path,
                'process': p,
                'name': script_name
            }
        
        stdout, stderr = p.communicate()
        
        if stdout:
            bot.send_message(chat_id, f"📤 مخرجات {script_name}:\n{stdout.decode()}")
        if stderr:
            bot.send_message(chat_id, f"⚠️ أخطاء {script_name}:\n{stderr.decode()}")
            
    except Exception as e:
        bot.send_message(chat_id, f"❌ فشل تشغيل {script_name}: {e}")
    finally:
        with lock:
            if chat_id in bot_scripts:
                bot_scripts[chat_id]['process'] = None

def start_file(script_path, chat_id):
    script_name = os.path.basename(script_path)
    
    with lock:
        if chat_id in bot_scripts:
            process = bot_scripts[chat_id].get('process')
            if process and psutil.pid_exists(process.pid):
                bot.send_message(chat_id, f"⚠️ {script_name} يعمل بالفعل")
                return False
    
    threading.Thread(target=run_script, args=(script_path, chat_id), daemon=True).start()
    bot.send_message(chat_id, f"▶️ تم تشغيل {script_name}")
    return True

# ======== الأوامر ======== #
@bot.message_handler(commands=['start'])
def start(message):
    if message.from_user.username in banned_users:
        bot.send_message(message.chat.id, "⛔ أنت محظور")
        return
    
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton("📤 رفع ملف", callback_data='upload'),
        types.InlineKeyboardButton("📂 الملفات", callback_data='files'),
        types.InlineKeyboardButton("📊 الحالة", callback_data='status'),
        types.InlineKeyboardButton("ℹ️ المساعدة", callback_data='help')
    )
    
    bot.send_message(
        message.chat.id,
        f"👋 مرحباً {message.from_user.first_name}!\n\n"
        "🤖 بوت تشغيل ملفات بايثون\n\n"
        "📌 الأوامر:\n"
        "/upload - رفع ملف\n"
        "/files - عرض الملفات\n"
        "/run [اسم] - تشغيل ملف\n"
        "/stop [اسم] - إيقاف ملف\n"
        "/delete [اسم] - حذف ملف\n"
        "/status - حالة البوت\n",
        reply_markup=markup
    )

@bot.message_handler(commands=['help'])
def help_command(message):
    help_text = """
📋 **الأوامر المتاحة:**

📤 /upload - رفع ملف بايثون جديد
📂 /files - عرض جميع الملفات
▶️ /run [اسم] - تشغيل ملف
⏹️ /stop [اسم] - إيقاف ملف
🗑️ /delete [اسم] - حذف ملف
📊 /status - حالة البوت
ℹ️ /help - هذه القائمة
"""
    bot.send_message(message.chat.id, help_text)

@bot.message_handler(commands=['upload'])
def upload_command(message):
    bot.send_message(message.chat.id, "📤 أرسل ملف .py الآن")
    bot.register_next_step_handler(message, handle_file)

@bot.message_handler(commands=['run'])
def run_command(message):
    try:
        name = message.text.split(' ', 1)[1].strip()
        path = os.path.join(UPLOAD_DIR, name)
        if os.path.exists(path):
            start_file(path, message.chat.id)
        else:
            bot.send_message(message.chat.id, f"❌ الملف {name} غير موجود")
    except IndexError:
        bot.send_message(message.chat.id, "📝 استخدم: /run [اسم الملف]")
    except Exception as e:
        bot.send_message(message.chat.id, f"❌ خطأ: {e}")

@bot.message_handler(commands=['stop'])
def stop_command(message):
    try:
        name = message.text.split(' ', 1)[1].strip()
        path = os.path.join(UPLOAD_DIR, name)
        if os.path.exists(path):
            stop_bot(path, message.chat.id)
        else:
            bot.send_message(message.chat.id, f"❌ الملف {name} غير موجود")
    except IndexError:
        bot.send_message(message.chat.id, "📝 استخدم: /stop [اسم الملف]")
    except Exception as e:
        bot.send_message(message.chat.id, f"❌ خطأ: {e}")

@bot.message_handler(commands=['delete'])
def delete_command(message):
    try:
        name = message.text.split(' ', 1)[1].strip()
        path = os.path.join(UPLOAD_DIR, name)
        if os.path.exists(path):
            stop_bot(path, message.chat.id, delete=True)
        else:
            bot.send_message(message.chat.id, f"❌ الملف {name} غير موجود")
    except IndexError:
        bot.send_message(message.chat.id, "📝 استخدم: /delete [اسم الملف]")
    except Exception as e:
        bot.send_message(message.chat.id, f"❌ خطأ: {e}")

@bot.message_handler(commands=['files'])
def files_command(message):
    files = [f for f in os.listdir(UPLOAD_DIR) if f.endswith('.py')]
    
    if not files:
        bot.send_message(message.chat.id, "📂 لا توجد ملفات")
        return
    
    text = "📂 **الملفات:**\n\n"
    for i, f in enumerate(files, 1):
        path = os.path.join(UPLOAD_DIR, f)
        size = os.path.getsize(path) / 1024
        status = get_status(path)
        text += f"{i}. `{f}` ({size:.1f}KB) - {status}\n"
    
    markup = types.InlineKeyboardMarkup(row_width=2)
    for f in files[:5]:
        markup.add(
            types.InlineKeyboardButton(f"▶️ {f[:10]}", callback_data=f'run_{f}'),
            types.InlineKeyboardButton(f"⏹️ {f[:10]}", callback_data=f'stop_{f}'),
            types.InlineKeyboardButton(f"🗑️ {f[:10]}", callback_data=f'del_{f}')
        )
    markup.add(types.InlineKeyboardButton("🔄 تحديث", callback_data='refresh'))
    
    bot.send_message(message.chat.id, text, reply_markup=markup, parse_mode='Markdown')

@bot.message_handler(commands=['status'])
def status_command(message):
    try:
        cpu = psutil.cpu_percent()
        mem = psutil.virtual_memory()
        files = len([f for f in os.listdir(UPLOAD_DIR) if f.endswith('.py')])
        
        running = 0
        for data in bot_scripts.values():
            if data.get('process') and psutil.pid_exists(data['process'].pid):
                running += 1
        
        text = f"""
📊 **حالة البوت**

📂 الملفات: {files}
▶️ قيد التشغيل: {running}

💻 السيرفر:
• CPU: {cpu}%
• RAM: {mem.used / (1024**3):.1f}/{mem.total / (1024**3):.1f} GB
"""
        bot.send_message(message.chat.id, text, parse_mode='Markdown')
    except Exception as e:
        bot.send_message(message.chat.id, f"❌ خطأ في جلب الحالة: {e}")

# ======== معالج الملفات ======== #
@bot.message_handler(content_types=['document'])
def handle_file(message):
    try:
        file_name = message.document.file_name
        if not file_name.endswith('.py'):
            bot.reply_to(message, "❌ فقط ملفات .py مسموحة")
            return
        
        file_info = bot.get_file(message.document.file_id)
        downloaded = bot.download_file(file_info.file_path)
        
        path = os.path.join(UPLOAD_DIR, file_name)
        with open(path, 'wb') as f:
            f.write(downloaded)
        
        bot.reply_to(message, f"✅ تم رفع {file_name} بنجاح\n"
                             f"▶️ لتشغيله: /run {file_name}")
        
        # تشغيل تلقائي (اختياري)
        start_file(path, message.chat.id)
        
    except Exception as e:
        bot.reply_to(message, f"❌ فشل الرفع: {e}")

# ======== معالج الأزرار ======== #
@bot.callback_query_handler(func=lambda call: True)
def callback(call):
    if call.data == 'upload':
        bot.send_message(call.message.chat.id, "📤 أرسل ملف .py الآن")
    elif call.data == 'files':
        files_command(call.message)
    elif call.data == 'status':
        status_command(call.message)
    elif call.data == 'help':
        help_command(call.message)
    elif call.data == 'refresh':
        files_command(call.message)
    elif call.data.startswith('run_'):
        name = call.data.replace('run_', '')
        path = os.path.join(UPLOAD_DIR, name)
        if os.path.exists(path):
            start_file(path, call.message.chat.id)
        else:
            bot.answer_callback_query(call.id, "❌ الملف غير موجود")
    elif call.data.startswith('stop_'):
        name = call.data.replace('stop_', '')
        path = os.path.join(UPLOAD_DIR, name)
        if os.path.exists(path):
            stop_bot(path, call.message.chat.id)
        else:
            bot.answer_callback_query(call.id, "❌ الملف غير موجود")
    elif call.data.startswith('del_'):
        name = call.data.replace('del_', '')
        path = os.path.join(UPLOAD_DIR, name)
        if os.path.exists(path):
            stop_bot(path, call.message.chat.id, delete=True)
            files_command(call.message)
        else:
            bot.answer_callback_query(call.id, "❌ الملف غير موجود")
    
    bot.answer_callback_query(call.id)

# ======== تشغيل البوت ======== #
if __name__ == "__main__":
    print("🤖 البوت قيد التشغيل...")
    while True:
        try:
            bot.infinity_polling()
        except Exception as e:
            print(f"❌ خطأ: {e}, إعادة المحاولة...")
            time.sleep(5)