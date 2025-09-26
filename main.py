import telebot
import requests
import json
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
import random
import re
import yt_dlp
import os
import tempfile
import threading
from urllib.parse import urlparse
import logging

# إعدادات البوت
API_TOKEN = '8461163944:AAG692d6NA-4h0O--5GRr9gHEjKNr1P4p1k'
bot = telebot.TeleBot(API_TOKEN)

# إعداد التسجيل
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# رموز تعبيرية عشوائية
EMOJIS = ['🌳', '🌴', '🥀', '🌺', '🌻', '🌵', '🌾', '🌼', '🌷', '🌿', '☘️', '🪻', '🌱', '🍀', '🍁', '🪴', '🌲']

# تخزين مؤقت للبيانات
user_data = {}

def get_random_emoji():
    return random.choice(EMOJIS)

def is_supported_url(url):
    """التحقق من أن الرابط مدعوم - يدعم جميع مواقع التواصل الاجتماعي"""
    try:
        # محاولة الحصول على معلومات الفيديو للتحقق من الدعم
        ydl_opts = {
            'quiet': True,
            'no_warnings': True,
            'extract_flat': True,
        }
        
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.extract_info(url, download=False)
            return True
    except:
        return False

def get_video_info(url):
    """الحصول على معلومات الفيديو باستخدام yt-dlp"""
    ydl_opts = {
        'quiet': True,
        'no_warnings': True,
    }
    
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            return info
    except Exception as e:
        logger.error(f"Error getting video info: {e}")
        return None

def get_available_formats(info):
    """الحصول على الصيغ المتاحة للفيديو"""
    formats = []
    
    if 'formats' in info:
        for fmt in info['formats']:
            # تخطي التنسيقات التي لا تحتوي على فيديو أو صوت
            if not fmt.get('url'):
                continue
                
            format_note = fmt.get('format_note', 'unknown')
            ext = fmt.get('ext', 'unknown')
            filesize = fmt.get('filesize') or fmt.get('filesize_approx')
            
            # تحديد نوع المحتوى
            if fmt.get('vcodec') != 'none' and fmt.get('acodec') != 'none':
                content_type = 'فيديو+صوت'
            elif fmt.get('vcodec') != 'none':
                content_type = 'فيديو فقط'
            else:
                content_type = 'صوت فقط'
            
            # حساب حجم الملف
            size_text = "غير معروف"
            if filesize:
                if filesize > 1024*1024*1024:
                    size_text = f"{filesize/(1024*1024*1024):.1f} GB"
                elif filesize > 1024*1024:
                    size_text = f"{filesize/(1024*1024):.1f} MB"
                elif filesize > 1024:
                    size_text = f"{filesize/1024:.1f} KB"
                else:
                    size_text = f"{filesize} B"
            
            format_id = fmt.get('format_id', 'unknown')
            
            formats.append({
                'format_id': format_id,
                'quality': format_note if format_note != 'unknown' else ext.upper(),
                'type': content_type,
                'size': size_text,
                'ext': ext
            })
    
    # إضافة خيار الصوت فقط إذا كان هناك فيديو
    has_video = any(fmt.get('vcodec') != 'none' for fmt in info.get('formats', []))
    has_audio = any(fmt.get('acodec') != 'none' for fmt in info.get('formats', []))
    
    if has_video and has_audio:
        formats.append({
            'format_id': 'audio_only',
            'quality': 'أفضل جودة صوت',
            'type': 'صوت فقط',
            'size': 'متغير',
            'ext': 'mp3'
        })
    
    # إضافة خيار أفضل جودة
    formats.append({
        'format_id': 'best',
        'quality': 'أفضل جودة متاحة',
        'type': 'فيديو+صوت',
        'size': 'متغير',
        'ext': 'مختلف'
    })
    
    return formats

