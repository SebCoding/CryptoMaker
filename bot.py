import sys
import time
import datetime as dt
import pandas as pd
import rapidjson

import logger
import utils
from configuration import Configuration
from enums import TradeStatus
from enums.TradeStatus import TradeStatus
from exchange.ExchangeREST import ExchangeREST
from exchange.ExchangeWS import ExchangeWS
from strategies.ScalpEmaRsiAdx import ScalpEmaRsiAdx

logger = logger.init_custom_logger(__name__)


class Bot:
    confirmed_candles = None
    last_candle_timestamp = 0

    def __init__(self):
        self.config = Configuration.get_config()
        self.pair = self.config['exchange']['pair']
        self.strategy = globals()[self.config['strategy']['name']]()
        self.interval = self.strategy.interval
        self.minimum_candles_to_start = self.strategy.minimum_candles_to_start

        self.exchange_rest = ExchangeREST()
        self.exchange_ws = ExchangeWS(self.interval)
        self.candle_topic_name = \
            self.exchange_ws.get_candle_topic(self.pair, self.exchange_ws.interval_map[self.interval])
        self.public_ws = self.exchange_ws.public_ws
        self.private_ws = self.exchange_ws.private_ws

    # Fetch INIT_CANDLES_COUNT candles preceding 'to_time' (not including to_time)
    def get_historic_candles(self, to_time):
        logger.info(f'Fetching {self.minimum_candles_to_start} prior historical candles.')
        from_time = utils.adjust_from_time_timestamp(to_time, self.interval, self.minimum_candles_to_start)
        to_time -= 1  # subtract 1s because get_candle_data() includes candle to 'to_time'
        df = self.exchange_rest.get_candle_data(self.pair, from_time, to_time, self.interval)
        return df

    """
        Push frequency: 1-60s from Bybit
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

    def refresh_candles(self):
        data = self.public_ws.fetch(self.candle_topic_name)
        if data and data['timestamp'] > self.last_candle_timestamp:

            # If we only trade on closed candles ignore data that is not confirmed
            if self.config['trade_entries']['trade_on_closed_candles_only'] and not data['confirm']:
                return False

            to_append = [
                {
                    'start': data['start'],
                    'end': data['end'],
                    'datetime': dt.datetime.fromtimestamp(int(data['start'])),
                    'pair': self.pair,
                    'open': data['open'],
                    'high': data['high'],
                    'low': data['low'],
                    'close': data['close'],
                    'volume': data['volume'],
                    'confirm': data['confirm'],
                    'timestamp': int(data['timestamp'])
                }
            ]
            # DataFrame is empty
            if self.confirmed_candles is None:
                self.confirmed_candles = self.get_historic_candles(int(data['start']))
                self.confirmed_candles = self.confirmed_candles.append(to_append, ignore_index=True)
                # print(self.confirmed_candles.tail(10).to_string()); exit(0)
            # DataFrame contains at least 1 row
            else:
                if data['confirm']:
                    # Previous candle is confirmed we add a new row
                    if self.confirmed_candles["confirm"].iloc[-1]:
                        self.confirmed_candles = self.confirmed_candles.append(to_append, ignore_index=True)
                    # Previous candle is not confirmed we update the last row
                    else:
                        # self.confirmed_candles.drop(self.confirmed_candles.tail(1).index, inplace=True)
                        # self.confirmed_candles = self.confirmed_candles.append(to_append, ignore_index=True)
                        self.confirmed_candles = self.confirmed_candles.iloc[:-1, :].append(to_append,
                                                                                            ignore_index=True)

                # Current candle not confirmed and previous confirmed we add a new row
                elif self.confirmed_candles["confirm"].iloc[-1]:
                    self.confirmed_candles = self.confirmed_candles.append(to_append, ignore_index=True)

                # Current candle not confirmed and previous not confirmed we update the last row
                else:
                    # self.confirmed_candles.drop(self.confirmed_candles.tail(1).index, inplace=True)
                    # self.confirmed_candles = self.confirmed_candles.append(to_append, ignore_index=True)
                    self.confirmed_candles = self.confirmed_candles.iloc[:-1, :].append(to_append, ignore_index=True)

            # Confirm we did not skip any candles
            # Current candle 'start' time must be equal to prior candle 'end' time
            try:
                assert (len(self.confirmed_candles) < 2 or
                        (self.confirmed_candles["start"].iloc[-1] == self.confirmed_candles["end"].iloc[-2]))
            except AssertionError as e:
                msg = f'*******  start[{self.confirmed_candles["start"].iloc[-1]}] != prev_end[{self.confirmed_candles["end"].iloc[-2]}]  *******\n'
                msg += self.confirmed_candles.tail(1).to_string() + '\n'
                logger.error(msg)
                # We are missing data, the dataframe is corrupted. Rebuild the dataframe from scratch
                logger.error('Recovering from missing candle data. rebuilding the dataframe from scratch.')
                self.confirmed_candles = self.get_historic_candles(int(data['start']))
                self.confirmed_candles = self.confirmed_candles.append(to_append, ignore_index=True)

            self.last_candle_timestamp = data['timestamp']
            # print('\n\n')
            # if self.confirmed_candles is not None:
            #     print(self.confirmed_candles.tail(10).to_string())
            return True
        return False

    def print_candles(self, pair, interval, sleep=0.0):
        last_timestamp = 0
        while True:
            data = self.public_ws.fetch(self.candle_topic_name)
            if data and data['timestamp'] > last_timestamp:
                # print(rapidjson.dumps(data, indent=2)); exit(0)

                # Candle confirmed, add to confirmed candles
                if data['confirm']:
                    if self.confirmed_candles is None:
                        self.confirmed_candles = pd.DataFrame.from_records([data])
                    else:
                        self.confirmed_candles = self.confirmed_candles.append([data], ignore_index=True)
                        # self.confirmed_candles = pd.concat([self.confirmed_candles, pd.DataFrame([data])], axis=0, ignore_index=True)

                if self.confirmed_candles is not None:
                    print('\n\n\n\n')
                    print(self.confirmed_candles.to_markdown())
                print()

                df = pd.DataFrame.from_records([data])
                print(df.to_markdown())

                last_timestamp = data['timestamp']
            time.sleep(sleep)

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

    def run_forever(self):
        # self.print_orderbook(5, 0.5)

        with open('trace.txt', 'w') as f:
            while True:
                data_changed = self.refresh_candles()
                if data_changed:
                    df = self.strategy.add_indicators_and_signals(self.confirmed_candles)
                    f.write('')
                    print()
                    f.write('\n' + df.tail(10).to_string())
                    print('\n' + df.tail(10).to_string())
                    res = self.strategy.find_entry()
                    if res['TradeStatus'] in [TradeStatus.EnterLong, TradeStatus.EnterShort]:
                        f.write(f"\nlast_signal_index: {res['signal_index']}")
                        print(f"last_signal_index: {res['signal_index']}")
                        f.write(f"{res['TradeStatus']}: {rapidjson.dumps(res, indent=2)}")
                        print(f"{res['TradeStatus']}: {rapidjson.dumps(res, indent=2)}")
                time.sleep(1)
