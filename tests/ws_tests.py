"""
To see which endpoints and topics are available, check the Bybit API
documentation:
    https://bybit-exchange.github.io/docs/inverse/#t-websocket
    https://bybit-exchange.github.io/docs/linear/#t-websocket

Inverse Perpetual endpoints:
wss://stream-testnet.bybit.com/realtime
wss://stream.bybit.com/realtime

Perpetual endpoints:
wss://stream-testnet.bybit.com/realtime_public
wss://stream-testnet.bybit.com/realtime_private
wss://stream.bybit.com/realtime_public or wss://stream.bytick.com/realtime_public
wss://stream.bybit.com/realtime_private or wss://stream.bytick.com/realtime_private

Spot endpoints:
wss://stream-testnet.bybit.com/spot/quote/ws/v1
wss://stream-testnet.bybit.com/spot/quote/ws/v2
wss://stream-testnet.bybit.com/spot/ws
wss://stream.bybit.com/spot/quote/ws/v1
wss://stream.bybit.com/spot/quote/ws/v2
wss://stream.bybit.com/spot/ws

Futures Public Topics:
orderBookL2_25
orderBookL2-200
trade
insurance
instrument_info
klineV2

Futures Private Topics:
position
execution
order
stop_order
wallet

Spot Topics:
Subscribing to spot topics uses the JSON format to pass the topic name and
filters, as opposed to futures WS where the topic and filters are pass in a
single string. So, it's recommended to pass a JSON or python dict in your
subscriptions, which also be used to fetch the topic's updates. Examples can
be found in the code panel here: https://bybit-exchange.github.io/docs/spot/#t-publictopics

However, as private spot topics do not require a subscription, the following
strings can be used to fetch data:
outboundAccountInfo
executionReport
ticketInfo

"""
from pybit import WebSocket
import logging
import time
import pandas as pd

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')



# USDT Perpetual
endpoint_public = 'wss://stream.bybit.com/realtime_public'


# Inverse Perpetual
# endpoint_public = "wss://stream.bybit.com/realtime"
# subs = ["klineV2.1.BTCUSD"]

subs = ["orderBookL2_25.BTCUSDT", "candle.1.BTCUSDT"]
ws = WebSocket(endpoint_public, subscriptions=subs)

last_timestamp = 0
i = 0
top = 4

try:
    while True:
        data = ws.fetch(subs[0])
        if data:
            i += 1
            print(f'Orderbook Top {top}')
            #print(f'data: {data}')
            df = pd.DataFrame(data)
            df.set_index('price', inplace=True)
            df.index.astype(float)
            #df['price'] = df['price'].astype(float)
            # df.set_index(['side', 'price'], inplace=True)
            # print(df.to_string())


            sell_df = df.loc[df['side'] == 'Sell'].sort_values('price', ascending=False).tail(top)
            print(sell_df.to_string())
            buy_df = df.loc[df['side'] == 'Buy'].sort_values('price', ascending=False).head(top)
            print(buy_df.to_string())

            spread = float(sell_df.index[-1]) - float(buy_df.index[0])
            print(f'Spread = {spread}\n')
            time.sleep(0.02) # Orderbook: 20ms
            # exit(1)
        time.sleep(0.02)  # Orderbook 20ms

except KeyboardInterrupt as e:
    print(f'Caught KeyboardInterrupt exiting peacefully')
    exit(1)