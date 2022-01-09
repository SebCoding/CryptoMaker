from enum import Enum


class TradeTypes(str, Enum):
    Long = 'Long'
    Short = 'Short'

    @classmethod
    def get_side(cls, trade_type):
        if trade_type == cls.Long:
            return 'Buy'
        elif trade_type == cls.Short:
            return 'Sell'
        else:
            return None



