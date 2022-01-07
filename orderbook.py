import pandas as pd
import logger
import time
from configuration import Configuration
from exchange.ExchangeWS import ExchangeWS


class Orderbook:

    def __init__(self):
        self.logger = logger.init_custom_logger(__name__)
        self.config = Configuration.get_config()
        self.pair = self.config['exchange']['pair']
        self.exchange_ws = ExchangeWS()
        self.public_ws = self.exchange_ws.public_ws
        self.orderbook_top25_topic_name = self.exchange_ws.get_orderbook25_topic(self.pair)

    def print_orderbook(self, top, sleep=0.0):
        while True:
            data = self.public_ws.fetch(self.orderbook_top25_topic_name)
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
