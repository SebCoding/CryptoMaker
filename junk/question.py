from pybit import WebSocket
endpoint_public = 'wss://stream.bybit.com/realtime_public'
subs = ["orderBookL2_25.BTCUSDT"]
ws = WebSocket(endpoint_public, subscriptions=subs)
while True:
        data = ws.fetch(subs[0])
        if data:
                print(data)