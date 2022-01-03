import time

import pandas as pd

import logger
from configuration import Configuration
from exchange.ExchangeWS import ExchangeWS

logger = logger.init_custom_logger(__name__)


class Bot:

    def __init__(self):
        self.config = Configuration.get_config()
        self.pair = self.config['exchange']['pair']
        # self.exchange_rest = ExchangeREST()
        self.exchange_ws = ExchangeWS()

    def run_forever(self):
        ws = self.exchange_ws.public_ws
        orderbook_topic = self.exchange_ws.get_orderbook25_topic(self.pair)
        top = 5
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
            time.sleep(0.5)  # Orderbook 20ms