def download_media(url, format_id, download_type='video'):
    """تحميل الوسائط بناءً على التنسيق المختار"""
    temp_dir = tempfile.gettempdir()
    
    if format_id == 'audio_only':
        ydl_opts = {
            'format': 'bestaudio/best',
            'outtmpl': os.path.join(temp_dir, '%(title)s.%(ext)s'),
            'quiet': True,
            'postprocessors': [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'mp3',
                'preferredquality': '192',
            }],
        }
    elif format_id == 'best':
        ydl_opts = {
            'format': 'best',
            'outtmpl': os.path.join(temp_dir, '%(title)s.%(ext)s'),
            'quiet': True,
        }
    else:
        ydl_opts = {
            'format': format_id,
            'outtmpl': os.path.join(temp_dir, '%(title)s.%(ext)s'),
            'quiet': True,
        }
    
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            downloaded_file = ydl.prepare_filename(info)
            
            if format_id == 'audio_only':
                downloaded_file = downloaded_file.rsplit('.', 1)[0] + '.mp3'
            
            return downloaded_file, info.get('title', 'media')
    except Exception as e:
        logger.error(f"Download error: {e}")
        return None, None

@bot.message_handler(commands=['start', 'help'])
def send_welcome(message):
    emoji = get_random_emoji()
    welcome_text = f"""مرحبا {emoji}!

أرسل لي رابط من أي موقع تواصل اجتماعي وسأساعدك في تحميل المحتوى.

{emoji} **يدعم جميع مواقع التواصل الاجتماعي:**
- 📹 YouTube, Vimeo, Dailymotion
- 📸 Instagram, Facebook, Twitter/X
- 🎵 TikTok, Snapchat, Likee
- 💬 Reddit, Twitch, Pinterest
- 🎵 SoundCloud, Spotify, Apple Music
- 📷 Imgur, Flickr, 500px
- 🎬 Netflix, Hulu, Disney+ (بعض المحتويات)
- 🌐 وأكثر من 1000 موقع آخر!

{emoji} فقط أرسل الرابط واتبع التعليمات!"""
    
    bot.reply_to(message, welcome_text)

@bot.message_handler(func=lambda message: True)
def handle_url(message):
    url = message.text.strip()
    emoji = get_random_emoji()
    
    # التحقق من أن النص هو رابط
    if not re.match(r'^https?://', url):
        bot.reply_to(message, f"{emoji} يرجى إرسال رابط صحيح يبدأ بـ http:// أو https://")
        return
    
    if not is_supported_url(url):
        bot.reply_to(message, f"{emoji} عذراً، هذا الرابط غير مدعوم أو غير متاح.")
        return
    
    bot.send_chat_action(message.chat.id, 'typing')
    
    # إظهار رسالة انتظار
    wait_msg = bot.send_message(message.chat.id, f"{emoji} جاري تحليل الرابط...")
    
    video_info = get_video_info(url)
    
    if not video_info:
        bot.edit_message_text(f"{emoji} عذراً، لم أتمكن من تحليل الرابط. قد يكون المحتوى محمياً أو غير متاح.", 
                            message.chat.id, wait_msg.message_id)
        return
    
    # الحصول على الصيغ المتاحة
    formats = get_available_formats(video_info)
    
    if not formats:
        bot.edit_message_text(f"{emoji} عذراً، لم أتمكن من العثور على صيغ متاحة للتحميل.", 
                            message.chat.id, wait_msg.message_id)
        return
    
    # حفظ بيانات المستخدم
    user_data[message.chat.id] = {
        'url': url,
        'formats': formats,
        'title': video_info.get('title', 'وسائط'),
        'duration': video_info.get('duration'),
        'uploader': video_info.get('uploader', 'مجهول')
    }
    
    # إنشاء keyboard للصيغ
    keyboard = InlineKeyboardMarkup()
    row = []
    
    for i, fmt in enumerate(formats):
        # تقصير النص إذا كان طويلاً
        quality_text = fmt['quality'][:15] + "..." if len(fmt['quality']) > 15 else fmt['quality']
        btn_text = f"{emoji} {quality_text} ({fmt['type']})"
        callback_data = f"format_{i}"
        
        row.append(InlineKeyboardButton(text=btn_text, callback_data=callback_data))
        
        if len(row) == 1:  # زر واحد في كل صف لعرض المعلومات الكاملة
            keyboard.add(*row)
            row = []
    
    if row:
        keyboard.add(*row)
    
    # إضافة زر للمساعدة
    keyboard.add(InlineKeyboardButton(text=f"{emoji} المساعدة", callback_data="help"))
    
    # معلومات الفيديو
    title = video_info.get('title', 'الوسائط')[:100] + "..." if len(video_info.get('title', '')) > 100 else video_info.get('title', 'الوسائط')
    uploader = video_info.get('uploader', 'مجهول')
    duration = video_info.get('duration')
    duration_text = f"{duration//60}:{duration%60:02d}" if duration else "غير معروف"
    
    info_text = f"""
{emoji} **{title}**

👤 **المنشئ:** {uploader}
⏱ **المدة:** {duration_text}
📊 **الصيغ المتاحة:** {len(formats)}

اختر الصيغ المناسبة:
    """
    
    bot.edit_message_text(
        info_text,
        message.chat.id,
        wait_msg.message_id,
        reply_markup=keyboard,
        parse_mode='Markdown'
    )

