"""
    Exchange class that implements operations done through the REST API
"""
import datetime as dt

import ccxt
import pandas as pd

import api_keys
import constants
import logger
from configuration import Configuration

logger = logger.init_custom_logger(__name__)


class ExchangeREST:
    name = None
    use_testnet = False  # Boolean True/False.

    def __init__(self):
        self.config = Configuration.get_config()

        # Unauthenticated
        # self.exchange = getattr(ccxt, self.config['exchange']['name'].lower())()

        # Authenticated
        exchange_id = self.config['exchange']['name'].lower()
        exchange_class = getattr(ccxt, exchange_id)
        self.exchange = exchange_class({
            'apiKey': api_keys.BYBIT_API_KEY,
            'secret': api_keys.BYBIT_API_SECRET,
            'enableRateLimit': True,
            # 'options': {
            #      'defaultType': 'future',  # 'spot', 'future', 'margin', 'delivery'
            # },
        })

        self.name = self.exchange.name

        # Testnet/Mainnet
        if self.config['exchange']['testnet']:
            self.use_testnet = True
            # Testnet
            self.exchange.set_sandbox_mode(True)
            self.name += '-Testnet'
        else:
            # Mainnet
            self.exchange.set_sandbox_mode(False)
        # Market type
        if self.config['exchange']['market_type'] == 'perpetual futures':
            self.exchange.options['defaultType'] = 'future'
        else:
            msg = f"Unsupported market type [{self.config['exchange']['market_type']}]."
            logger.error(msg)
            raise Exception(msg)

        # number in milliseconds, default 10000
        self.exchange.timeout = int(self.config['exchange']['rest']['timeout'])
        self.exchange.load_markets()

    def get_candle_data(self, pair, from_time, to_time, interval, include_prior=0, verbose=False):
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
            start_time = self.adjust_from_time(from_time, interval, include_prior)

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
            logger.error(msg)
            raise Exception(msg)

    def validate_pair(self, pair):
        market = self.exchange.market(pair)
        if market is None:
            msg = f'\nInvalid [{pair}] for exchange {self.name}.'
            logger .error(msg)
            raise Exception(msg)

    def get_maker_fee(self, pair):
        market = self.exchange.market(pair)
        return market['maker']

    def get_taker_fee(self, pair):
        market = self.exchange.market(pair)
        return market['taker']

    # Adjust from_time to include prior X entries for that interval for ema200
    @staticmethod
    def adjust_from_time(from_time, interval, include_prior):
        if interval not in constants.REST_VALID_INTERVALS:
            msg = f'Invalid interval value: {interval}'
            logger.error(msg)
            raise Exception(msg)

        delta = include_prior - 1
        if 'm' in interval:
            interval = interval.replace('m', '')
            from_time = from_time - dt.timedelta(minutes=int(interval) * delta)
        elif 'h' in interval:
            interval = interval.replace('h', '')
            from_time = from_time - dt.timedelta(hours=int(interval) * delta)
        elif 'd' in interval:
            interval = interval.replace('d', '')
            from_time = from_time - dt.timedelta(days=delta)
        elif 'w' in interval:
            interval = interval.replace('w', '')
            from_time = from_time - dt.timedelta(weeks=delta)
        return from_time
