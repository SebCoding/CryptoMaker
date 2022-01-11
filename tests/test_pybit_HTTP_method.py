import logging

import pandas as pd
import rapidjson

import api_keys
from pybit import HTTP
import datetime as dt

session_auth = HTTP(
    endpoint='https://api-testnet.bybit.com',
    api_key=api_keys.TESTNET_BYBIT_API_KEY,
    api_secret=api_keys.TESTNET_BYBIT_API_SECRET,
    logging_level=logging.DEBUG
)

#############################################################################
# ALWAYS CHECK FOR THE data['ret_msg'] == 'OK' BEFORE TRYING TO READ RESULT
#############################################################################

# Balances
# balance = session_auth.get_wallet_balance()['result']['USDT']
# print(f'balance:\n{rapidjson.dumps(balance, indent=2)}')
# balance_df = pd.DataFrame([balance])
# print(balance_df.to_string())
# print()

# Positions
#positions = session_auth.my_position(symbol='BTCUSDT')['result']
# for x in positions:
#     print(f'Positions:\n{rapidjson.dumps(x, indent=2)}')
#print(f'Position:\n{rapidjson.dumps(positions[0], indent=2)}')
# position_df = pd.DataFrame(positions)
# print(position_df.to_string())
#print()

# Check time difference with Bybit server
# print(dt.datetime.now())
# server_time = session_auth.server_time()
# print(dt.datetime.fromtimestamp(float(server_time['time_now'])))
# print()

# Trade Records
# trade_records = session_auth.user_trade_records(symbol='BTCUSDT')['result']['data']
# print(rapidjson.dumps(trade_records, indent=2))
# df = pd.DataFrame(trade_records)
# df['datetime'] = df.trade_time.apply(lambda x: dt.datetime.fromtimestamp(x))
# print(df.to_string())
# print()

# Active Orders
orders = session_auth.get_active_order(symbol='BTCUSDT', order_status='New')['result']['data']
print(rapidjson.dumps(orders, indent=2))
df = pd.DataFrame(orders)
print(df.to_string())
print()






