import pandas as pd
import rapidjson

from enums.BybitEnums import OrderSide
from exchange.ExchangeBybit import ExchangeBybit
from logging_.Logger import Logger
import time
from Configuration import Configuration
from old.ExchangeWS import ExchangeWS


class Orderbook:
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

    def __init__(self, exchange):
        self._logger = Logger.get_module_logger(__name__)
        self._config = Configuration.get_config()
        self.pair = self._config['exchange']['pair']
        self.exchange = exchange
        self.ws = self.exchange.ws_public
        self.ob25_topic_name = self.exchange.get_orderbook25_topic(self.pair)
        self.last_timestamp = 0

    def get_top1(self):
        """
            This method will loop until new data can be provided from the websocket
            Returns 2 values:
              - A list of containing the top1 entry for buyers, followed by the top1 entry for sellers
              - the spread
        """
        timeout = 120  # timeout after 120s
        start_time = time.time()
        running = 0
        while running < timeout:
            data = self.ws.fetch(self.ob25_topic_name)
            if data and data['timestamp_e6'] > self.last_timestamp:
                spread = abs(float(data['order_book'][25]['price']) - float(data['order_book'][24]['price']))
                return [data['order_book'][24], data['order_book'][25]], spread
            running = time.time() - start_time
        self._logger.error("Orderbook timed out trying to read new data from orderbook websocket.")
        return None, None

    def get_entries(self, top):
        """
            Returns 2 values:
              - the "top" entries on each side
              - the spread
            The data is ordered by price, starting with the lowest buys and ending with the highest sells.
        """
        timeout = 60  # timeout after 60s
        start_time = time.time()
        running = 0
        while running < timeout:
            data = self.ws.fetch(self.ob25_topic_name)
            if data and data['timestamp_e6'] > self.last_timestamp:
                spread = abs(float(data['order_book'][25]['price']) - float(data['order_book'][24]['price']))
                return [data['order_book'][25 - top:25], data['order_book'][25:25 + top]], spread
            running = time.time() - start_time
        self._logger.error("Orderbook timed out trying to read new data from orderbook websocket.")
        return None, None

    def get_spread(self):
        data = self.ws.fetch(self.ob25_topic_name)
        if data:
            return abs(float(data[25]['price']) - float(data[24]['price']))

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
                df.reset_index(drop=True, inplace=True)  # reset row numbers (index) after sort
                # print(df.to_string() + '\n')

                # Print sellers at the top
                sell_df = df[25 - top:25]
                print(sell_df.to_string() + '\n')

                # print buyers at the bottom
                buy_df = df[25:25 + top]
                print(buy_df.to_string() + '\n')

                spread = abs(sell_df.iloc[-1]['price'] - buy_df.iloc[0]['price'])
                if spread > max_spread:
                    max_spread = spread
                print(f"Spread: Sell[{sell_df.iloc[-1]['price']}] - Buy[{buy_df.iloc[0]['price']}] = {spread}")
                print(f'Max Spread: {max_spread}' + '\n')
            time.sleep(sleep)  # Orderbook push rate 20ms

# ob = Orderbook()
# while True:
#     print(*ob.get_top1(1), sep='\n')
#     print('\n')
#     time.sleep(1)
# print(ob.get_spread())
# ob.print_orderbook(top=1, sleep=0.5)
