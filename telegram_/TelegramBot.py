"""
    pip install --user --force-reinstall python-telegram-bot

    How to get a group or a channel chat_id?
    Ask the @username_to_id_bot and it will return the id

    @CryptoMaker2022Bot: token(5093560329:AAH_emOOa09RIUj6RDzWy_wh7pr2ysLnKaI)

    @CryptoMakerGroup: Chat_id = -1001714621495
    https://t.me/+UXhbqp43EzQ3ODlh
"""

import telegram
import datetime as dt
import api_keys
import constants
from Configuration import Configuration


class TelegramBot:
    enabled = Configuration.get_config()['telegram']['enable']
    instance_name = Configuration.get_config()['bot']['instance_name']
    telegram_bot = telegram.Bot(token=api_keys.TELEGRAM_BOT_TOKEN)

    @classmethod
    def send_to_group(cls, msg, fixed_width=True, include_time=False):
        if cls.enabled and api_keys.TELEGRAM_BOT_TOKEN and api_keys.TELEGRAM_GRP_CHAT_ID:
            _now = f'[{dt.datetime.now().strftime(constants.DATETIME_FMT)}] ' if include_time else ''
            if fixed_width:
                msg = f'`{_now}{cls.instance_name}: {msg}`'
            else:
                msg = f'{_now}{cls.instance_name}: {msg}'.replace('-', '\\-')
            cls.telegram_bot.send_message(text=msg, chat_id=api_keys.TELEGRAM_GRP_CHAT_ID,
                                          parse_mode=telegram.ParseMode.MARKDOWN_V2)

"""
    Testing. 
"""
# print(bot.get_me())

# updates = bot.get_updates()
# print(updates[0])

#TelegramBot.send_to_group("Testing, testing")