@bot.callback_query_handler(func=lambda call: call.data.startswith('format_'))
def handle_format_selection(call):
    emoji = get_random_emoji()
    user_id = call.message.chat.id
    
    if user_id not in user_data:
        bot.answer_callback_query(call.id, "انتهت الجلسة. أرسل الرابط مرة أخرى.")
        return
    
    format_index = int(call.data.split('_')[1])
    selected_format = user_data[user_id]['formats'][format_index]
    
    # بدء التحميل
    bot.edit_message_text(
        f"{emoji} جاري التحميل... قد تستغرق العملية عدة دقائق حسب حجم الملف",
        user_id,
        call.message.message_id
    )
    
    # التحميل في thread منفصل
    thread = threading.Thread(target=download_and_send, args=(user_id, call.message.message_id, selected_format))
    thread.start()

@bot.callback_query_handler(func=lambda call: call.data == 'help')
def handle_help(call):
    emoji = get_random_emoji()
    help_text = f"""
{emoji} **كيفية الاستخدام:**

1. أرسل رابط أي فيديو أو منشور من مواقع التواصل الاجتماعي
2. انتظر حتى يحلل البوت الرابط
3. اختر الصيغة المناسبة من القائمة
4. انتظر حتى يكتمل التحميل والإرسال

{emoji} **ملاحظات:**
- بعض المحتويات قد تكون محمية ولا يمكن تحميلها
- جودة وسرعة التحميل تعتمد على الموقع الأصلي
- قد يستغرق تحميل الملفات الكبيرة عدة دقائق
    """
    
    bot.answer_callback_query(call.id)
    bot.send_message(call.message.chat.id, help_text, parse_mode='Markdown')

def download_and_send(user_id, message_id, selected_format):
    """دالة منفصلة للتحميل والإرسال"""
    emoji = get_random_emoji()
    
    try:
        if user_id not in user_data:
            return
        
        url = user_data[user_id]['url']
        title = user_data[user_id]['title']
        
        bot.edit_message_text(
            f"{emoji} جاري تحميل {selected_format['type']}...",
            user_id,
            message_id
        )
        
        file_path, media_title = download_media(url, selected_format['format_id'])
        
        if not file_path or not os.path.exists(file_path):
            bot.edit_message_text(
                f"{emoji} عذراً، فشل التحميل. حاول مرة أخرى أو اختر صيغة أخرى.",
                user_id,
                message_id
            )
            return
        
        # التحقق من حجم الملف (تليجرام له حدود)
        file_size = os.path.getsize(file_path)
        max_size = 50 * 1024 * 1024  # 50MB حد تليجرام
        
        if file_size > max_size:
            bot.edit_message_text(
                f"{emoji} الملف كبير جداً ({file_size/(1024*1024):.1f}MB). الحد الأقصى هو 50MB.",
                user_id,
                message_id
            )
            os.remove(file_path)
            return
        
        # إرسال الملف
        bot.edit_message_text(
            f"{emoji} جاري الإرسال...",
            user_id,
            message_id
        )
        
        caption = f"{emoji} {title}\n📊 الجودة: {selected_format['quality']}\n🎬 النوع: {selected_format['type']}"
        
        with open(file_path, 'rb') as file:
            if selected_format['type'] == 'صوت فقط' or selected_format['format_id'] == 'audio_only':
                bot.send_audio(user_id, file, caption=caption, title=media_title)
            elif selected_format['type'] == 'فيديو فقط' or selected_format['type'] == 'فيديو+صوت':
                bot.send_video(user_id, file, caption=caption)
            else:
                bot.send_document(user_id, file, caption=caption)
        
        # حذف الملف المؤقت
        os.remove(file_path)
        
        bot.edit_message_text(
            f"{emoji} تم التحميل والإرسال بنجاح!",
            user_id,
            message_id
        )
        
    except Exception as e:
        logger.error(f"Error in download_and_send: {e}")
        bot.edit_message_text(
            f"{emoji} عذراً، حدث خطأ أثناء التحميل. حاول مرة أخرى.",
            user_id,
            message_id
        )
    
    # تنظيف البيانات
    if user_id in user_data:
        del user_data[user_id]

