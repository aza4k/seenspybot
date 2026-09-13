import asyncio
import argparse
import json
import os
import sys
from telethon import TelegramClient
from telethon.errors import SessionPasswordNeededError
from dotenv import load_dotenv

load_dotenv()

API_ID = int(os.getenv("TELEGRAM_API_ID", 0))
API_HASH = os.getenv("TELEGRAM_API_HASH", "")
STATE_FILE = ".auth_state.json"
SESSION_NAME = "user_session"


async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--status", action="store_true", help="Check auth status")
    parser.add_argument("--request-code", type=str, help="Phone number to request code")
    parser.add_argument("--code", type=str, help="Verification code received in Telegram")
    parser.add_argument("--password", type=str, help="2FA password if required")
    args = parser.parse_args()

    client = TelegramClient(SESSION_NAME, API_ID, API_HASH)
    await client.connect()

    try:
        if args.status:
            is_auth = await client.is_user_authorized()
            if is_auth:
                me = await client.get_me()
                print(f"AUTHORIZED:{me.id}:{me.first_name}")
            else:
                print("NOT_AUTHORIZED")
            return

        if args.request_code:
            phone = args.request_code.strip()
            result = await client.send_code_request(phone)
            with open(STATE_FILE, "w", encoding="utf-8") as f:
                json.dump({
                    "phone": phone,
                    "phone_code_hash": result.phone_code_hash
                }, f)
            print(f"CODE_SENT:{phone}")
            return

        if args.code:
            if not os.path.exists(STATE_FILE):
                print("ERROR:Avval kod so'ralmagan (--request-code)")
                return

            with open(STATE_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)

            phone = data["phone"]
            phone_code_hash = data["phone_code_hash"]

            try:
                await client.sign_in(
                    phone=phone,
                    code=args.code.strip(),
                    phone_code_hash=phone_code_hash
                )
                me = await client.get_me()
                if os.path.exists(STATE_FILE):
                    os.remove(STATE_FILE)
                print(f"SUCCESS:{me.id}:{me.first_name}")
            except SessionPasswordNeededError:
                if args.password:
                    await client.sign_in(password=args.password)
                    me = await client.get_me()
                    if os.path.exists(STATE_FILE):
                        os.remove(STATE_FILE)
                    print(f"SUCCESS:{me.id}:{me.first_name}")
                else:
                    print("PASSWORD_NEEDED:2FA parol talab qilinadi")
            return

    except Exception as e:
        print(f"ERROR:{e}")
    finally:
        await client.disconnect()


if __name__ == "__main__":
    asyncio.run(main())
