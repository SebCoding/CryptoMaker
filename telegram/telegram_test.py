# https://docs.telethon.dev/en/latest/index.html
import asyncio
from datetime import datetime
import time

import telebot
from telethon.sync import TelegramClient
from telethon.tl.types import InputPeerUser, InputPeerChannel
from telethon import TelegramClient, sync, events

# Example
# import telethon
# async def main():
#     peer = await client.get_input_entity('someone')
#     print(peer) # to get user_id and access_hash
# client.loop.run_until_complete(main())

# get your api_id, api_hash, token
# from telegram as described above
# https://my.telegram.org/apps
import api_keys

api_id = api_keys.TELEGRAM_API_ID
api_hash = api_keys.TELEGRAM_API_HASH
phone = api_keys.TELEGRAM_PHONE
token = 'bot token'


async def send_message_to_user(user_name, message):
    client = TelegramClient('session', api_id, api_hash)
    await client.connect()

    # in case of script ran first time it will
    # ask either to input token or otp sent to
    # number or sent or your telegram id
    if not await client.is_user_authorized():
        await client.send_code_request(phone)
        # signing in the client
        await client.sign_in(phone, input('Enter the code: '))

    try:
        # Was able to find these by calling client.get_entity(user_name)
        # receiver_user_id = 910877967
        # receiver_user_hash = 2376862059296984476
        # receiver = InputPeerUser(receiver_user_id, receiver_user_hash)

        receiver = await client.get_input_entity(user_name)

        # receiver_entity = client.get_entity(user_name)
        # print(receiver_entity)

        print(f'Sending to Telegram user[{user_name}]. Message=[{message}]')
        # sending message using telegram client
        await client.send_message(receiver, message, parse_mode='html')
    except Exception as e:
        # there may be many error coming in while like peer
        # error, wrong access_hash, flood_error, etc
        print(e);
    await client.disconnect()

# Send message to user
# message = f'{int(time.time())}: It\'s full of mosquitoes in here.'
# asyncio.run(send_message_to_user('@SebLife3', message))

# To send messages to chat or group (the group must be public) use the invite link
# otherwise you get this error if you use the name:
# > You can't write in this chat (caused by SendMessageRequest)
message = f'{int(time.time())}: Sending messages to group from python.'
asyncio.run(send_message_to_user('https://t.me/CryptoMakerChannelTest', message))




