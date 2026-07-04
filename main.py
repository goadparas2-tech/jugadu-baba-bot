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
IPHONE_REWARD_LINK = "https://apps.apple.com/in/app/mehmandari/id6766165293"
ANDROID_REWARD_LINK = "https://t.me/jugaduBaba0/97"
YOUTUBE_CHANNEL = "Jugadu Baba"
YOUTUBE_CHANNEL_URL = "https://youtube.com/@JugaduBaba-bmw"
LINK_DELETE_SECONDS = 30
# ================================

logging.basicConfig(format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO)
logger = logging.getLogger(__name__)

SUBSCRIBE_KEYWORDS = ["subscribed", "subscribers", "सदस्यता"]


async def verify_subscription_via_ocr(photo_bytes: bytes) -> tuple[bool, str]:
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
        is_verified = any(kw.lower() in full_text for kw in SUBSCRIBE_KEYWORDS)
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
    device_label = "🍏 Kothi-Bangle Wala iPhone Link" if device == "iphone" else "🤖 Desi Android Link"

    reward_text = (
        f"🥳 *Mubarak Ho {name}! Chha Gaye Guru!* 🎉\n"
        f"────────────────────────\n"
        f"Baba tumse bohot prasann hue! 🧙‍♂️✨\n"
        f"Sab verify ho gaya hai. Tumhari imandari dekh ke rona aa gaya! 😂\n\n"
        f"👇 *Neeche dabaao aur maze lo:* 👇\n\n"
        f"⚠️ *DHYAN SE:* Yeh link sirf `{LINK_DELETE_SECONDS} seconds` mein dhuwan ban ke uuad jayega! 💣\n"
        f"Fatafat click karo, deri mat karna! ⏰"
    )

    keyboard = [[InlineKeyboardButton(f"🚀 {device_label} LO!", url=reward_link)]]

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
                f"🕵️‍♂️ *BABA! Naya Bakra Hazir Hai — #{serial}*\n"
                f"────────────────────────\n"
                f"👤 *Naam:* {user.first_name}\n"
                f"🆔 *ID:* `{uid}`\n"
                f"🔗 *Username:* @{user.username or 'N/A'}"
            ),
            parse_mode="Markdown"
        )
    except Exception as e:
        logger.error(f"Admin notification failed: {e}")

    keyboard = [[
        InlineKeyboardButton("🍏 Ameer ka iPhone", callback_data=f"device_iphone_{uid}"),
        InlineKeyboardButton("🤖 Sasta-Tikau Android", callback_data=f"device_android_{uid}"),
    ]]

    await update.message.reply_text(
        f"👋 *Aao yaara {user.first_name}! Swagat hai!*\n\n"
        f"🔮 *{YOUTUBE_CHANNEL}* ke gufa mein aapka swagat hai!\n"
        f"Yahan sab milega, par pehle ek chota sa test. 😉\n\n"
        f"📱 *Pehle ye batao, jeb mein kaunsa maal hai?*",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown"
    )


