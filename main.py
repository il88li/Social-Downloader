import asyncio
import logging
import sqlite3
from datetime import datetime
from telethon import TelegramClient, Button, events
from telethon.errors import FloodWaitError, UserPrivacyRestrictedError, ChannelPrivateError
from telethon.tl.functions.channels import InviteToChannelRequest, GetParticipantsRequest
from telethon.tl.types import ChannelParticipantsSearch, InputChannel
import random
import re

# إعداد التسجيل
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class AdvancedMemberTransferBot:
    def __init__(self, api_id, api_hash, bot_token, session_name='advanced_member_bot'):
        self.api_id = api_id
        self.api_hash = api_hash
        self.bot_token = bot_token
        self.session_name = session_name
        self.client = None
        self.user_sessions = {}
        self.active_transfers = {}
        
        # تهيئة قاعدة البيانات
        self.init_database()
        
    def init_database(self):
        """تهيئة قاعدة البيانات"""
        self.conn = sqlite3.connect('member_transfer.db', check_same_thread=False)
        cursor = self.conn.cursor()
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS transfers (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                source_chat TEXT,
                target_chat TEXT,
                total_members INTEGER,
                transferred INTEGER,
                failed INTEGER,
                status TEXT,
                start_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                end_time TIMESTAMP
            )
        ''')
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS user_settings (
                user_id INTEGER PRIMARY KEY,
                delay_seconds REAL DEFAULT 3.0,
                max_users INTEGER DEFAULT 30,
                auto_continue BOOLEAN DEFAULT FALSE
            )
        ''')
        
        self.conn.commit()

    async def start_bot(self):
        """بدء تشغيل البوت"""
        try:
            self.client = TelegramClient(self.session_name, self.api_id, self.api_hash)
            await self.client.start(bot_token=self.bot_token)
            
            # إضافة معالجين للأحداث
            self.client.add_event_handler(self.handle_start, events.NewMessage(pattern='/start'))
            self.client.add_event_handler(self.handle_callback, events.CallbackQuery)
            self.client.add_event_handler(self.handle_message, events.NewMessage)
            
            logger.info("✅ بدأ تشغيل البوت بنجاح")
            await self.client.run_until_disconnected()
            
        except Exception as e:
            logger.error(f"❌ خطأ في تشغيل البوت: {e}")

    async def get_main_keyboard(self):
        """لوحة المفاتيح الرئيسية"""
        return [
            [Button.inline("🔍 إعداد المجموعات", b"setup_groups")],
            [Button.inline("⚙️ إعدادات النقل", b"transfer_settings")],
            [Button.inline("🚀 بدء النقل", b"start_transfer"), Button.inline("⏹️ إيقاف", b"stop_transfer")],
            [Button.inline("📊 الإحصائيات", b"statistics")]
        ]

    async def get_group_setup_keyboard(self):
        """لوحة إعداد المجموعات"""
        return [
            [Button.inline("📥 تعيين المصدر", b"set_source"), Button.inline("📤 تعيين الهدف", b"set_target")],
            [Button.inline("✅ التحقق من الصلاحيات", b"check_permissions")],
            [Button.inline("🔙 رجوع", b"main_menu")]
        ]

    async def get_settings_keyboard(self):
        """لوحة الإعدادات"""
        return [
            [Button.inline("⏱️ وقت التأخير", b"set_delay"), Button.inline("👥 الحد الأقصى", b"set_max_users")],
            [Button.inline("💾 حفظ الإعدادات", b"save_settings")],
            [Button.inline("🔙 رجوع", b"main_menu")]
        ]

    async def handle_start(self, event):
        """معالجة أمر /start"""
        sender = await event.get_sender()
        
        welcome_text = f"""
        🤖 **مرحباً {sender.first_name}!

        بوت نقل الأعضاء المتقدم**

        **الميزات:**
        ✅ نقل أعضاء حقيقي بين المجموعات
        ✅ إدارة الصلاحيات التلقائية
        ✅ مقاومة الحظر والتقييد
        ✅ تقارير مفصلة عن العمليات

        **استخدم الأزرار للتحكم:**
        """
        
        keyboard = await self.get_main_keyboard()
        await event.reply(welcome_text, buttons=keyboard)

    async def handle_callback(self, event):
        """معالجة الضغط على الأزرار"""
        try:
            data = event.data.decode('utf-8')
            user_id = event.sender_id
            
            if data == "main_menu":
                await self.show_main_menu(event)
            elif data == "setup_groups":
                await self.show_group_setup(event)
            elif data == "transfer_settings":
                await self.show_settings_menu(event)
            elif data == "set_source":
                await self.request_source_group(event)
            elif data == "set_target":
                await self.request_target_group(event)
            elif data == "check_permissions":
                await self.check_permissions(event)
            elif data == "set_delay":
                await self.request_delay_setting(event)
            elif data == "set_max_users":
                await self.request_max_users_setting(event)
            elif data == "save_settings":
                await self.save_settings(event)
            elif data == "start_transfer":
                await self.start_member_transfer(event)
            elif data == "stop_transfer":
                await self.stop_transfer(event)
            elif data == "statistics":
                await self.show_statistics(event)
                
        except Exception as e:
            logger.error(f"خطأ في معالجة الزر: {e}")
            await event.answer("❌ حدث خطأ", alert=True)

    async def handle_message(self, event):
        """معالجة الرسائل النصية"""
        user_id = event.sender_id
        text = event.text
        
        if user_id in self.user_sessions and 'waiting_for' in self.user_sessions[user_id]:
            waiting_for = self.user_sessions[user_id]['waiting_for']
            
            if waiting_for == 'source_group':
                await self.process_source_group(event, text)
            elif waiting_for == 'target_group':
                await self.process_target_group(event, text)
            elif waiting_for == 'delay_setting':
                await self.process_delay_setting(event, text)
            elif waiting_for == 'max_users_setting':
                await self.process_max_users_setting(event, text)

    async def request_source_group(self, event):
        """طلب مجموعة المصدر"""
        user_id = event.sender_id
        self.user_sessions[user_id] = {'waiting_for': 'source_group'}
        await event.edit("📥 **أرسل معرف مجموعة المصدر:**\n\n• @username\n• رابط الدعوة\n• ID المجموعة")

    async def process_source_group(self, event, group_input):
        """معالجة مجموعة المصدر"""
        user_id = event.sender_id
        try:
            entity = await self.get_chat_entity(group_input)
            if not entity:
                await event.reply("❌ لم أستطع العثور على المجموعة")
                return
                
            self.user_sessions[user_id]['source_group'] = entity
            await event.reply(f"✅ تم تعيين مجموعة المصدر: {entity.title}")
            
        except Exception as e:
            await event.reply(f"❌ خطأ: {str(e)}")

    async def request_target_group(self, event):
        """طلب مجموعة الهدف"""
        user_id = event.sender_id
        self.user_sessions[user_id] = {'waiting_for': 'target_group'}
        await event.edit("📤 **أرسل معرف مجموعة الهدف:**\n\n• @username\n• رابط الدعوة\n• ID المجموعة")

    async def process_target_group(self, event, group_input):
        """معالجة مجموعة الهدف"""
        user_id = event.sender_id
        try:
            entity = await self.get_chat_entity(group_input)
            if not entity:
                await event.reply("❌ لم أستطع العثور على المجموعة")
                return
                
            self.user_sessions[user_id]['target_group'] = entity
            await event.reply(f"✅ تم تعيين مجموعة الهدف: {entity.title}")
            
        except Exception as e:
            await event.reply(f"❌ خطأ: {str(e)}")

    async def get_chat_entity(self, input_str):
        """الحصول على كيان المجموعة"""
        try:
            # محاولة الحصول على الكيان مباشرة
            entity = await self.client.get_entity(input_str)
            return entity
        except Exception as e:
            logger.error(f"Error getting entity: {e}")
            return None

    # الدوال الفعلية لنقل الأعضاء
    async def get_chat_members(self, chat_entity, limit=1000):
        """جلب أعضاء المجموعة - الدالة الفعلية"""
        try:
            participants = []
            async for user in self.client.iter_participants(chat_entity, aggressive=True):
                if user.bot or user.deleted:
                    continue
                participants.append(user)
                if len(participants) >= limit:
                    break
            return participants
        except ChannelPrivateError:
            raise Exception("لا أملك صلاحية الوصول لهذه المجموعة")
        except Exception as e:
            raise Exception(f"خطأ في جلب الأعضاء: {str(e)}")

    async def add_member_to_chat(self, user, target_chat):
        """إضافة عضو إلى مجموعة - الدالة الفعلية"""
        try:
            await self.client(InviteToChannelRequest(
                channel=target_chat,
                users=[user]
            ))
            return True
        except UserPrivacyRestrictedError:
            return False  # المستخدم لديه إعدادات خصوصية
        except FloodWaitError as e:
            raise e  إعادة رفع الخطأ للتعامل معه
        except Exception as e:
            logger.error(f"Error adding user {user.id}: {e}")
            return False

    async def start_member_transfer(self, event):
        """بدء عملية نقل الأعضاء الفعلية"""
        user_id = event.sender_id
        
        if user_id not in self.user_sessions:
            await event.answer("❌ قم بإعداد المجموعات أولاً", alert=True)
            return
            
        session = self.user_sessions[user_id]
        if 'source_group' not in session or 'target_group' not in session:
            await event.answer("❌ قم بتعيين المجموعات أولاً", alert=True)
            return

        try:
            # جلب الإعدادات
            settings = await self.get_user_settings(user_id)
            delay = settings.get('delay_seconds', 3.0)
            max_users = settings.get('max_users', 30)

            # جلب الأعضاء من المصدر
            await event.edit("🔍 جاري جلب الأعضاء من مجموعة المصدر...")
            members = await self.get_chat_members(session['source_group'], max_users)
            
            if not members:
                await event.edit("❌ لم أجد أعضاء لنقلهم")
                return

            # بدء النقل
            self.active_transfers[user_id] = True
            transfer_id = await self.create_transfer_record(user_id, session, len(members))
            
            success_count = 0
            failed_count = 0
            
            await event.edit(f"🚀 بدء نقل {len(members)} عضو...")
            
            for i, member in enumerate(members):
                if not self.active_transfers.get(user_id, False):
                    break
                    
                try:
                    result = await self.add_member_to_chat(member, session['target_group'])
                    if result:
                        success_count += 1
                    else:
                        failed_count += 1
                    
                    # تحديث التقدم كل 5 أعضاء
                    if (i + 1) % 5 == 0:
                        progress = f"📊 التقدم: {i+1}/{len(members)}\n✅ نجح: {success_count}\n❌ فشل: {failed_count}"
                        await event.edit(progress)
                    
                    # تأخير بين العمليات
                    if i < len(members) - 1:  # لا تأخير بعد آخر عملية
                        await asyncio.sleep(delay + random.uniform(0.5, 1.5))
                        
                except FloodWaitError as e:
                    wait_time = e.seconds
                    await event.edit(f"⏳ انتظر {wait_time} ثانية بسبب التقييد...")
                    await asyncio.sleep(wait_time)
                    continue
                except Exception as e:
                    logger.error(f"Error in transfer: {e}")
                    failed_count += 1
                    continue

            # إنهاء النقل
            await self.complete_transfer(transfer_id, success_count, failed_count)
            
            result_text = f"""
✅ **اكتمل النقل!**

📊 **النتائج:**
• الإجمالي: {len(members)}
• الناجح: {success_count}
• الفاشل: {failed_count}
• النجاح: {(success_count/len(members))*100:.1f}%
            """
            
            await event.edit(result_text)
            
        except Exception as e:
            logger.error(f"Transfer error: {e}")
            await event.edit(f"❌ خطأ في النقل: {str(e)}")

    async def create_transfer_record(self, user_id, session, total_members):
        """إنشاء سجل للنقل في قاعدة البيانات"""
        cursor = self.conn.cursor()
        cursor.execute('''
            INSERT INTO transfers 
            (user_id, source_chat, target_chat, total_members, status)
            VALUES (?, ?, ?, ?, ?)
        ''', (user_id, str(session['source_group'].id), str(session['target_group'].id), total_members, 'started'))
        self.conn.commit()
        return cursor.lastrowid

    async def complete_transfer(self, transfer_id, success_count, failed_count):
        """إكمال سجل النقل"""
        cursor = self.conn.cursor()
        cursor.execute('''
            UPDATE transfers 
            SET transferred = ?, failed = ?, status = 'completed', end_time = CURRENT_TIMESTAMP
            WHERE id = ?
        ''', (success_count, failed_count, transfer_id))
        self.conn.commit()

    async def stop_transfer(self, event):
        """إيقاف النقل"""
        user_id = event.sender_id
        self.active_transfers[user_id] = False
        await event.answer("⏹️ تم إيقاف النقل", alert=True)

    async def get_user_settings(self, user_id):
        """الحصول على إعدادات المستخدم"""
        cursor = self.conn.cursor()
        cursor.execute('SELECT delay_seconds, max_users FROM user_settings WHERE user_id = ?', (user_id,))
        result = cursor.fetchone()
        if result:
            return {'delay_seconds': result[0], 'max_users': result[1]}
        return {'delay_seconds': 3.0, 'max_users': 30}

    async def request_delay_setting(self, event):
        """طلب إعداد الوقت"""
        user_id = event.sender_id
        self.user_sessions[user_id] = {'waiting_for': 'delay_setting'}
        await event.edit("⏱️ **أدخل وقت التأخير بين كل عملية (بالثواني):**\n\nمثال: 2.5")

    async def process_delay_setting(self, event, delay_str):
        """معالجة إعداد الوقت"""
        try:
            delay = float(delay_str)
            if delay < 1:
                await event.reply("⚠️ وقت قليل قد يؤدي لحظر!")
            elif delay > 10:
                await event.reply("⏳ وقت طويل ولكن آمن")
            
            user_id = event.sender_id
            if 'settings' not in self.user_sessions[user_id]:
                self.user_sessions[user_id]['settings'] = {}
            self.user_sessions[user_id]['settings']['delay_seconds'] = delay
            await event.reply(f"✅ تم تعيين التأخير: {delay} ثانية")
            
        except ValueError:
            await event.reply("❌ أدخل رقم صحيح أو عشري")

    async def request_max_users_setting(self, event):
        """طلب إعداد الحد الأقصى"""
        user_id = event.sender_id
        self.user_sessions[user_id] = {'waiting_for': 'max_users_setting'}
        await event.edit("👥 **أدخل الحد الأقصى للأعضاء:**\n\nمثال: 50")

    async def process_max_users_setting(self, event, max_str):
        """معالجة إعداد الحد الأقصى"""
        try:
            max_users = int(max_str)
            if max_users > 100:
                await event.reply("⚠️ عدد كبير قد يكون خطيراً!")
            
            user_id = event.sender_id
            if 'settings' not in self.user_sessions[user_id]:
                self.user_sessions[user_id]['settings'] = {}
            self.user_sessions[user_id]['settings']['max_users'] = max_users
            await event.reply(f"✅ تم تعيين الحد الأقصى: {max_users} عضو")
            
        except ValueError:
            await event.reply("❌ أدخل رقم صحيح")

    async def save_settings(self, event):
        """حفظ الإعدادات"""
        user_id = event.sender_id
        if user_id in self.user_sessions and 'settings' in self.user_sessions[user_id]:
            settings = self.user_sessions[user_id]['settings']
            cursor = self.conn.cursor()
            cursor.execute('''
                INSERT OR REPLACE INTO user_settings 
                (user_id, delay_seconds, max_users) 
                VALUES (?, ?, ?)
            ''', (user_id, settings.get('delay_seconds', 3.0), settings.get('max_users', 30)))
            self.conn.commit()
            await event.answer("✅ تم حفظ الإعدادات")
        else:
            await event.answer("❌ لا توجد إعدادات لحفظها")

    async def check_permissions(self, event):
        """التحقق من الصلاحيات"""
        user_id = event.sender_id
        if user_id not in self.user_sessions:
            await event.answer("❌ قم بإعداد المجموعات أولاً", alert=True)
            return
            
        session = self.user_sessions[user_id]
        try:
            # التحقق من الصلاحيات في المجموعات
            source = session.get('source_group')
            target = session.get('target_group')
            
            if source and target:
                # محاولة جلب معلومات المجموعة للتحقق من الصلاحيات
                await event.edit("🔍 جاري التحقق من الصلاحيات...")
                
                # هذه مجرد تحقق أساسي - تحتاج لتحسين
                can_proceed = True
                message = "✅ **التحقق من الصلاحيات:**\n\n"
                
                try:
                    await self.client.get_permissions(source, await self.client.get_me())
                    message += "📥 مجموعة المصدر: ✅ متاحة\n"
                except:
                    message += "📥 مجموعة المصدر: ❌ غير متاحة\n"
                    can_proceed = False
                    
                try:
                    await self.client.get_permissions(target, await self.client.get_me())
                    message += "📤 مجموعة الهدف: ✅ متاحة\n"
                except:
                    message += "📤 مجموعة الهدف: ❌ غير متاحة\n"
                    can_proceed = False
                
                if can_proceed:
                    message += "\n🎯 **الحالة:** جاهز للنقل"
                else:
                    message += "\n⚠️ **الحالة:** تحتاج لإصلاح الصلاحيات"
                
                await event.edit(message)
                
        except Exception as e:
            await event.edit(f"❌ خطأ في التحقق: {str(e)}")

    async def show_statistics(self, event):
        """عرض الإحصائيات"""
        user_id = event.sender_id
        cursor = self.conn.cursor()
        cursor.execute('''
            SELECT COUNT(*), SUM(transferred), SUM(failed) 
            FROM transfers WHERE user_id = ?
        ''', (user_id,))
        result = cursor.fetchone()
        
        if result and result[0] > 0:
            stats_text = f"""
📊 **إحصائيات النقل:**

• عدد العمليات: {result[0]}
• إجمالي المنقول: {result[1] or 0}
• إجمالي الفاشل: {result[2] or 0}
• نسبة النجاح: {((result[1] or 0)/((result[1] or 0) + (result[2] or 0)) * 100):.1f}%
            """
        else:
            stats_text = "📊 لم تقم بأي عمليات نقل بعد"
        
        await event.edit(stats_text)

    async def show_main_menu(self, event):
        """عرض القائمة الرئيسية"""
        keyboard = await self.get_main_keyboard()
        await event.edit("🏠 **القائمة الرئيسية**", buttons=keyboard)

    async def show_group_setup(self, event):
        """عرض إعداد المجموعات"""
        keyboard = await self.get_group_setup_keyboard()
        await event.edit("🔍 **إعداد المجموعات**", buttons=keyboard)

    async def show_settings_menu(self, event):
        """عرض إعدادات النقل"""
        keyboard = await self.get_settings_keyboard()
        await event.edit("⚙️ **إعدادات النقل**", buttons=keyboard)

# التشغيل الرئيسي
async def main():
    # 🔧 استبدل هذه بالقيم الحقيقية
    API_ID = 1234567  # من my.telegram.org
    API_HASH = 'your_api_hash_here'  # من my.telegram.org
    BOT_TOKEN = 'your_bot_token_here'  # من @BotFather
    
    bot = AdvancedMemberTransferBot(
        api_id=23656977,
        api_hash=49d3f43531a92b3f5bc403766313ca1e,
        bot_token=8461163944:AAG692d6NA-4h0O--5GRr9gHEjKNr1P4p1k
    )
    
    await bot.start_bot()

if __name__ == '__main__':
    asyncio.run(main())
