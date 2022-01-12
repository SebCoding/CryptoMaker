"""
    Exchange class that implements operations done through the REST API
"""
import datetime as dt
import logging

import ccxt
import pandas as pd

import api_keys
from logging_.Logger import Logger
import utils
from Configuration import Configuration
from exchange.retrier import retrier


class ExchangeREST:
    name = None
    use_testnet = False  # Boolean True/False.

    def __init__(self):
        self._logger = Logger.get_module_logger(__name__)
        self._config = Configuration.get_config()

        # Unauthenticated
        # self.exchange = getattr(ccxt, self.config['exchange']['name'].lower())()

        # Authenticated
        exchange_id = self._config['exchange']['name'].lower()
        exchange_class = getattr(ccxt, exchange_id)

        # Testnet
        if self._config['exchange']['testnet']:
            self.exchange = exchange_class({
                'apiKey': api_keys.TESTNET_BYBIT_API_KEY,
                'secret': api_keys.TESTNET_BYBIT_API_SECRET,
                'enableRateLimit': True,
                # 'options': {
                #      'defaultType': 'future',  # 'spot', 'future', 'margin', 'delivery'
                # },
            })
            self.name = self.exchange.name + '-Testnet'
            self.use_testnet = True
            self.exchange.set_sandbox_mode(True)
        # Mainnet
        else:
            self.exchange = exchange_class({
                'apiKey': api_keys.BYBIT_API_KEY,
                'secret': api_keys.BYBIT_API_SECRET,
                'enableRateLimit': True,
                # 'options': {
                #      'defaultType': 'future',  # 'spot', 'future', 'margin', 'delivery'
                # },
            })
            self.name = self.exchange.name
            self.exchange.set_sandbox_mode(False)

        # TODO: Figure out to deal with the logging_ of the ccxt module
        self.exchange._logger.setLevel(logging.INFO)

        # Market type
        if self._config['exchange']['market_type'] == 'perpetual futures':
            self.exchange.options['defaultType'] = 'linear'
        else:
            msg = f"Unsupported market type [{self._config['exchange']['market_type']}]."
            self._logger.error(msg)
            raise Exception(msg)

        # number in milliseconds, default 10000
        self.exchange.timeout = int(self._config['exchange']['rest']['timeout'])
        self.exchange.load_markets()

    # from_time, to_time must be timestamps
    def get_candle_data(self, pair, from_time, to_time, interval, verbose=False):
        from_time_str = dt.datetime.fromtimestamp(from_time).strftime('%Y-%m-%d')
        to_time_str = dt.datetime.fromtimestamp(to_time).strftime('%Y-%m-%d')

        if verbose:
            print(f'Fetching {pair} data from {self.name}. Interval [{interval}],',
                  f' From[{from_time_str}], To[{to_time_str}]')

        df_list = []
        start_time = from_time
        last_datetime_stamp = start_time * 1000
        to_time_stamp = to_time * 1000

        while last_datetime_stamp < to_time_stamp:
            result = self.exchange.fetch_ohlcv(
                symbol=pair,
                timeframe=interval,
                since=int(last_datetime_stamp)
            )

            tmp_df = pd.DataFrame(result, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])

            if tmp_df is None or (len(tmp_df.index) == 0):
                break
            df_list.append(tmp_df)
            last_datetime_stamp = float(max(tmp_df.timestamp) + 1000)  # Add (1000ms = 1 sec) to last data received

        if df_list is None or len(df_list) == 0:
            return None

        df = pd.concat(df_list)

        # Drop rows that have a timestamp greater than to_time
        df = df[df.timestamp <= int(to_time * 1000)]

        # Add columns
        df['pair'] = pair
        df['confirm'] = True
        df['datetime'] = [dt.datetime.fromtimestamp(x / 1000) for x in df.timestamp]
        df.rename(columns={'timestamp': 'start'}, inplace=True)
        df['start'] = df['start'] / 1000  # Convert open_time to seconds
        df['end'] = df['start'].map(lambda start: utils.adjust_from_time_timestamp(start, interval, 1, backward=False))
        df['timestamp'] = 0

        # Only keep relevant columns OHLCV and re-order
        df = df.loc[:, ['start', 'end', 'datetime', 'pair', 'open', 'high', 'low', 'close', 'volume', 'confirm', 'timestamp']]

        # Set proper data types
        df['start'] = df['start'].astype(int)
        df['end'] = df['end'].astype(int)
        df['open'] = df['open'].astype(float)
        df['high'] = df['high'].astype(float)
        df['low'] = df['low'].astype(float)
        df['close'] = df['close'].astype(float)
        df['volume'] = df['volume'].astype(float)
        df['timestamp'] = df['timestamp'].astype(int)
        return df

    def get_candle_data_old(self, pair, from_time, to_time, interval, include_prior=0, verbose=False):
        self.validate_pair(pair)
        self.validate_interval(interval)
        from_time_str = from_time.strftime('%Y-%m-%d')
        to_time_str = to_time.strftime('%Y-%m-%d')

        if verbose:
            print(f'Fetching {pair} data from {self.name}. Interval [{interval}],',
                  f' From[{from_time_str}], To[{to_time_str}]')

        df_list = []
        start_time = from_time

        # Adjust from_time for example to add 200 additional prior entries for example ema200
        if include_prior > 0:
            start_time = utils.adjust_from_time_datetime(from_time, interval, include_prior)

        last_datetime_stamp = start_time.timestamp() * 1000
        to_time_stamp = to_time.timestamp() * 1000

        while last_datetime_stamp < to_time_stamp:
            result = self.exchange.fetch_ohlcv(
                symbol=pair,
                timeframe=interval,
                since=int(last_datetime_stamp)
            )
            tmp_df = pd.DataFrame(result, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])

            # Add pair column
            tmp_df['pair'] = pair

            if tmp_df is None or (len(tmp_df.index) == 0):
                break

            tmp_df.index = [dt.datetime.fromtimestamp(x / 1000) for x in tmp_df.timestamp]
            df_list.append(tmp_df)
            last_datetime_stamp = float(max(tmp_df.timestamp) + 1000)  # Add (1000ms = 1 sec) to last data received

        if df_list is None or len(df_list) == 0:
            return None

        df = pd.concat(df_list)

        # Drop rows that have a timestamp greater than to_time
        df = df[df.timestamp <= int(to_time.timestamp() * 1000)]

        # Only keep relevant columns OHLCV and re-order
        df = df.loc[:, ['pair', 'open', 'high', 'low', 'close', 'volume']]

        # Set proper data types
        df['open'] = df['open'].astype(float)
        df['high'] = df['high'].astype(float)
        df['low'] = df['low'].astype(float)
        df['close'] = df['close'].astype(float)
        df['volume'] = df['volume'].astype(float)
        return df

    def validate_interval(self, interval):
        valid_intervals = list(self.exchange.timeframes.keys())
        valid_intervals_str = ' '
        valid_intervals_str = valid_intervals_str.join(valid_intervals)
        if interval not in valid_intervals:
            msg = f'\nInvalid Interval [{interval}]. Expected values: {valid_intervals_str}'
            self._logger.error(msg)
            raise Exception(msg)

    def validate_pair(self, pair):
        market = self.exchange.market(pair)
        if market is None:
            msg = f'\nInvalid [{pair}] for exchange {self.name}.'
            self._logger.error(msg)
            raise Exception(msg)

    def get_maker_fee(self, pair):
        market = self.exchange.market(pair)
        return market['maker']

    def get_taker_fee(self, pair):
        market = self.exchange.market(pair)
        return market['taker']

    @retrier
    def get_balances(self) -> dict:
        try:
            balances = self.exchange.fetch_balance()
            # Remove additional info from ccxt results
            balances.pop("info", None)
            balances.pop("free", None)
            balances.pop("total", None)
            balances.pop("used", None)
            return balances
        except (ccxt.NetworkError, ccxt.ExchangeError) as e:
            msg = f'Could not get balance due to {e.__class__.__name__}. Message: {e}'
            self._logger.exception(msg)
            raise Exception(msg) from e

    @retrier
    def get_positions(self, pair):
        try:
            positions = self.exchange.fetch_positions([pair])
            return positions
        except (ccxt.NetworkError, ccxt.ExchangeError) as e:
            msg = f'Could not get positions due to {e.__class__.__name__}. Message: {e}'
            self._logger.exception(msg)
            raise Exception(msg) from e

