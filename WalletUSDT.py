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

    def __init__(self, exchange_rest, exchange_ws):
        self.logger = Logger.get_module_logger(__name__)
        self._config = Configuration.get_config()
        self._exchange_rest = exchange_rest
        self._exchange_ws = exchange_ws
        self._stake_currency = self._config['exchange']['stake_currency']
        self._free = 0.0
        self._used = 0.0
        self._total = 0.0
        self.update_wallet()

    def update_wallet(self):
        data = self._exchange_ws.private_ws.fetch(self._wallet_topic_name)
        if data:
            self._free = data['available_balance']
            self._total = data['wallet_balance']
            self._used = self._total - self._free
        else:
            balances = self._exchange_rest.get_balances()[self._stake_currency]
            if balances:
                self._free = balances['free']
                self._used = balances['used']
                self._total = balances['total']

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