async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    uid = user.id

    if uid not in user_data:
        await update.message.reply_text("🚨 *Arrey ruko ruko!* Pehle tameez se /start dabao, phir photo bhejiyo! 😂")
        return

    uinfo = user_data[uid]
    state = uinfo.get("state", "")
    serial = uinfo.get("serial", get_serial(uid))
    device = uinfo.get("device", "unknown")

    if state not in ("waiting_subscribe", "waiting_like"):
        await update.message.reply_text("🤷‍♂️ *Arrey bhai!* Abhi photo ki koi zaroorat nahi hai. Maze mat lo, /start karo!")
        return

    # STEP 1 — Subscribe Verification via OCR
    if state == "waiting_subscribe":
        processing_msg = await update.message.reply_text("🔍 *Ruko zara... Baba ka scanner chal raha hai!* ⏳", parse_mode="Markdown")

        photo_file = await update.message.photo[-1].get_file()
        photo_bytes = await photo_file.download_as_bytearray()
        is_verified, _ = await verify_subscription_via_ocr(bytes(photo_bytes))

        try:
            await context.bot.delete_message(chat_id=update.message.chat_id, message_id=processing_msg.message_id)
        except Exception:
            pass

        if not is_verified:
            await update.message.reply_text(
                "❌ *Arey bhai! Yeh kya bheja?*\n\n"
                "🔎 Baba ke scanner ne koi subscription nahi dekha!\n\n"
                "📸 Sahi screenshot bhejo jisme *Subscribed*, *Subscribers*, ya *सदस्यता* clearly dikh raha ho.\n"
                "Channel ke andar se screenshot lo aur dobara bhejo! 🙏",
                parse_mode="Markdown"
            )
            return

        user_data[uid]["state"] = "waiting_like"

        try:
            await context.bot.forward_message(chat_id=ADMIN_CHAT_ID, from_chat_id=update.message.chat_id, message_id=update.message.message_id)
            await context.bot.send_message(
                chat_id=ADMIN_CHAT_ID,
                text=f"✅ *Step 1 (Subscribe) OCR se Verify Ho Gaya!* \n🔢 Bakra: *#{serial}* | 📱 Phone: {device.upper()}",
                parse_mode="Markdown"
            )
        except Exception as e:
            logger.error(f"Admin forward failed: {e}")

        keyboard = [[InlineKeyboardButton("📺 YouTube Channel", url=YOUTUBE_CHANNEL_URL)]]
        await update.message.reply_text(
            f"🎯 *Wah! Ek teer se ek shikar!* (Subscribe Done) ✅\n"
            f"📊 *Progress:* `[█████░░░░░] 50%` \n\n"
            f"🔥 *Ab aakhri kaam:* Niche wale button se jaake kisi bhi ek video ko 👍 *Like* thoko, aur uska screenshot yahan chipkao! 📸",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="Markdown"
        )

    # STEP 2 — Like Verified
    elif state == "waiting_like":
        user_data[uid]["state"] = "done"

        try:
            await context.bot.forward_message(chat_id=ADMIN_CHAT_ID, from_chat_id=update.message.chat_id, message_id=update.message.message_id)
            await context.bot.send_message(
                chat_id=ADMIN_CHAT_ID,
                text=f"👑 *Step 2 (Like) bhi khatam! Link bhej diya.* \n🔢 Bakra: *#{serial}*",
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
        await update.message.reply_text("🛑 *Oye hero!* Mujhe sirf photo/screenshot chahiye, koi aisi-waisi file mat bhejo! 📸")


async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data

    uid = update.effective_user.id
    if uid not in user_data:
        await query.message.reply_text("⏳ Kahani khatam, paisa hazam! Session expire ho gaya, firse /start karo.")
        return

    keyboard = [[InlineKeyboardButton("📺 YouTube Link Pe Jaao", url=YOUTUBE_CHANNEL_URL)]]

    if data.startswith("device_iphone_"):
        user_data[uid]["device"] = "iphone"
        user_data[uid]["state"] = "waiting_subscribe"
        await query.edit_message_text(
            f"🍏 *Oho! Kothi-Bangle wale log! iPhone select kiya!*\n"
            f"📊 *Progress:* `[░░░░░░░░░░] 0%` \n\n"
            f"👉 *Step 1:* Niche button pe click karke channel ko *Subscribe* karo aur screenshot yahan bhej do! 📸",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="Markdown"
        )

    elif data.startswith("device_android_"):
        user_data[uid]["device"] = "android"
        user_data[uid]["state"] = "waiting_subscribe"
        await query.edit_message_text(
            f"🤖 *Zindabad! Desi Android select kiya! Humara wala phone!*\n"
            f"📊 *Progress:* `[░░░░░░░░░░] 0%` \n\n"
            f"👉 *Step 1:* Niche button pe click karke channel ko *Subscribe* karo aur screenshot yahan bhej do! 📸",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="Markdown"
        )


async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    state = user_data.get(uid, {}).get("state", "")

    if state == "waiting_subscribe":
        await update.message.reply_text("☝️ Baatein kam, kaam zyada! Pehle channel Subscribe karo aur screenshot bhejo! 📸")
    elif state == "waiting_like":
        await update.message.reply_text("👍 Ek pyara sa Like dabaao video par, aur uska screenshot yahan chipkaao boss!")
    else:
        await update.message.reply_text("Arrey bhai sahab! Seedhe /start likho aur system shuru karo! 😎")


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

    logger.info("Jugadu Baba Bot is online and laughing...")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
