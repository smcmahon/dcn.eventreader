#!/usr/bin/env python
# encoding: utf-8
"""
caldate.py

Copyright (c) 2009 Stephen McMahon. Licensed under the GPL.

DocTests for caldate

    >>> start = datetime.date(2009, 4, 1)
    >>> start
    datetime.date(2009, 4, 1)

    >>> end = datetime.date(2009, 4, 30)
    >>> end
    datetime.date(2009, 4, 30)

    >>> daily(start, start, start)
    [datetime.date(2009, 4, 1)]

    >>> daily(start, end, end)
    [datetime.date(2009, 4, 30)]

    >>> len(daily(start, end, start))
    30

    >>> len(daily(start, end, datetime.date(2009, 4, 16)))
    15

    >>> target = datetime.date(2009, 4, 10)
    >>> weekly(start, end, target)
    [datetime.date(2009, 4, 10), datetime.date(2009, 4, 17), datetime.date(2009, 4, 24)]

    >>> target = datetime.date(2009, 3, 10)
    >>> weekly(start, end, target)
    [datetime.date(2009, 4, 7), datetime.date(2009, 4, 14), datetime.date(2009, 4, 21), datetime.date(2009, 4, 28)]

    >>> target = datetime.date(2009, 4, 1)
    >>> weekly(start, end, target)
    [datetime.date(2009, 4, 1), datetime.date(2009, 4, 8), datetime.date(2009, 4, 15), datetime.date(2009, 4, 22), datetime.date(2009, 4, 29)]

    >>> target = datetime.date(2009, 4, 30)
    >>> weekly(start, end, target)
    [datetime.date(2009, 4, 30)]

    >>> weekly(start, end, start - aday)
    [datetime.date(2009, 4, 7), datetime.date(2009, 4, 14), datetime.date(2009, 4, 21), datetime.date(2009, 4, 28)]

    >>> weekly(start, end, start + aday)
    [datetime.date(2009, 4, 2), datetime.date(2009, 4, 9), datetime.date(2009, 4, 16), datetime.date(2009, 4, 23), datetime.date(2009, 4, 30)]

    >>> [d.weekday() for d in weekly(datetime.date(2012, 6, 20), datetime.date(2012, 7, 31), datetime.date(2012, 6, 20))]
    [2, 2, 2, 2, 2, 2]

    >>> target = datetime.date(2009, 5, 1)
    >>> weekly(start, end, target)
    []

    >>> weekly(target, target, target)
    [datetime.date(2009, 5, 1)]

    >>> start = datetime.date(2009, 5, 1)
    >>> end = datetime.date(2009, 5, 31)

    >>> target = datetime.date(2009, 5, 1)
    >>> biweekly(start, end, target)
    [datetime.date(2009, 5, 1), datetime.date(2009, 5, 15), datetime.date(2009, 5, 29)]

    >>> target = datetime.date(2009, 4, 30)
    >>> biweekly(start, end, target)
    [datetime.date(2009, 5, 14), datetime.date(2009, 5, 28)]

    >>> target = datetime.date(2009, 5, 2)
    >>> biweekly(start, end, target)
    [datetime.date(2009, 5, 2), datetime.date(2009, 5, 16), datetime.date(2009, 5, 30)]

    >>> target = datetime.date(2009, 6, 1)
    >>> biweekly(start, end, target)
    []

    >>> monthly(start, end, datetime.date(2009, 4, 1))
    [datetime.date(2009, 5, 6)]

    >>> datetime.date(2009, 4, 1).weekday() == monthly(start, end, datetime.date(2009, 4, 1))[0].weekday()
    True

    >>> monthly(start, end, datetime.date(2009, 4, 15))
    [datetime.date(2009, 5, 20)]

    >>> datetime.date(2009, 4, 15).weekday() == monthly(start, end, datetime.date(2009, 5, 20))[0].weekday()
    True

    >>> monthly(start, end, datetime.date(2009, 4, 30))
    []

    >>> monthly(start, datetime.date(2009, 6, 30), datetime.date(2009, 4, 30))
    []

    >>> monthly(start, datetime.date(2009, 7, 31), datetime.date(2009, 4, 30))
    [datetime.date(2009, 7, 30)]

    >>> monthly(start, datetime.date(2009, 7, 31), datetime.date(2009, 5, 12))
    [datetime.date(2009, 5, 12), datetime.date(2009, 6, 9), datetime.date(2009, 7, 14)]

    >>> startOfWeek(datetime.date(2012, 8, 21))
    datetime.date(2012, 8, 19)

    >>> endOfWeek(datetime.date(2012, 8, 21))
    datetime.date(2012, 8, 25)

    >>> weekDatesCalendar(datetime.date(2012, 8, 21))
    [datetime.date(2012, 8, 19), datetime.date(2012, 8, 20), datetime.date(2012, 8, 21), datetime.date(2012, 8, 22), datetime.date(2012, 8, 23), datetime.date(2012, 8, 24), datetime.date(2012, 8, 25)]

"""
import re
import datetime
from datetime import date, timedelta

# date splitting pattern
spat = re.compile(r"[/-]")

aday = timedelta(1)


def parseDateString(datestring):
    return date(*[int(s) for s in spat.split(datestring)])


def hardRecurr(start, end, target, offset):
    """
      For fixed-day count recurrance
    """

    tdoffset = timedelta(offset)
    res = []
    if target <= end:
        if start < target:
            start = target
        day = start + timedelta(((target - start).days + offset) % offset)
        while day <= end:
            res.append(day)
            day += tdoffset
    return res


def daily(start, end, target):
    adate = max(start, target)
    res = []
    while adate <= end:
        res.append(adate)
        adate += aday
    return res


def weekly(start, end, target):
    """
      Find the day of week for target,
      return dates for all the same weekdays
      inclusively between start and end.

    """
    return hardRecurr(start, end, target, 7)


def biweekly(start, end, target):
    """
      Alternate weeks
    """

    return hardRecurr(start, end, target, 14)


def startOfMonth(adate):
    return adate.replace(day=1)


def startOfNextMonth(adate):
    if adate.month == 12:
        return date(adate.year + 1, 1, 1)
    else:
        return date(adate.year, adate.month + 1, 1)


def endOfMonth(adate):
    return startOfNextMonth(adate) - aday


def monthly(start, end, target):
    """
      Follow an xth weekday in month pattern
    """

    week = target.day / 7

    if target > start:
        monthStart = startOfMonth(target)
    else:
        monthStart = startOfMonth(start)

    res = []
    while monthStart <= end:
        tdow = target.weekday()
        msdow = monthStart.weekday()
        if tdow >= msdow:
            ofs = tdow - msdow
        else:
            ofs = 7 - (msdow - tdow)
        date = monthStart + timedelta(week * 7 + ofs)
        if monthStart <= date <= endOfMonth(monthStart):
            res.append(date)
        monthStart = startOfNextMonth(monthStart)
    return res


def startOfWeek(target):
    """ return date for Sunday in target's week """

    wday = target.isoweekday() % 7
    return target - timedelta(wday)


def endOfWeek(target):
    """ return date for Saturday in target's week """

    wday = target.isoweekday() % 7
    return target + timedelta(6 - wday)


def weekDatesCalendar(target):
    """ returns a list of week dates for target's week """

    sunday = startOfWeek(target)
    return [sunday + timedelta(i) for i in range(0, 7)]

if __name__ == "__main__":
    import doctest
    doctest.testmod()
