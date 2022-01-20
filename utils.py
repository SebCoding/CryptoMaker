import constants
import datetime as dt
from logging_.Logger import Logger

_logger = Logger.get_module_logger(__name__)


def convert_interval_to_sec(interval):
    if interval not in constants.VALID_INTERVALS:
        msg = f'Invalid interval value: {interval}'
        _logger.error(msg)
        raise Exception(msg)
    nb_secs = 0
    if 'm' in interval:
        interval = int(interval.replace('m', ''))
        nb_secs = (interval * 60)
    elif 'h' in interval:
        interval = int(interval.replace('h', ''))
        nb_secs = (interval * 3600)  # 60*60 = 3600
    elif 'd' in interval:
        interval = int(interval.replace('d', ''))
        nb_secs = (interval * 86400)  # 24*60*60 = 86400
    elif 'w' in interval:
        interval = int(interval.replace('w', ''))
        nb_secs = (interval * 604800)  # 7*24*60*60 = 604800
    return nb_secs


# Offsets the 'from_time' backwards from 'nb_candles' in the specified timeframe (interval).
# The offset can backward or forward in time
# Assumes 'from_time' is in seconds
def adjust_from_time_timestamp(from_time, interval, nb_candles, backward=True):
    if interval not in constants.VALID_INTERVALS:
        msg = f'Invalid interval value: {interval}'
        _logger.error(msg)
        raise Exception(msg)
    if backward:
        nb_candles = nb_candles * -1
    if 'm' in interval:
        interval = int(interval.replace('m', ''))
        from_time += (nb_candles * interval * 60)
    elif 'h' in interval:
        interval = int(interval.replace('h', ''))
        from_time += (nb_candles * interval * 3600)  # 60*60 = 3600
    elif 'd' in interval:
        interval = int(interval.replace('d', ''))
        from_time += (nb_candles * interval * 86400)  # 24*60*60 = 86400
    elif 'w' in interval:
        interval = int(interval.replace('w', ''))
        from_time += (nb_candles * interval * 604800)  # 7*24*60*60 = 604800
    return from_time


# Adjust from_time to include prior X entries for that interval
# 'from_time' must be a datetime object
def adjust_from_time_datetime(from_time, interval, include_prior):
    if interval not in constants.VALID_INTERVALS:
        msg = f'Invalid interval value: {interval}'
        _logger.error(msg)
        raise Exception(msg)

    delta = include_prior - 1
    if 'm' in interval:
        interval = interval.replace('m', '')
        from_time = from_time - dt.timedelta(minutes=int(interval) * delta)
    elif 'h' in interval:
        interval = interval.replace('h', '')
        from_time = from_time - dt.timedelta(hours=int(interval) * delta)
    elif 'd' in interval:
        from_time = from_time - dt.timedelta(days=delta)
    elif 'w' in interval:
        from_time = from_time - dt.timedelta(weeks=delta)
    return from_time


def seconds_to_human_readable(seconds):
    # Remove days and keep remainder in seconds
    seconds = seconds % (24 * 3600)
    hours = seconds // 3600
    seconds %= 3600
    minutes = seconds // 60
    seconds %= 60
    output = f"{int(hours)}h {int(minutes)}m {int(seconds)}s"
    for c in output:
        if c in ['0', ':', 'h', 'm', 's', ' ']:
            output = output.replace(c, '', 1)
        else:
            break
    if len(output) == 0:
        output = 'less than 1s'
    return output


