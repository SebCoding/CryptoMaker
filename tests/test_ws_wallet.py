import api_keys
from pybit import WebSocket

subs = ["wallet"]
ws = WebSocket(
    "wss://stream-testnet.bybit.com/realtime_private",
    subscriptions=subs,
    api_key=api_keys.TESTNET_BYBIT_API_KEY,
    api_secret=api_keys.TESTNET_BYBIT_API_SECRET
)
while True:
    data = ws.fetch(subs[0])
    if data:
        print(data)