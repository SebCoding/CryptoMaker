import pandas as pd
import time
import utils
from Configuration import Configuration
from Logger import Logger
import datetime as dt


class CandleHandler:
    _candles_df = None
    _last_candle_timestamp = 0

    def __init__(self, exchange):
        self._logger = Logger.get_module_logger(__name__)
        self._config = Configuration.get_config()
        self.pair = self._config['exchange']['pair']
        self.interval = self._config['strategy']['interval']
        self.minimum_candles_to_start = int(self._config['strategy']['minimum_candles_to_start'])
        self._exchange = exchange
        self._candle_topic_name = \
            self._exchange.get_candle_topic(self.pair, self._exchange.interval_map[self.interval])
        self.ws_public = self._exchange.ws_public

    # Fetch 'minimum_candles_to_start' candles preceding 'to_time' (not including to_time)
    def get_historic_candles(self, to_time):
        self._logger.info(f'Fetching {self.minimum_candles_to_start} prior historical candles.')
        from_time = utils.adjust_from_time_timestamp(to_time, self.interval, self.minimum_candles_to_start)
        to_time -= 1  # subtract 1s because get_candle_data() includes candle to 'to_time'
        df = self._exchange.get_candle_data(self.pair, from_time, to_time, self.interval)
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

    # Return 2 values: candles dataframe and True/False if the data has been modified since last call
    def get_refreshed_candles(self):
        data_changed = False
        data_list = self.ws_public.fetch(self._candle_topic_name)
        if data_list:
            for data in data_list:
                if data['timestamp'] > self._last_candle_timestamp:
                    # If we only trade on closed candles ignore data that is not confirmed
                    if self._config['trade']['trade_on_closed_candles_only'] and not data['confirm']:
                        return self._candles_df, False
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
                    if self._candles_df is None:
                        self._candles_df = self.get_historic_candles(int(data['start']))
                        self._candles_df = self._candles_df.append(to_append, ignore_index=True)
                        # print(self.confirmed_candles.tail(10).to_string()); exit(0)
                    # DataFrame contains at least 1 row
                    else:
                        if data['confirm']:
                            # Previous candle is confirmed we add a new row
                            if self._candles_df["confirm"].iloc[-1]:
                                self._candles_df = self._candles_df.append(to_append, ignore_index=True)

                            # Previous candle is not confirmed we update the last row
                            else:
                                # self.confirmed_candles.drop(self.confirmed_candles.tail(1).index, inplace=True)
                                # self.confirmed_candles = self.confirmed_candles.append(to_append, ignore_index=True)
                                self._candles_df = self._candles_df.iloc[:-1, :].append(to_append,
                                                                                        ignore_index=True)
                        # Current candle not confirmed and previous confirmed we add a new row
                        elif self._candles_df["confirm"].iloc[-1]:
                            self._candles_df = self._candles_df.append(to_append, ignore_index=True)

                        # Current candle not confirmed and previous not confirmed we update the last row
                        else:
                            # self.confirmed_candles.drop(self.confirmed_candles.tail(1).index, inplace=True)
                            # self.confirmed_candles = self.confirmed_candles.append(to_append, ignore_index=True)
                            self._candles_df = self._candles_df.iloc[:-1, :].append(to_append, ignore_index=True)

                    # Confirm that the websocket did not skip any data
                    # Current candle 'start' time must be equal to prior candle 'end' time
                    if len(self._candles_df) >= 2 and (self._candles_df["start"].iloc[-1] != self._candles_df["end"].iloc[-2]):
                        msg = f'*******  start[{self._candles_df["start"].iloc[-1]}] != prev_end[{self._candles_df["end"].iloc[-2]}]  *******\n'
                        msg += self._candles_df.tail(2).to_string() + '\n'
                        self._logger.error(msg)
                        # The dataframe is corrupted. Rebuild the dataframe from scratch
                        self._logger.error('Recovering from missing candle data. rebuilding the dataframe from scratch.')
                        self._candles_df = self.get_historic_candles(int(data['start']))
                        self._candles_df = self._candles_df.append(to_append, ignore_index=True)
                        self._logger.error('Candles dataframe has been rebuilt successfully.')

                    self._last_candle_timestamp = data['timestamp']
                    data_changed = True
        return self._candles_df, data_changed

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
