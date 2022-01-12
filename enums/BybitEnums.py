"""
    https://bybit-exchange.github.io/docs/linear/#t-enums
    https://bybit-exchange.github.io/docs/inverse_futures/#t-enums
"""


class OrderSide:
    Buy = 'Buy'
    Sell = 'Sell'


class OrderType:
    Market = 'Market'
    Limit = 'Limit'


class TimeInForce:
    GTC = 'GoodTillCancel'
    IOC = 'ImmediateOrCancel'
    FOK = 'FillOrKill'
    PostOnly = 'PostOnly'


class TriggerPriceType:
    LastPrice = 'LastPrice'
    IndexPrice = 'IndexPrice'
    MarkPrice = 'MarkPrice'


class OrderStatus:
    """
        Created - order has been accepted by the system but not yet put through the matching engine
        Rejected - order has been triggered but failed to be placed (e.g. due to insufficient margin)
        New - order has been placed successfully
        PartiallyFilled
        Filled
        Cancelled
        PendingCancel - matching engine has received the cancelation request but it may not be canceled successfully
    """
    Created = 'Created'
    Rejected = 'Rejected'
    New = 'New'
    PartiallyFilled = 'PartiallyFilled'
    Filled = 'Filled'
    Cancelled = 'Cancelled'
    PendingCancel = 'PendingCancel'


class StopOrderType:
    TakeProfit = 'TakeProfit'
    StopLoss = 'StopLoss'
    TrailingStop = 'TrailingStop'
    Stop = 'Stop'


class ContractType:
    InversePerpetual = 'InversePerpetual'
    LinearPerpetual = 'LinearPerpetual'
    InverseFutures = 'InverseFutures'


class ExecType:
    Trade = 'Trade'
    AdlTrade = 'AdlTrade'
    Funding = 'Funding'
    BustTrade = 'BustTrade'
