from enum import Enum


class TradeSignalsStates(str, Enum):
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
