"""


Use this token to access the HTTP API:
5093560329:AAH_emOOa09RIUj6RDzWy_wh7pr2ysLnKaI
Keep your token secure and store it safely, it can be used by anyone to control your bot.
https://core.telegram.org/bots/api

First run at the terminal:
pip install telegram-send
telegram-send --configure
"""
import telegram_send as ts


def send_telegram_message(message):
    ts.send(messages=[str(message)])


send_telegram_message("Hello")
