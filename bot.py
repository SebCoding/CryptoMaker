import sys
import time

import pandas as pd
import rapidjson

import logger
from configuration import Configuration
from exchange.ExchangeWS import ExchangeWS

logger = logger.init_custom_logger(__name__)


class Bot:
    INTERVAL = 1

    candles = pd.DataFrame()

    def __init__(self):
        self.config = Configuration.get_config()
        self.pair = self.config['exchange']['pair']
        # self.exchange_rest = ExchangeREST()
        self.exchange_ws = ExchangeWS(self.INTERVAL)

    def print_orderbook(self, top, sleep=0.0):
        ws = self.exchange_ws.public_ws
        orderbook_topic = self.exchange_ws.get_orderbook25_topic(self.pair)
        while True:
            data = ws.fetch(orderbook_topic)
            if data:
                print(f'Orderbook Top {top}')
                # print(f'data: {data}')
                df = pd.DataFrame(data)
                df.set_index('price', inplace=True)
                df.index.astype(float)
                # df['price'] = df['price'].astype(float)
                # df.set_index(['side', 'price'], inplace=True)
                # print(df.to_string())

                sell_df = df.loc[df['side'] == 'Sell'].sort_values('price', ascending=False).tail(top)
                print(sell_df.to_string())
                buy_df = df.loc[df['side'] == 'Buy'].sort_values('price', ascending=False).head(top)
                print(buy_df.to_string())

                spread = float(sell_df.index[-1]) - float(buy_df.index[0])
                print(f'Spread = {spread}\n')
            time.sleep(sleep)  # Orderbook push rate 20ms

    """
        Candle format
        {
            "start": 1641277860,
            "end": 1641277920,
            "period": "1",
            "open": 46289.5,
            "close": 46289.5,
            "high": 46291,
            "low": 46289.5,
            "volume": "4.833",
            "turnover": "223719.5515",
            "confirm": false,
            "cross_seq": 6286368356,
            "timestamp": 1641277877187493
        }
    """
    def print_candles(self, pair, interval, sleep=0.0):
        ws = self.exchange_ws.public_ws
        topic = self.exchange_ws.get_candle_topic(pair, interval)
        last_timestamp = 0
        while True:
            data = ws.fetch(topic)
            if data and data['timestamp'] > last_timestamp:
                #print(rapidjson.dumps(data, indent=2)); exit(0)
                if data['confirm']:
                    if self.candles is None:
                        self.candles = pd.DataFrame.from_records([data])
                    else:
                        self.candles = self.candles.append([data], ignore_index=True)

                print('\n\n\n\n')
                print(self.candles.to_markdown())
                print()

                df = pd.DataFrame.from_records([data])
                print(df.to_markdown())


                last_timestamp = data['timestamp']
            time.sleep(sleep)

    def run_forever(self):
        # self.print_orderbook(5, 0.5)
        self.print_candles(self.pair, self.INTERVAL, sleep=0.5)
