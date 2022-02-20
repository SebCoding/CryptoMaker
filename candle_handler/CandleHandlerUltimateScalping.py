import time

import arrow

from CandleHandler import CandleHandler
from enums.SignalMode import SignalMode
import datetime as dt


class CandleHandlerUltimateScalping(CandleHandler):
    """
        We need to override the CandleHandler base class for the UltimateScalper strategy to be able to work in
        sub_interval mode.

        For example, in the case where we would want to run the strategy in 3m interval with sub_interval 1m.
        In this case, we have 2 separate parts of the code reading the 1m socket and interfering
        with each other (once the websocket is read, the data is no longer there to be read).

        In this example, the CandleHandler needs the 1m websocket to build the dataframe in sub_interval properly and
        the strategy itself also needs a separate 1m dataframe to calculate the MACD Histogram in the 1m lower
        timeframe.
    """
    _candles_df_1m = None
    _last_candle_timestamp_1m = 1

    def __init__(self, exchange, interval=None, sub_interval=None, signal_mode=None, minimum_candles_to_start=0):
        super().__init__(exchange, interval, sub_interval, signal_mode, minimum_candles_to_start)
        self._candle_1m_topic_name = self._exchange.get_candle_topic(self.pair, self._exchange.interval_map['1m'])
        self.candle_list_1m = None
        self.data_changed_1m = False

    def get_refreshed_candles(self):
        if self.signal_mode == SignalMode.SubInterval:
            df, data_changed = self._get_refreshed_candles_sub_interval()
            self._refresh_candles_1m()
        else:
            df, data_changed = self._get_refreshed_candles()
            if data_changed:
                # print(candles_df.tail(10).to_string() + '\n')
                while True:
                    self.candle_list_1m = self.ws_public.fetch(self._candle_1m_topic_name)
                    self._refresh_candles_1m()
                    if self._candles_df_1m is not None and self._candles_df_1m.iloc[-1]['end'] >= df.iloc[-1]['end']:
                        # print(candles_df_1m.tail(10).to_string() + '\n')
                        break
                    else:
                        time.sleep(1)  # wait 1s

        return df, data_changed, self._candles_df_1m

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

        # Keep a copy of what was read from the websocket for the _candles_1m_df dataframe
        if self.sub_interval == '1m':
            self.candle_list_1m = candle_list_sub
        else:
            self.candle_list_1m = self.ws_public.fetch(self._candle_1m_topic_name)

        # Remove unconfirmed candles
        if candle_list:
            candle_list = [e for e in candle_list if e['confirm'] is True]
        if candle_list_sub:
            candle_list_sub = [e for e in candle_list_sub if e['confirm'] is True]
        if self.candle_list_1m:
            self.candle_list_1m = [e for e in self.candle_list_1m if e['confirm'] is True]

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

                    # print('\n'+self._candles_df.tail(10).to_string())

        return self._candles_df, data_changed

    def _refresh_candles_1m(self):
        """
            Always call get_refreshed_candles() before get_refreshed_candles_1m() because get_refreshed_candles()
            because get_refreshed_candles() is teh one reading the websocket for both.
        """
        self.data_changed_1m = False
        candle_list = self.candle_list_1m
        if candle_list:
            for candle in candle_list:
                if candle['timestamp'] > self._last_candle_timestamp_1m:
                    # If we only trade on closed candles ignore data that is not confirmed
                    if self.signal_mode == SignalMode.Interval and not candle['confirm']:
                        # Assuming confirmed candles are placed before the unconfirmed candles in the list,
                        # we can exit on the 1st unconfirmed candle encountered
                        return self._candles_df_1m, False
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
                    if self._candles_df_1m is None:
                        self._candles_df_1m = self.get_historic_candles(int(candle['start']))
                        self._candles_df_1m = self._candles_df_1m.append(to_append, ignore_index=True)
                        # print(self._candles_df_1m.tail(10).to_string()); exit(0)
                    # DataFrame contains at least 1 row
                    else:
                        if candle['confirm']:
                            # Previous candle is confirmed we add a new row
                            if self._candles_df_1m["confirm"].iloc[-1]:
                                self._candles_df_1m = self._candles_df_1m.append(to_append, ignore_index=True)

                            # Previous candle is not confirmed we update the last row
                            else:
                                # self.confirmed_candles.drop(self.confirmed_candles.tail(1).index, inplace=True)
                                # self.confirmed_candles = self.confirmed_candles.append(to_append, ignore_index=True)
                                self._candles_df_1m = self._candles_df_1m.iloc[:-1, :].append(to_append,
                                                                                              ignore_index=True)
                        # Current candle not confirmed and previous candle is confirmed we add a new row
                        elif self._candles_df_1m["confirm"].iloc[-1]:
                            self._candles_df_1m = self._candles_df_1m.append(to_append, ignore_index=True)

                        # Current candle not confirmed and previous not confirmed we update the last row
                        else:
                            # self.confirmed_candles.drop(self.confirmed_candles.tail(1).index, inplace=True)
                            # self.confirmed_candles = self.confirmed_candles.append(to_append, ignore_index=True)
                            self._candles_df_1m = self._candles_df_1m.iloc[:-1, :].append(to_append, ignore_index=True)

                    # Confirm that the websocket did not skip any data
                    # Current candle 'start' time must be equal to prior candle 'end' time
                    self.validate_last_entry(to_append)

                    self._last_candle_timestamp_1m = candle['timestamp']
                    self.data_changed_1m = True

                    # Every DROP_OLD_ROWS_LIMIT new rows,
                    # drop the oldest DROP_OLD_ROWS_LIMIT rows
                    if len(self._candles_df_1m) > self.minimum_candles_to_start + self.DROP_OLD_ROWS_THRESHOLD:
                        self._logger.info(f'Dropping oldest {self.DROP_OLD_ROWS_THRESHOLD} of candles dataframe.')
                        self._candles_df_1m = self._candles_df_1m.tail(self.DROP_OLD_ROWS_THRESHOLD).copy()
                        self._candles_df_1m.reset_index(inplace=True)

                    self._candles_df_1m['open'] = self._candles_df_1m['open'].astype(float)
                    self._candles_df_1m['high'] = self._candles_df_1m['high'].astype(float)
                    self._candles_df_1m['low'] = self._candles_df_1m['low'].astype(float)
                    self._candles_df_1m['close'] = self._candles_df_1m['close'].astype(float)
                    self._candles_df_1m['volume'] = self._candles_df_1m['volume'].astype(float)

                    # print('\n' + self._candles_df_1m.tail(10).to_string())l
