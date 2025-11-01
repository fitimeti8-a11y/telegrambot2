import asyncio
import re
import time
import os
from threading import Thread
from flask import Flask, request, jsonify
from pyrogram import Client
from pyrogram.errors import FloodWait

# === Configuration ===
API_ID = int(os.getenv("API_ID", "29969433"))
API_HASH = os.getenv("API_HASH", "884f9ffa4e8ece099cccccade82effac")
SESSION_STRING = os.getenv("SESSION_STRING", "BQHJTBkAsUpm_azwJqDz2tu9oHOE4zXtXxsktHKFLYytvW8zE9cTOTJHcNoFW0LN34sIF_t5hkZxQyiGwvpQdKBZ3jC7e6jsoikhY4uGzGlWxqArJ3yHeprIpivtsKUR_6KSd2Zk4HmRAbWd5PkNBsaOtAcV7NClY0jk5B7vdL-uY0X0WdUkhOH8mT5oznk91yvCRl-oicFiyTrTks8mLm7lbHoGtPSBHt450awdlNQz-_-qs3y2mG_Qk1Qx5xY1WLWyPvSgONQxbRCiUEZC6EwfJan_4pMWYJqEvwSnE3NHc1Dxlox0x9mBRx602NPu-7sFGmiCm0IgaIKBmdEHzFltIKXdjwAAAAHrPloTAA")
TARGET_BOT = os.getenv("TARGET_BOT", "@telebrecheddb_bot")

# === Flask setup ===
app = Flask(__name__)

# === Telegram Client ===
tg_client = Client(
    name="session",
    api_id=API_ID,
    api_hash=API_HASH,
    session_string=SESSION_STRING,
    no_updates=True
)

tg_loop = asyncio.new_event_loop()
tg_ready = False


def parse_bot_response(text: str) -> dict:
    text = text.replace("Телефон", "Phone") \
               .replace("История изменения имени", "Name change history") \
               .replace("Интересовались этим", "Viewed by")

    data = {
        "success": True,
        "username": None,
        "id": None,
        "phone": None,
        "viewed_by": None,
        "name_history": []
    }

    username_match = re.search(r"t\.me/([A-Za-z0-9_]+)", text)
    if username_match:
        data["username"] = username_match.group(1)

    id_match = re.search(r"ID[:： ]+(\d+)", text)
    if id_match:
        data["id"] = id_match.group(1)

    phone_match = re.search(r"Phone[:： ]+(\d+)", text)
    if phone_match:
        data["phone"] = phone_match.group(1)

    viewed_match = re.search(r"Viewed by[:： ]*(\d+)", text)
    if viewed_match:
        data["viewed_by"] = int(viewed_match.group(1))

    history_match = re.findall(r"(\d{2}\.\d{2}\.\d{4}) → @([\w\d_]+),\s*([\w\d, ]+)", text)
    for d, u, i in history_match:
        ids = re.findall(r"\d+", i)
        data["name_history"].append({
            "date": d,
            "username": u,
            "id": ids[0] if ids else None
        })

    return data


async def send_and_wait(username: str) -> dict:
    username = username.strip().lstrip("@")
    message_to_send = f"t.me/{username}"

    try:
        sent = await tg_client.send_message(TARGET_BOT, message_to_send)
    except FloodWait as e:
        await asyncio.sleep(e.value)
        sent = await tg_client.send_message(TARGET_BOT, message_to_send)
    except Exception as e:
        return {"success": False, "error": f"Error contacting bot: {e}"}

    reply_text = None
    start_time = time.time()

    while time.time() - start_time < 60:
        async for msg in tg_client.get_chat_history(TARGET_BOT, limit=10):
            if msg.id > sent.id and not msg.outgoing and msg.text:
                reply_text = msg.text
                break
        if reply_text:
            break
        await asyncio.sleep(2)

    if not reply_text:
        return {"success": False, "error": "No reply from bot after 60s."}

    return parse_bot_response(reply_text)


@app.route("/check")
def check():
    global tg_ready
    if not tg_ready:
        return jsonify({"success": False, "error": "Telegram loop not ready yet."})

    username = request.args.get("username")
    if not username:
        return jsonify({"success": False, "error": "Missing 'username' parameter"}), 400

    try:
        future = asyncio.run_coroutine_threadsafe(send_and_wait(username), tg_loop)
        result = future.result(timeout=70)
        return jsonify(result)
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/")
def home():
    return jsonify({"status": "running", "telegram_ready": tg_ready})


def run_flask():
    port = int(os.getenv("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False, use_reloader=False)


async def start_tg():
    global tg_ready
    await tg_client.start()
    tg_ready = True
    print("✅ Telegram client started successfully")


def main():
    global tg_loop
    tg_loop.create_task(start_tg())
    Thread(target=run_flask, daemon=True).start()
    tg_loop.run_forever()


if __name__ == "__main__":
    asyncio.set_event_loop(tg_loop)
    main()