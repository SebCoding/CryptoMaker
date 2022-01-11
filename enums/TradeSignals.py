from enum import Enum


class TradeSignals(str, Enum):
    # Longs
    EnterLong = 'EnterLong'
    Long = 'Long'
    ExitLong = 'ExitLong'

    # Shorts
    EnterShort = 'EnterShort'
    Short = 'Short'
    ExitShort = 'ExitShort'

    # No trade
    NoTrade = 'NoTrade'
