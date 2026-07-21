import os
import logging
import asyncio
import base64
import httpx
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ContextTypes

# ============ CONFIG ============
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
ADMIN_CHAT_ID = int(os.environ.get("ADMIN_CHAT_ID", "0"))
OCR_API_KEY = os.environ.get("OCR_API_KEY", "")

IPHONE_REWARD_LINK = "https://jugadutech2026.blogspot.com/?m=1"
ANDROID_REWARD_LINK = "https://jugadutech2026.blogspot.com/?m=1"
YOUTUBE_CHANNEL = "Jugadu Baba"
YOUTUBE_CHANNEL_URL = "https://youtube.com/@techjugad-9?si=pAzLXsooI2HpnZSL"

# 👇 AAPKA HOW TO DOWNLOAD WALA LINK YAHAN SET HAI 👇
HOW_TO_DOWNLOAD_URL = "https://t.me/Babamodsapkk/15"

# TIMER: 5 Min (300 Seconds)
LINK_DELETE_SECONDS = 300 
# ================================

logging.basicConfig(format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO)
logger = logging.getLogger(__name__)

# Keywords for checking both Like and Subscribe in a single image
COMBINED_KEYWORDS = ["subscribed", "subscribers", "सदस्यता", "liked", "like", "पसंद", "share", "remix", "comment"]

async def verify_image_via_ocr(photo_bytes: bytes, keywords: list) -> tuple[bool, str]:
    try:
        b64 = base64.b64encode(photo_bytes).decode("utf-8")
        payload = {
            "apikey": OCR_API_KEY,
            "base64Image": f"data:image/jpeg;base64,{b64}",
            "language": "eng",
            "isOverlayRequired": False,
            "detectOrientation": True,
            "scale": True,
            "OCREngine": 2,
        }
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post("https://api.ocr.space/parse/image", data=payload)
            resp.raise_for_status()
            data = resp.json()

        parsed = data.get("ParsedResults", [])
        if not parsed:
            return False, ""

        full_text = " ".join(r.get("ParsedText", "") for r in parsed).lower()
        is_verified = any(kw.lower() in full_text for kw in keywords)
        return is_verified, full_text

    except Exception as e:
        logger.error(f"OCR verification error: {e}")
        return False, ""

user_data = {}
user_counter = 0
uid_to_serial = {}

def get_serial(uid: int) -> int:
    global user_counter
    if uid not in uid_to_serial:
        user_counter += 1
        uid_to_serial[uid] = user_counter
    return uid_to_serial[uid]

async def delete_message_later(context, chat_id, message_id, delay):
    await asyncio.sleep(delay)
    try:
        await context.bot.delete_message(chat_id=chat_id, message_id=message_id)
    except Exception as e:
        logger.error(f"Delete error: {e}")

async def send_reward_link(context, uid: int, uinfo: dict):
    device = uinfo.get("device", "iphone")
    name = uinfo.get("name", "User")
    reward_link = IPHONE_REWARD_LINK if device == "iphone" else ANDROID_REWARD_LINK
    device_label = "🍏 Get iPhone Link" if device == "iphone" else "🤖 Get Android Link"

    # Polite Reward Message
    reward_text = (
        f"🎉 *Congratulations {name}!* \n"
        f"────────────────────────\n"
        f"Aapka screenshot successfully verify ho gaya hai. ✅\n\n"
        f"👇 *Niche aapka reward link diya gaya hai:* 👇\n\n"
        f"*(💡 Agar aapko App ya Movie download karne mein pareshani ho, toh kripya 'How to Download' wala video zaroor dekhein.)*\n\n"
        f"⚠️ *Dhyan dein:* Yeh link security ke liye sirf `5 Minute` tak valid rahega. Kripya jaldi click karein!"
    )

    keyboard = [
        [InlineKeyboardButton(f"🚀 {device_label}", url=reward_link)],
        [InlineKeyboardButton("🎬 How to Download (Tutorial)", url=HOW_TO_DOWNLOAD_URL)]
    ]

    sent = await context.bot.send_message(
        chat_id=uid,
        text=reward_text,
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown"
    )
    asyncio.create_task(delete_message_later(context, uid, sent.message_id, LINK_DELETE_SECONDS))
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    uid = user.id
    serial = get_serial(uid)

    user_data[uid] = {
        "state": "choosing_device",
        "name": user.first_name,
        "username": user.username or "N/A",
        "serial": serial,
    }

    try:
        await context.bot.send_message(
            chat_id=ADMIN_CHAT_ID,
            text=(
                f"👤 *New User Alert — #{serial}*\n"
                f"────────────────────────\n"
                f"👤 *Name:* {user.first_name}\n"
                f"🆔 *ID:* `{uid}`\n"
                f"🔗 *Username:* @{user.username or 'N/A'}"
            ),
            parse_mode="Markdown"
        )
    except Exception as e:
        logger.error(f"Admin notification failed: {e}")

    keyboard = [[
        InlineKeyboardButton("🍏 iPhone (iOS)", callback_data=f"device_iphone_{uid}"),
        InlineKeyboardButton("🤖 Android", callback_data=f"device_android_{uid}"),
    ]]

    await update.message.reply_text(
        f"👋 *Namaste {user.first_name}!* Aapka swagat hai.\n\n"
        f"Kripya aage badhne ke liye apna device select karein:",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown"
    )

