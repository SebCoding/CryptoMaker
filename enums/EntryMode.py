from enum import Enum


class EntryMode(str, Enum):
    Maker = 'maker'
    Taker = 'taker'