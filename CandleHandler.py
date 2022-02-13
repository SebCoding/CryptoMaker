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
    # For example: every each 1000 new rows we delete the 1000 oldest rows
    DROP_OLD_ROWS_THRESHOLD = 1000

    def __init__(self, exchange, interval=None, sub_interval=None, signal_mode=None, minimum_candles_to_start=0):
        """
            If interval or signal_mode are provided they override the config file.
        """
        self._logger = Logger.get_module_logger(__name__)
        self._config = Configuration.get_config()
        self.pair = self._config['exchange']['pair']

        self.interval = interval if interval else self._config['trading']['interval']
        self.sub_interval = sub_interval if sub_interval else self._config['trading']['sub_interval']
        self.signal_mode = signal_mode if signal_mode else self._config['strategy']['signal_mode']

        if minimum_candles_to_start > 0:
            self.minimum_candles_to_start = minimum_candles_to_start
        else:
            self.minimum_candles_to_start = int(self._config['strategy']['minimum_candles_to_start'])

        self.sub_interval = self._config['trading']['sub_interval']
        self.minutes_in_interval = utils.convert_interval_to_sec(self.interval) / 60
        self._exchange = exchange
        self._candle_topic_name = \
            self._exchange.get_candle_topic(self.pair, self._exchange.interval_map[self.interval])
        self._candle_sub_topic_name = \
            self._exchange.get_candle_topic(self.pair, self._exchange.interval_map[self.sub_interval])
        self.ws_public = self._exchange.ws_public

    # Fetch 'minimum_candles_to_start' candles preceding 'to_time' (not including to_time)
    def get_historic_candles(self, to_time):
        self._logger.info(f'\nFetching {int(self.minimum_candles_to_start)} {self.interval} historical candles.')
        from_time = utils.adjust_from_time_timestamp(to_time, self.interval, self.minimum_candles_to_start)
        to_time -= 1  # subtract 1s because get_candle_data() includes candle to 'to_time'
        df = self._exchange.get_candle_data(self.pair, from_time, to_time, self.interval)
        return df

    def get_refreshed_candles(self):
        if self.signal_mode == SignalMode.SubInterval:
            return self._get_refreshed_candles_sub_interval()
        else:
            return self._get_refreshed_candles()

    def _get_refreshed_candles(self):
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

                    self._last_candle_timestamp = candle['timestamp']
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

        return self._candles_df, data_changed

    def _get_refreshed_candles_sub_interval(self):
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

            In the "sub_interval" signal_mode, confirmed interval candles get added to the dataframe.
            Confirmed sub_interval minute candles are used as the un-confirmed candles in the dataframe
        """
        data_changed = False

        # Read websockets
        candle_list = self.ws_public.fetch(self._candle_topic_name)
        candle_list_sub = self.ws_public.fetch(self._candle_sub_topic_name)

        # if candle_list or candle_list_sub:
        #     print('hey')
        #
        # if candle_list_sub:
        #     candle = candle_list_sub[0]
        #     print(rapidjson.dumps(candle, indent=2))

        # Remove unconfirmed candles
        if candle_list:
            candle_list = [e for e in candle_list if e['confirm'] is True]
        if candle_list_sub:
            candle_list_sub = [e for e in candle_list_sub if e['confirm'] is True]

        # We did not receive any confirmed "trading interval" candles, but we received confirmed sub_interval candles.
        # We add the confirmed sub_interval candles to the dataframe as unconfirmed "trading interval" candles.
        if not candle_list and candle_list_sub:
            candle_list = candle_list_sub
            # For sub_interval candles, only keep the latest candle
            candle_list = sorted(candle_list, key=lambda i: i['timestamp'], reverse=False)
            candle_list = [candle_list[-1]]
            candle_list[0]['confirm'] = False  # Mark the candle as unconfirmed

        # We've received confirmed "trading interval" candles (not sub_interval), we add them to the dataframe
        if candle_list:
            for candle in candle_list:
                if candle['timestamp'] > self._last_candle_timestamp:
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
                        current_minute = arrow.get(int(candle['start'])).to('local').minute
                        offset = current_minute % self.minutes_in_interval
                        start = int(candle['start']) - (offset * 60)
                        self._candles_df = self.get_historic_candles(start)
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
                    self.validate_last_entry(to_append)

                    self._last_candle_timestamp = candle['timestamp']
                    data_changed = True

                    # Every DROP_OLD_ROWS_LIMIT new rows,
                    # drop the oldest DROP_OLD_ROWS_LIMIT rows
                    if len(self._candles_df) > self.minimum_candles_to_start + self.DROP_OLD_ROWS_THRESHOLD:
                        self._logger.info(f'Dropping oldest {self.DROP_OLD_ROWS_THRESHOLD} of candles dataframe.')
                        self._candles_df = self._candles_df.tail(self.DROP_OLD_ROWS_THRESHOLD).copy()
                        self._candles_df.reset_index(inplace=True)

                    #print('\n'+self._candles_df.tail(10).to_string())
        return self._candles_df, data_changed

    def validate_last_entry(self, to_append):
        """
            Confirm that the websocket did not skip any data

            For signal_mode in ['interval', 'realtime']:
              Current candle 'start' time must be equal to prior candle 'end' time

            For signal_mode = 'sub_interval':
              if last row is confirmed
                 Current candle 'start' time must be equal to prior candle 'end' time
              else
                 The time between Current candle 'start' time and to prior candle 'end' time
                 must be less or equal to the current interval being traded
        """
        valid = True
        msg = ''
        if self._candles_df is not None and len(self._candles_df) >= 2:
            start_timestamp = int(self._candles_df["start"].iloc[-1])
            # signal_mode = 'sub_interval'
            if self.signal_mode == SignalMode.SubInterval:
                prev_end = arrow.get(int(self._candles_df["end"].iloc[-2]))
                cur_start = arrow.get(int(self._candles_df["start"].iloc[-1]))
                cur_confirm = self._candles_df["confirm"].iloc[-1]
                if cur_confirm and cur_start != prev_end:
                    valid = False
                    msg = f'*******  cur_start[{self._candles_df["start_time"].iloc[-1]}] != ' \
                          f'prev_end[{self._candles_df["end_time"].iloc[-2]}]  *******\n'
                elif (cur_start - prev_end) >= dt.timedelta(minutes=(self.minutes_in_interval - 1)):
                    valid = False
                    msg = f'*******  diff(cur_start[{self._candles_df["start_time"].iloc[-1]}], ' \
                          f'prev_end[{self._candles_df["end_time"].iloc[-2]}]) >= ' \
                          f'{self.minutes_in_interval - 1}min *******\n'
            # signal_mode = 'interval' or 'realtime'
            elif self._candles_df["start"].iloc[-1] != self._candles_df["end"].iloc[-2]:
                valid = False
                msg = f'*******  cur_start[{self._candles_df["start_time"].iloc[-1]}] != ' \
                      f'prev_end[{self._candles_df["end_time"].iloc[-2]}]  *******\n'

            if not valid:
                # For 'sub_interval' mode adjust start_timestamp
                if self.signal_mode == SignalMode.SubInterval:
                    current_minute = arrow.get(start_timestamp).to('local').minute
                    offset = current_minute % self.minutes_in_interval
                    start_timestamp = start_timestamp - (offset * 60)

                msg += self._candles_df.tail(2).to_string() + '\n'
                self._logger.error(msg)
                # The dataframe is corrupted. Rebuild the dataframe from scratch
                self._logger.error(
                    'Recovering from missing candle data. rebuilding the dataframe from scratch.')
                self._candles_df = self.get_historic_candles(start_timestamp)
                self._candles_df = self._candles_df.append(to_append, ignore_index=True)
                self._logger.error('Candles dataframe has been rebuilt successfully.')

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
