from enum import Enum


class TradeStatus(str, Enum):
    # Longs
    EnterLong = 'Enter Long'
    Long = 'Long'
    ExitLong = 'Exit Long'

    # Shorts
    EnterShort = 'Enter Short'
    Short = 'Short'
    ExitShort = 'Exit Short'

    # No trade
    NoTrade = 'No Trade'
