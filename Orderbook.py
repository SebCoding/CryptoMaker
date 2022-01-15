"""
    Class implementation of the orderbook.
    It uses websockets to get the data.

    topics:
     - orderBookL2_25: Fetches the orderbook with a depth of 25 orders per side.
        => Push frequency: 20ms

     - orderBookL2_200: Fetches the orderbook with a depth of 200 orders per side.
        => Push frequency: 100ms

     After the subscription response, the first response will be the snapshot response.
     This shows the entire orderbook. The data is ordered by price, starting with the
     lowest buys and ending with the highest sells. Following this, all responses are
     in the delta format, which represents updates to the orderbook relative to the
     last response.
"""
import pandas as pd

from exchange.ExchangeBybit import ExchangeBybit
from logging_.Logger import Logger
import time
from Configuration import Configuration
from old.ExchangeWS import ExchangeWS


class Orderbook:

    def __init__(self):
        self._logger = Logger.get_module_logger(__name__)
        self._config = Configuration.get_config()
        self.pair = self._config['exchange']['pair']
        self.exchange = ExchangeBybit()
        self.ws = self.exchange.ws_public
        self.ob25_topic_name = self.exchange.get_orderbook25_topic(self.pair)

    # Return the "top" entries on each side
    def get_orderbook(self, top, side=None):

    def print_orderbook(self, top, sleep=0.0):
        max_spread = 0
        while True:
            # orderBookL2_25: Fetches the orderbook with a depth of 25 orders per side.
            data = self.ws.fetch(self.ob25_topic_name)
            if data:
                print(f'Orderbook Top {top}')
                # print(f'data: {data}')
                df = pd.DataFrame(data)
                df.drop(columns=['id'])
                df = df[['symbol', 'side', 'size', 'price']]
                df['size'] = df['size'].astype(float)
                df['price'] = df['price'].astype(float)

                # For some reason the data does not arrive grouped and sorted properly
                # Re-sort by side, price in descending order
                df.sort_values(['side', 'price'], ascending=False, inplace=True)
                df.reset_index(drop=True, inplace=True) # reset row numbers (index) after sort
                # print(df.to_string() + '\n')

                # Print sellers at the top
                sell_df = df[25-top:25]
                print(sell_df.to_string() + '\n')

                # print buyers at the bottom
                buy_df = df[25:25+top]
                print(buy_df.to_string() + '\n')

                spread = abs(float(sell_df.iloc[-1]['price']) - float(buy_df.iloc[0]['price']))
                if spread > max_spread:
                    max_spread = spread
                print(f"Spread: Sell[{sell_df.iloc[-1]['price']}] - Buy[{buy_df.iloc[0]['price']}] = {spread}")
                print(f'Max Spread: {max_spread}' + '\n')
            time.sleep(sleep)  # Orderbook push rate 20ms

# ob = Orderbook()
# ob.print_orderbook(top=1, sleep=0.5)