async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    uid = user.id

    if uid not in user_data:
        await update.message.reply_text("🚨 Kripya pehle /start command ka use karein.")
        return

    uinfo = user_data[uid]
    state = uinfo.get("state", "")
    serial = uinfo.get("serial", get_serial(uid))
    device = uinfo.get("device", "unknown")

    if state != "waiting_screenshot":
        await update.message.reply_text("🤷‍♂️ Abhi screenshot ki zarurat nahi hai. Kripya process start karne ke liye /start par click karein.")
        return

    # 🚀 YAHAN SE ANIMATION START HOTI HAI 🚀
    processing_msg = await update.message.reply_text("🔄 *System Initialization...* `[----------] 0%`", parse_mode="Markdown")
    await asyncio.sleep(0.5)
    await processing_msg.edit_text("📡 *Connecting to Server...* `[██--------] 20%`", parse_mode="Markdown")
    await asyncio.sleep(0.5)
    await processing_msg.edit_text("🔍 *Image Scanning Started...* `[████------] 40%`", parse_mode="Markdown")
    await asyncio.sleep(0.5)
    await processing_msg.edit_text("🤖 *Checking Subscribe & Like...* `[███████---] 70%`", parse_mode="Markdown")
    await asyncio.sleep(0.5)
    await processing_msg.edit_text("⏳ *Finalizing Verification...* `[█████████-] 90%`", parse_mode="Markdown")

    # OCR Processing
    photo_file = await update.message.photo[-1].get_file()
    photo_bytes = await photo_file.download_as_bytearray()
    is_verified, _ = await verify_image_via_ocr(bytes(photo_bytes), COMBINED_KEYWORDS)

    try:
        await context.bot.delete_message(chat_id=update.message.chat_id, message_id=processing_msg.message_id)
    except Exception:
        pass

    if not is_verified:
        await update.message.reply_text(
            "❌ *Verification Failed!* `[██████████] 100%`\n\n"
            "🔎 Lagta hai aapne channel Subscribe ya video Like nahi kiya hai.\n\n"
            "📸 Kripya YouTube par video ko Like aur channel ko Subscribe karein, aur ek clear screenshot yahan bhejein jisme dono dikh rahe hon. 🙏",
            parse_mode="Markdown"
        )
        return

    user_data[uid]["state"] = "done"

    try:
        await context.bot.forward_message(chat_id=ADMIN_CHAT_ID, from_chat_id=update.message.chat_id, message_id=update.message.message_id)
        await context.bot.send_message(
            chat_id=ADMIN_CHAT_ID,
            text=f"✅ *Task Complete! OCR Verified!* \n🔢 User: *#{serial}* | 📱 Phone: {device.upper()}\nReward link sent successfully.",
            parse_mode="Markdown"
        )
    except Exception as e:
        logger.error(f"Admin forward failed: {e}")

    await send_reward_link(context, uid, user_data[uid])

async def handle_document(update: Update, context: ContextTypes.DEFAULT_TYPE):
    doc = update.message.document
    if doc and doc.mime_type and "image" in doc.mime_type:
        await handle_photo(update, context)
    else:
        await update.message.reply_text("🛑 Kripya sirf image/screenshot file hi bhejein.")

async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data

    uid = update.effective_user.id
    if uid not in user_data:
        await query.message.reply_text("⏳ Session expire ho gaya hai. Kripya fir se /start karein.")
        return

    keyboard = [
        [InlineKeyboardButton("📺 YouTube Channel Par Jayein", url=YOUTUBE_CHANNEL_URL)]
    ]

    if data.startswith("device_iphone_"):
        user_data[uid]["device"] = "iphone"
        user_data[uid]["state"] = "waiting_screenshot"
        await query.edit_message_text(
            f"🍏 *Aapne iPhone (iOS) select kiya hai.*\n\n"
            f"👉 *STEP 1:* Niche diye gaye **YouTube Channel** button par click karein. Kisi ek video ko *Like* karein aur channel ko *Subscribe* karein.\n\n"
            f"📸 *STEP 2:* Kripya uske baad ek screenshot (jisme Subscribe aur Like dono dikhein) yahan bhej dein.",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="Markdown"
        )

    elif data.startswith("device_android_"):
        user_data[uid]["device"] = "android"
        user_data[uid]["state"] = "waiting_screenshot"
        await query.edit_message_text(
            f"🤖 *Aapne Android select kiya hai.*\n\n"
            f"👉 *STEP 1:* Niche diye gaye **YouTube Channel** button par click karein. Kisi ek video ko *Like* karein aur channel ko *Subscribe* karein.\n\n"
            f"📸 *STEP 2:* Kripya uske baad ek screenshot (jisme Subscribe aur Like dono dikhein) yahan bhej dein.",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="Markdown"
        )

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    state = user_data.get(uid, {}).get("state", "")

    if state == "waiting_screenshot":
        await update.message.reply_text("☝️ Kripya pehle video ko Like aur channel ko Subscribe karke ek screenshot bhejein.")
    else:
        await update.message.reply_text("Kripya process shuru karne ke liye /start type karein.")

def main():
    if not TELEGRAM_BOT_TOKEN:
        raise ValueError("TELEGRAM_BOT_TOKEN set nahi hai!")
    if not ADMIN_CHAT_ID or ADMIN_CHAT_ID == 0:
        raise ValueError("ADMIN_CHAT_ID set nahi hai!")

    app = Application.builder().token(TELEGRAM_BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    app.add_handler(MessageHandler(filters.Document.IMAGE, handle_document))
    app.add_handler(CallbackQueryHandler(handle_callback))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))

    logger.info("Bot is online and running...")
    app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
