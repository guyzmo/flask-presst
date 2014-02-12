import datetime
from email.utils import parsedate_tz


class timezone(datetime.tzinfo):
    def __init__(self, utcoffset):
        self._utcoffset = utcoffset

    def utcoffset(self, dt):
        return self._utcoffset

    def dst(self):
        return datetime.timedelta(0)


def parsedate_to_datetime(data):
    # from email.utils.parsedate_to_datetime (introduced in Python 3.3)
    # backported to 2.7.5
    _ = parsedate_tz(data)
    dtuple = _[:-1]
    tz = _[-1]

    if tz is None:
        return datetime.datetime(*dtuple[:6])
    return datetime.datetime(*dtuple[:6],
            tzinfo=timezone(datetime.timedelta(seconds=tz)))