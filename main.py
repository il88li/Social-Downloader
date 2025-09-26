import telebot
import requests
import json
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
import random
import re

# إعدادات البوت
API_TOKEN = '8461163944:AAG692d6NA-4h0O--5GRr9gHEjKNr1P4p1k'
API_URL = 'https://sii3.top/api/do.php?url='

bot = telebot.TeleBot(API_TOKEN)

# رموز تعبيرية عشوائية
EMOJIS = ['🌳', '🌴', '🥀', '🌺', '🌻', '🌵', '🌾', '🌼', '🌷', '🌿', '☘️', '🪻', '🌱', '🍀', '🍁', '🪴', '🌲']

# تخزين مؤقت للبيانات
user_data = {}

def get_random_emoji():
    return random.choice(EMOJIS)

def is_social_media_url(url):
    """التحقق من أن الرابط من مواقع التواصل الاجتماعي المدعومة"""
    social_patterns = [
        r'(https?://)?(www\.)?(twitter\.com|x\.com|t\.co)',
        r'(https?://)?(www\.)?(instagram\.com)',
        r'(https?://)?(www\.)?(facebook\.com|fb\.watch)',
        r'(https?://)?(www\.)?(youtube\.com|youtu\.be)',
        r'(https?://)?(www\.)?(tiktok\.com)',
        r'(https?://)?(www\.)?(snapchat\.com)',
        r'(https?://)?(www\.)?(linkedin\.com)'
    ]
    
    for pattern in social_patterns:
        if re.search(pattern, url.lower()):
            return True
    return False

def get_available_qualities(url):
    """الحصول على الجودات المتاحة من API"""
    try:
        response = requests.get(API_URL + url)
        if response.status_code == 200:
            data = response.json()
            return data
        return None
    except Exception as e:
        print(f"Error fetching qualities: {e}")
        return None

@bot.message_handler(commands=['start', 'help'])
def send_welcome(message):
    emoji = get_random_emoji()
    welcome_text = f"""مرحبا {emoji}!

أرسل لي رابط من أي موقع تواصل اجتماعي وسأساعدك في تحميل المحتوى.

{emoji} المدعومة:
- Twitter/X
- Instagram 
- Facebook
- YouTube
- TikTok
- وغيرها...

{emoji} فقط أرسل الرابط واتبع التعليمات!"""
    
    bot.reply_to(message, welcome_text)

@bot.message_handler(func=lambda message: True)
def handle_url(message):
    url = message.text.strip()
    emoji = get_random_emoji()
    
    if not is_social_media_url(url):
        bot.reply_to(message, f"{emoji} هذا الرابط غير مدعوم. يرجى إرسال رابط من مواقع التواصل الاجتماعي.")
        return
    
    bot.send_chat_action(message.chat.id, 'typing')
    
    # إظهار رسالة انتظار
    wait_msg = bot.send_message(message.chat.id, f"{emoji} جاري تحليل الرابط...")
    
    qualities = get_available_qualities(url)
    
    if not qualities or 'qualities' not in qualities:
        bot.edit_message_text(f"{emoji} عذراً، لم أتمكن من تحميل المحتوى. تأكد من صحة الرابط.", 
                            message.chat.id, wait_msg.message_id)
        return
    
    # حفظ بيانات المستخدم
    user_data[message.chat.id] = {
        'url': url,
        'qualities': qualities['qualities']
    }
    
    # إنشاء keyboard للجودات
    keyboard = InlineKeyboardMarkup()
    
    for quality in qualities['qualities']:
        quality_text = f"{quality['quality']} - {quality['size']}" if 'size' in quality else quality['quality']
        keyboard.add(InlineKeyboardButton(
            text=f"{emoji} {quality_text}",
            callback_data=f"quality_{qualities['qualities'].index(quality)}"
        ))
    
    bot.edit_message_text(
        f"{emoji} اختر الجودة المناسبة:",
        message.chat.id,
        wait_msg.message_id,
        reply_markup=keyboard
    )

@bot.callback_query_handler(func=lambda call: call.data.startswith('quality_'))
def handle_quality_selection(call):
    emoji = get_random_emoji()
    user_id = call.message.chat.id
    
    if user_id not in user_data:
        bot.answer_callback_query(call.id, "انتهت الجلسة. أرسل الرابط مرة أخرى.")
        return
    
    quality_index = int(call.data.split('_')[1])
    selected_quality = user_data[user_id]['qualities'][quality_index]
    
    # حفظ الجودة المختارة
    user_data[user_id]['selected_quality'] = selected_quality
    
    # إنشاء keyboard لاختيار النوع
    keyboard = InlineKeyboardMarkup()
    keyboard.add(
        InlineKeyboardButton(text=f"{emoji} فيديو", callback_data="type_video"),
        InlineKeyboardButton(text=f"{emoji} صوت", callback_data="type_audio")
    )
    
    bot.edit_message_text(
        f"{emoji} اختر نوع التحميل:",
        user_id,
        call.message.message_id,
        reply_markup=keyboard
    )

@bot.callback_query_handler(func=lambda call: call.data.startswith('type_'))
def handle_type_selection(call):
    emoji = get_random_emoji()
    user_id = call.message.chat.id
    
    if user_id not in user_data or 'selected_quality' not in user_data[user_id]:
        bot.answer_callback_query(call.id, "انتهت الجلسة. أرسل الرابط مرة أخرى.")
        return
    
    download_type = call.data.split('_')[1]
    selected_quality = user_data[user_id]['selected_quality']
    url = user_data[user_id]['url']
    
    bot.edit_message_text(
        f"{emoji} جاري التحميل... يرجى الانتظار",
        user_id,
        call.message.message_id
    )
    
    try:
        # هنا يمكنك إضافة منطق التحميل الفعلي بناءً على النوع والجودة
        download_url = f"{API_URL}{url}&quality={selected_quality['quality']}&type={download_type}"
        
        # إرسال الملف
        if download_type == 'video':
            bot.send_video(user_id, download_url, caption=f"{emoji} تم التحميل بنجاح!")
        else:
            bot.send_audio(user_id, download_url, caption=f"{emoji} تم التحميل بنجاح!")
            
    except Exception as e:
        bot.edit_message_text(
            f"{emoji} عذراً، حدث خطأ أثناء التحميل. حاول مرة أخرى.",
            user_id,
            call.message.message_id
        )
    
    # تنظيف البيانات
    if user_id in user_data:
        del user_data[user_id]

@bot.message_handler(commands=['about'])
def about_bot(message):
    emoji = get_random_emoji()
    about_text = f"""
{emoji} بوت التحميل من مواقع التواصل الاجتماعي

{emoji} المميزات:
- دعم معظم مواقع التواصل الاجتماعي
- اختيار الجودة المناسبة
- تحميل فيديو أو صوت فقط
- واجهة سهلة الاستخدام

{emoji} المطور: @OlIiIl7
    """
    bot.reply_to(message, about_text)

# معالجة الأخطاء
@bot.message_handler(func=lambda message: True, content_types=['audio', 'video', 'photo', 'document'])
def handle_media(message):
    emoji = get_random_emoji()
    bot.reply_to(message, f"{emoji} يرجى إرسال رابط نصي فقط.")

if __name__ == '__main__':
    print("Bot is running...")
    bot.polling(none_stop=True)
