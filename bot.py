import logging
import sqlite3
import re
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

# ---- কনফিগারেশন ----
BOT_TOKEN = "YOUR_BOT_TOKEN" # তোমার বটের টোকেন
ADMIN_ID = 123456789          # তোমার নিজের টেলিগ্রাম আইডি (সংখ্যায়)

# Force Subscribe এর জন্য তোমার নিজের ২টি প্রধান চ্যানেল (ইউজারনেম অথবা আইডি)
REQ_CHANNEL_1 = "@my_main_channel_1" 
REQ_CHANNEL_2 = "@my_main_channel_2"

# লগিং সেটআপ
logging.basicConfig(level=logging.INFO)

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

# ---- ডেটাবেজ সেটআপ ----
def init_db():
    conn = sqlite3.connect('multibot.db')
    cursor = conn.cursor()
    # ইউজার এবং তাদের নিজস্ব চ্যানেলের ডাটা
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            channel_id TEXT
        )
    ''')
    conn.commit()
    conn.close()

init_db()

# ---- হেল্পার ফাংশনস ----
def get_all_users():
    conn = sqlite3.connect('multibot.db')
    cursor = conn.cursor()
    cursor.execute('SELECT user_id FROM users')
    users = [row[0] for row in cursor.fetchall()]
    conn.close()
    return users

def get_user_channel(user_id):
    conn = sqlite3.connect('multibot.db')
    cursor = conn.cursor()
    cursor.execute('SELECT channel_id FROM users WHERE user_id = ?', (user_id,))
    row = cursor.fetchone()
    conn.close()
    return row[0] if row else None

def save_user_channel(user_id, channel_id):
    conn = sqlite3.connect('multibot.db')
    cursor = conn.cursor()
    cursor.execute('INSERT OR REPLACE INTO users (user_id, channel_id) VALUES (?, ?)', (user_id, channel_id))
    conn.commit()
    conn.close()

# Force Subscribe চেক করার ফাংশন
async def check_subscription(user_id: int) -> bool:
    try:
        member1 = await bot.get_chat_member(chat_id=REQ_CHANNEL_1, user_id=user_id)
        member2 = await bot.get_chat_member(chat_id=REQ_CHANNEL_2, user_id=user_id)
        
        valid_statuses = ['member', 'administrator', 'creator']
        return member1.status in valid_statuses and member2.status in valid_statuses
    except Exception:
        return False

# টেক্সট থেকে লিংক বের করার ফাংশন
def extract_urls(text: str):
    return re.findall(r'(https?://\S+)', text)


# ---- ১. ফোর্স সাবস্ক্রিপশন চেক (Middleware / Filter বিকল্প) ----
async def force_sub_failed_reply(message: types.Message):
    # চ্যানেল ২টির লিংক সহ বাটন তৈরি
    buttons = [
        [InlineKeyboardButton(text="📢 আমাদের চ্যানেল ১", url=f"https://t.me/{REQ_CHANNEL_1.replace('@','')}")],
        [InlineKeyboardButton(text="📢 আমাদের চ্যানেল ২", url=f"https://t.me/{REQ_CHANNEL_2.replace('@','')}")],
        [InlineKeyboardButton(text="🔄 জয়েন করেছি (Check)", callback_data="check_sub")]
    ]
    keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)
    await message.answer("❌ **আপনি আমাদের দুটি চ্যানেলে জয়েন করেননি!**\n\nবটটি ব্যবহার করতে নিচের চ্যানেলগুলোতে জয়েন করে 'Check' বাটনে চাপুন।", reply_markup=keyboard, parse_mode="Markdown")


# ---- ২. বটের কমান্ড হ্যান্ডলারস ----

@dp.message(Command("start"))
async def start_cmd(message: types.Message):
    # ডাটাবেজে ইউজার এন্ট্রি করা (চ্যানেল ফাঁকা রেখে)
    if not get_user_channel(message.from_user.id):
        save_user_channel(message.from_user.id, None)
        
    # সাবস্ক্রিপশন চেক
    if not await check_subscription(message.from_user.id):
        await force_sub_failed_reply(message)
        return

    welcome_text = (
        "👋 **স্বাগতম! এটি একটি প্রিমিয়াম চ্যানেল পোস্টার বট।**\n\n"
        "🛠 **সেটআপ গাইড:**\n"
        "১. প্রথমে এই বটটিকে আপনার চ্যানেলে **Admin** বানান।\n"
        "২. এরপর এখানে লিখুন: `/setchannel @your_channel` (আপনার চ্যানেল আইডি)\n\n"
        "সব সেট হয়ে গেলে, আপনি যা লিখে পাঠাবেন তা চমৎকার ইমোজি ও লিংক বাটন সহ আপনার চ্যানেলে চলে যাবে! 😎"
    )
    await message.answer(welcome_text, parse_mode="Markdown")

@dp.callback_query(F.data == "check_sub")
async def check_sub_callback(callback: types.CallbackQuery):
    if await check_subscription(callback.from_user.id):
        await callback.message.delete()
        await callback.message.answer("✅ ধন্যবাদ! আপনার সাবস্ক্রিপশন ভেরিফাইড। এখন আপনি বটটি ব্যবহার করতে পারবেন।\nআপনার চ্যানেল সেট করতে লিখুন: `/setchannel @username`")
    else:
        await callback.answer("⚠️ আপনি এখনো সব চ্যানেলে জয়েন করেননি! দয়া করে জয়েন করুন।", show_alert=True)

@dp.message(Command("setchannel"))
async def set_channel_cmd(message: types.Message):
    if not await check_subscription(message.from_user.id):
        await force_sub_failed_reply(message)
        return

    parts = message.text.split()
    if len(parts) < 2:
        await message.answer("❌ ভুল ফরম্যাট! এভাবে লিখুন: `/setchannel @your_channel_username`")
        return

    channel_id = parts[1]
    save_user_channel(message.from_user.id, channel_id)
    await message.answer(f"✅ আপনার চ্যানেল সফলভাবে সেভ হয়েছে!\n📢 **টার্গেট চ্যানেল:** `{channel_id}`", parse_mode="Markdown")


# ---- ৩. মেইন এডমিন ব্রডকাস্ট সিস্টেম ----

@dp.message(Command("broadcast"))
async def admin_broadcast(message: types.Message):
    # শুধু তুমি (মেইন এডমিন) এই কমান্ড দিতে পারবে
    if message.from_user.id != ADMIN_ID:
        return

    # কমান্ডের পরের অংশটুকু মেসেজ হিসেবে নেওয়া হবে
    broadcast_text = message.text.replace("/broadcast", "").strip()
    if not broadcast_text:
        await message.answer("❌ ব্রডকাস্টের জন্য কোনো মেসেজ লেখেননি। উদাহরণ:\n`/broadcast হাই অল, কেমন আছেন?`")
        return

    all_users = get_all_users()
    success_count = 0

    # সব ইউজারের কাছে মেসেজ পাঠানো
    for user_id in all_users:
        try:
            await bot.send_message(chat_id=user_id, text=f"📢 **অফিসিয়াল আপডেট:**\n\n{broadcast_text}", parse_mode="Markdown")
            success_count += 1
        except Exception:
            continue # ইউজার ব্লক করে রাখলে স্কিপ করবে

    await message.answer(f"🚀 ব্রডকাস্ট সফল হয়েছে!\n👥 মোট {success_count} জন সক্রিয় ইউজারের কাছে মেসেজ পাঠানো হয়েছে।")


# ---- ৪. সুন্দর ডিজাইন ও বাটন সহ চ্যানেলে পোস্ট মেকানিজম ----

@dp.message(F.text | F.photo)
async def process_and_post(message: types.Message):
    # ফোর্স সাবস্ক্রিপশন চেক
    if not await check_subscription(message.from_user.id):
        await force_sub_failed_reply(message)
        return

    # ইউজারের চ্যানেল চেক করা
    user_channel = get_user_channel(message.from_user.id)
    if not user_channel:
        await message.answer("❌ আপনি এখনো কোনো চ্যানেল সেট করেননি! আগে `/setchannel @username` কমান্ড দিন।")
        return

    # টেক্সট অথবা ফটোর ক্যাপশন নেওয়া
    original_text = message.text if message.text else message.caption
    if not original_text:
        await message.answer("❌ টেক্সট অথবা ক্যাপশনে কিছু লিখে পাঠান।")
        return

    # লিংক ডিটেক্ট করা
    urls = extract_urls(original_text)
    clean_text = original_text
    keyboard_buttons = []

    if urls:
        # মেইন লিংকটি প্রথম বাটন হিসেবে নিবে এবং টেক্সট থেকে লিংকটি রিমুভ করবে
        main_url = urls[0]
        clean_text = original_text.replace(main_url, "").strip()
        keyboard_buttons.append([InlineKeyboardButton(text="🔗 ভিজিট করুন / বিস্তারিত", url=main_url)])

    # ✨ ইমোজি এবং সুন্দর ডিজাইনিং ফরম্যাট ✨
    formatted_post = (
        f"🔥 **নতুন আপডেট** 🔥\n"
        f"━━━━━━━━━━━━━━━━━━━━\n\n"
        f"📝 {clean_text}\n\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"⚡ _Posted via Multi-Publisher Bot_"
    )

    reply_markup = InlineKeyboardMarkup(inline_keyboard=keyboard_buttons) if keyboard_buttons else None

    try:
        # ফটো হলে ফটো সহ চ্যানেলে যাবে, টেক্সট হলে শুধু টেক্সট
        if message.photo:
            photo_file_id = message.photo[-1].file_id
            await bot.send_photo(chat_id=user_channel, photo=photo_file_id, caption=formatted_post, reply_markup=reply_markup, parse_mode="Markdown")
        else:
            await bot.send_message(chat_id=user_channel, text=formatted_post, reply_markup=reply_markup, parse_mode="Markdown")

        await message.answer(f"🚀 আপনার চ্যানেলে (`{user_channel}`) সুন্দরভাবে পোস্টটি পাবলিশ হয়েছে!", parse_mode="Markdown")

    except Exception as e:
        await message.answer(f"❌ পোস্ট করা যায়নি।\nℹ️ নিশ্চিত করুন বটটি আপনার চ্যানেলে **Admin** হিসেবে যুক্ত আছে।\n\nError Details: `{str(e)}`", parse_mode="Markdown")


# ---- রান করা ----
if __name__ == "__main__":
    import asyncio
    asyncio.run(dp.start_polling(bot))