@bot.message_handler(commands=['supported'])
def supported_sites(message):
    emoji = get_random_emoji()
    sites_text = f"""
{emoji} **المواقع المدعومة (أكثر من 1000 موقع):**

🎥 **منصات الفيديو:**
- YouTube, Vimeo, Dailymotion
- Netflix, Hulu, Disney+, Amazon Prime
- Twitch, Floatplane, Nebula

📱 **التواصل الاجتماعي:**
- Instagram, Facebook, Twitter/X
- TikTok, Snapchat, Likee, Triller
- Reddit, Pinterest, LinkedIn
- Tumblr, Flickr, Imgur

🎵 **منصات الصوت:**
- SoundCloud, Spotify, Apple Music
- Deezer, Tidal, YouTube Music
- Bandcamp, Audius, Mixcloud

🌐 **المواقع الإخبارية والمدونات:**
- CNN, BBC, Reuters, Al Jazeera
- Medium, Blogger, WordPress

{emoji} **ومئات المواقع الأخرى!**
    """
    bot.reply_to(message, sites_text, parse_mode='Markdown')

@bot.message_handler(commands=['about'])
def about_bot(message):
    emoji = get_random_emoji()
    about_text = f"""
{emoji} **بوت التحميل الشامل**

✨ **المميزات:**
- يدعم جميع مواقع التواصل الاجتماعي
- تحميل الفيديو والصوت والصور
- خيارات متعددة للجودة والصيغ
- واجهة عربية سهلة الاستخدام
- دعم أكثر من 1000 موقع

🛠 **التقنية:**
- يعتمد على yt-dlp المتطور
- تحميل متعدد الجودات
- معالجة ذكية للروابط

{emoji} للإبلاغ عن مشاكل: @username
    """
    bot.reply_to(message, about_text, parse_mode='Markdown')

@bot.message_handler(commands=['status'])
def bot_status(message):
    emoji = get_random_emoji()
    status_text = f"""
{emoji} **حالة البوت:**

🟢 البوت يعمل بشكل طبيعي
👥 المستخدمين النشطين: {len(user_data)}
🔄 جاهز لتحميل الوسائط

{emoji} أرسل رابط لبدء التحميل!
    """
    bot.reply_to(message, status_text, parse_mode='Markdown')

# معالجة الأخطاء
@bot.message_handler(func=lambda message: True, content_types=['audio', 'video', 'photo', 'document'])
def handle_media(message):
    emoji = get_random_emoji()
    bot.reply_to(message, f"{emoji} يرجى إرسال رابط نصي فقط.")

# معالجة الأخطاء العامة
@bot.message_handler(func=lambda message: True)
def handle_other_messages(message):
    emoji = get_random_emoji()
    if message.text.startswith('/'):
        bot.reply_to(message, f"{emoji} الأمر غير معروف. استخدم /help للمساعدة.")
    else:
        bot.reply_to(message, f"{emoji} أرسل رابط من مواقع التواصل الاجتماعي لتحميل المحتوى.")

if __name__ == '__main__':
    print("🌍 بوت التحميل الشامل يعمل...")
    print("📹 يدعم جميع مواقع التواصل الاجتماعي")
    print("🎵 يمكنه تحميل الفيديو والصوت")
    print("⏰ جاهز لاستقبال الطلبات")
    
    try:
        bot.polling(none_stop=True)
    except Exception as e:
        logger.error(f"Bot error: {e}")
        print("إعادة تشغيل البوت...")
