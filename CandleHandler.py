import sys

import pandas as pd
import time

import rapidjson
import arrow

import utils
from Configuration import Configuration
from enums.SignalMode import SignalMode
from logging_.Logger import Logger
import datetime as dt


class CandleHandler:
    _candles_df = None
    _last_candle_timestamp = 1

    # Everytime we reach this value of additional rows to the original count, we delete this amount of the oldest rows.
    # For example: after each 1000 new rows we delete the 1000 oldest rows
    DROP_OLD_ROWS_THRESHOLD = 1000

    def __init__(self, exchange, interval=None, signal_mode=None, minimum_candles_to_start=0):
        """
            If interval or signal_mode are provided they override the config file.
        """
        self._logger = Logger.get_module_logger(__name__)
        self._config = Configuration.get_config()
        self.pair = self._config['exchange']['pair']

        self.interval = interval if interval else self._config['trading']['interval']
        self.signal_mode = signal_mode if signal_mode else self._config['strategy']['signal_mode']
        self.sub_interval_secs = int(self._config['strategy']['sub_interval_secs'])

        if minimum_candles_to_start > 0:
            self.minimum_candles_to_start = minimum_candles_to_start
        else:
            self.minimum_candles_to_start = int(self._config['strategy']['minimum_candles_to_start'])

        self._exchange = exchange
        self._candle_topic_name = \
            self._exchange.get_candle_topic(self.pair, self._exchange.interval_map[self.interval])
        self.ws_public = self._exchange.ws_public

        # Used fir sub_interval signal_mode
        self.last_confirmed_timestamp = 0
        self.last_result_timestamp = 0
        self.received_confirmed_candle = False

    # Fetch 'minimum_candles_to_start' candles preceding 'to_time' (not including to_time)
    def get_historic_candles(self, to_time):
        self._logger.info(f'\nFetching {int(self.minimum_candles_to_start)} {self.interval} historical candles.')
        from_time = utils.adjust_from_time_timestamp(to_time, self.interval, self.minimum_candles_to_start)
        to_time -= 1  # subtract 1s because get_candle_data() includes candle to 'to_time'
        df = self._exchange.get_candle_data(self.pair, from_time, to_time, self.interval)
        return df

    def get_refreshed_candles(self):
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
            Returns 2 values: candles dataframe and True/False if the data has been modified since last call
        """
        data_changed = False
        candle_list = self.ws_public.fetch(self._candle_topic_name)
        if candle_list:
            for candle in candle_list:
                if candle['timestamp'] > self._last_candle_timestamp:
                    # If we only trade on closed candles ignore data that is not confirmed
                    if self.signal_mode == SignalMode.Interval and not candle['confirm']:
                        # Assuming confirmed candles are placed before the unconfirmed candles in the list,
                        # we can exit on the 1st unconfirmed candle encountered
                        return self._candles_df, False

                    if self.signal_mode == SignalMode.SubInterval and candle['confirm']:
                        self.last_confirmed_timestamp = int(candle['end'])
                        self.last_result_timestamp = int(candle['end'])
                        self.received_confirmed_candle = True

                    to_append = [
                        {
                            'start': candle['start'],
                            'end': candle['end'],
                            'start_time': dt.datetime.fromtimestamp(int(candle['start'])),
                            'end_time': dt.datetime.fromtimestamp(int(candle['end'])),
                            'pair': self.pair,
                            'open': candle['open'],
                            'high': candle['high'],
                            'low': candle['low'],
                            'close': candle['close'],
                            'volume': candle['volume'],
                            'confirm': candle['confirm'],
                            'timestamp': int(candle['timestamp'])
                        }
                    ]

                    # DataFrame is empty
                    if self._candles_df is None:
                        self._candles_df = self.get_historic_candles(int(candle['start']))
                        self._candles_df = self._candles_df.append(to_append, ignore_index=True)
                        # print(self._candles_df.tail(10).to_string()); exit(0)
                    # DataFrame contains at least 1 row
                    else:
                        if candle['confirm']:
                            # Previous candle is confirmed we add a new row
                            if self._candles_df["confirm"].iloc[-1]:
                                self._candles_df = self._candles_df.append(to_append, ignore_index=True)

                            # Previous candle is not confirmed we update the last row
                            else:
                                # self.confirmed_candles.drop(self.confirmed_candles.tail(1).index, inplace=True)
                                # self.confirmed_candles = self.confirmed_candles.append(to_append, ignore_index=True)
                                self._candles_df = self._candles_df.iloc[:-1, :].append(to_append,
                                                                                        ignore_index=True)
                        # Current candle not confirmed and previous candle is confirmed we add a new row
                        elif self._candles_df["confirm"].iloc[-1]:
                            self._candles_df = self._candles_df.append(to_append, ignore_index=True)

                        # Current candle not confirmed and previous not confirmed we update the last row
                        else:
                            # self.confirmed_candles.drop(self.confirmed_candles.tail(1).index, inplace=True)
                            # self.confirmed_candles = self.confirmed_candles.append(to_append, ignore_index=True)
                            self._candles_df = self._candles_df.iloc[:-1, :].append(to_append, ignore_index=True)

                    # Confirm that the websocket did not skip any data
                    # Current candle 'start' time must be equal to prior candle 'end' time
                    self.validate_last_entry(to_append)

                    self._last_candle_timestamp = int(candle['timestamp'])
                    data_changed = True

                    # Every DROP_OLD_ROWS_LIMIT new rows,
                    # drop the oldest DROP_OLD_ROWS_LIMIT rows
                    if len(self._candles_df) > self.minimum_candles_to_start + self.DROP_OLD_ROWS_THRESHOLD:
                        self._logger.info(f'Dropping oldest {self.DROP_OLD_ROWS_THRESHOLD} of candles dataframe.')
                        self._candles_df = self._candles_df.tail(self.DROP_OLD_ROWS_THRESHOLD).copy()
                        self._candles_df.reset_index(inplace=True)

                    self._candles_df['open'] = self._candles_df['open'].astype(float)
                    self._candles_df['high'] = self._candles_df['high'].astype(float)
                    self._candles_df['low'] = self._candles_df['low'].astype(float)
                    self._candles_df['close'] = self._candles_df['close'].astype(float)
                    self._candles_df['volume'] = self._candles_df['volume'].astype(float)

        # print('\n' + self._candles_df.tail(10).to_string())

        if self.signal_mode == SignalMode.SubInterval and data_changed:
            # If we received a confirmed candle, we must return the result even if an unconfirmed candle follows
            if self.received_confirmed_candle:
                self.received_confirmed_candle = False
                self.last_result_timestamp = self.last_confirmed_timestamp
            else:
                now = int(time.time())
                elapsed_time = now - self.last_result_timestamp if self.last_result_timestamp != 0 else 0
                if elapsed_time >= self.sub_interval_secs:
                    self.last_result_timestamp = now
                    if self._config['bot']['display_dataframe']:
                        self._logger.info(f'sub_interval, elapsed time = {elapsed_time}s')
                else:
                    # Even if there is a data_changed we return false because we simulate updates only every
                    # sub_interval in seconds
                    return self._candles_df, False

        return self._candles_df, data_changed

    def validate_last_entry(self, to_append):
        """
            Confirm that the websocket did not skip any data
            Current candle 'start' time must be equal to prior candle 'end' time
        """
        if self._candles_df is not None and len(self._candles_df) >= 2:
            start_timestamp = int(self._candles_df["start"].iloc[-1])
            if self._candles_df["start"].iloc[-1] != self._candles_df["end"].iloc[-2]:
                valid = False
                msg = f'*******  cur_start[{self._candles_df["start_time"].iloc[-1]}] != ' \
                      f'prev_end[{self._candles_df["end_time"].iloc[-2]}]  *******\n'
                msg += self._candles_df.tail(2).to_string() + '\n'
                self._logger.error(msg)
                # The dataframe is corrupted. Rebuild the dataframe from scratch
                self._logger.error(
                    'Retying to recover from missing candle data. Rebuilding the dataframe from scratch.')
                self._candles_df = self.get_historic_candles(start_timestamp)
                self._candles_df = self._candles_df.append(to_append, ignore_index=True)
                self._logger.error(self.interval + ' candle dataframe has been rebuilt successfully.')

    def get_latest_price(self):
        self.get_refreshed_candles()
        return self._candles_df["close"].iloc[-1]

    # For experimenting with websockets and ohlcv data
    def print_candles(self, sleep=0.0):
        last_timestamp = 0
        while True:
            data = self.ws_public.fetch(self._candle_topic_name)
            if data and data['timestamp'] > last_timestamp:
                # print(rapidjson.dumps(data, indent=2)); exit(0)

                # Candle confirmed, add to confirmed candles
                if data['confirm']:
                    if self._candles_df is None:
                        self._candles_df = pd.DataFrame.from_records([data])
                    else:
                        self._candles_df = self._candles_df.append([data], ignore_index=True)
                        # self.confirmed_candles = pd.concat([self.confirmed_candles, pd.DataFrame([data])], axis=0,
                        # ignore_index=True)
                if self._candles_df is not None:
                    print('\n\n\n\n')
                    print(self._candles_df.to_markdown())
                print()
                df = pd.DataFrame.from_records([data])
                print(df.to_markdown())
                last_timestamp = data['timestamp']
            time.sleep(sleep)
