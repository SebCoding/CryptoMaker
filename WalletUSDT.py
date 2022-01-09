"""
    Wallet for USDT perpetual futures only.
    Hybrid class using REST API to get balances until the first update
    of the websocket that only happens after the balance in the wallet changes.
    Using websockets private topic ['wallet']
"""
from Configuration import Configuration
from Logger import Logger


class WalletUSDT:
    _wallet_topic_name = 'wallet'

    def __init__(self, exchange, stake_currency):
        self.logger = Logger.get_module_logger(__name__)
        self._config = Configuration.get_config()
        self._exchange = exchange
        self._stake_currency = stake_currency
        self._free = 0.0
        self._used = 0.0
        self._total = 0.0
        self.update_wallet()

    def update_wallet(self):
        balances = self._exchange.get_balances()
        if balances:
            self._free = balances['available_balance']
            self._total = balances['wallet_balance']
            self._used = self._total - self._free

    def get_free(self):
        self.update_wallet()
        return self._free

    def get_used(self):
        self.update_wallet()
        return self._used

    def get_total(self):
        self.update_wallet()
        return self._total

    free = property(get_free)
    used = property(get_used)
    total = property(get_total)

    def to_string(self) -> str:
        result = f'{self._stake_currency} Wallet (free: {self._free}, used: {self._used}, total: {self._total})'
        return result
