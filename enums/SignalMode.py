class SignalMode:

    # Signals are generated only at the end of each candle of the selected trading interval
    Interval = 'interval'

    # Signals are generated only at the end of each sub_interval candle
    # SubInterval must always be < Interval
    SubInterval = 'sub_interval'

    # Signals are generated in realtime as they happen  (approx. every 1s)
    Realtime = 'realtime'
