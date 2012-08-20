import calendar
from datetime import date, timedelta

from Acquisition import aq_get
from zope.i18nmessageid import MessageFactory
from zope.interface import implements, Interface
from Shared.DC.ZRDB.Results import Results

from Products.Five import BrowserView

from Products.CMFCore.utils import getToolByName

# from dcn.eventreader import eventreaderMessageFactory as _

import caldate

PLMF = MessageFactory('plonelocales')


class IEventQueryView(Interface):
    """
    EventQuery view interface
    """

    def getWeekdays():
        """Returns a list of Messages for the weekday names."""

    def eventMonth(year=None, month=None, **kwa):
        """
            returns a sequence of weeks, each week being a sequence of days.
            If year/month is None, uses today
            with each day being a dict with keys:
                day - timedate date
                events - a sequence of events in startTime order
                today - True if day is today
            Each event is a dictionary of event attributes
        """


def cleanDate(adate):
    return adate.strftime('%Y-%m-%d')


class EventQueryView(BrowserView):
    """
    EventQuery browser view
    """
    implements(IEventQueryView)

    def __init__(self, context, request):
        self.context = context
        self.request = request
        self.dbCal = aq_get(context, 'dbCal')
        self.reader = self.dbCal()
        self.portal_calendar = getToolByName(context, 'portal_calendar')
        self._ts = getToolByName(self.context, 'translation_service')

    def sql_quote(self, astring):
        return self.dbCal.sql_quote__(astring)

    def eventsByDateRange(self,
      start,
      end,
      oid=None,
      gcid=None,
      public=None,
      common=None,
      udf1=None,
      udf2=None):
        """
        Returns a sequence of Events with
        dates between start and end.
        Also, optionally, selects by several criteria
        """

        if oid is None:
            oid_test = ""
        else:
            oid_test = "AND e.oid = %u" % oid

        if public is None:
            public_test = ""
        else:
            public_test = "AND e.public = %s" % self.sql_quote(public)

        if common is None:
            common_test = ""
        else:
            common_test = "AND e.community = %s" % self.sql_quote(common)

        if udf1 is None:
            udf1_test = ""
        else:
            udf1_test = "AND e.udf1 = %s" % self.sql_quote(udf1)

        if udf2 is None:
            udf2_test = ""
        else:
            udf2_test = "AND e.udf2 = %s" % self.sql_quote(udf2)

        if gcid is None:
            gcid_test = ""
            gcid_from = ""
        else:
            gcid_test = "AND EvCats.eid = ev.eid AND EvCats.gcid = %d" % gcid
            gcid_from = ", EvCats"

        query = """
            SELECT DISTINCT e.eid, e.title, e.description, e.startTime, e.endTime,
             o.acronym, o.name as orgname,
             DATE_FORMAT(ev.sdate, "%%Y-%%m-%%d") as start,
             DATE_FORMAT(ev.edate, "%%Y-%%m-%%d") as end,
             TIME_FORMAT(e.startTime, "%%l:%%i %%p") as begins,
             TIME_FORMAT(e.endTime, "%%l:%%i %%p") as ends,
             ev.recurs
             FROM EvDates ev, Events e, Orgs o %s
             WHERE
               (ev.sdate >= "%s") AND (ev.edate <= "%s")
               AND ev.eid = e.eid
               AND o.oid = e.oid
               %s
               %s %s %s %s %s
            ORDER BY ev.sdate, e.startTime, e.title
        """ % (gcid_from, cleanDate(start), cleanDate(end), oid_test, public_test, common_test, udf1_test, udf2_test, gcid_test)

        dicts = Results(self.reader.query(query)).dictionaries()

        # convert dates to DateTimes and all strings from Windows-1252 to Unicode
        for adict in dicts:
            for s in ('start', 'end'):
                adict[s] = caldate.parseDateString(adict[s])
            for s in ('begins', 'ends'):
                adict[s] = adict[s].replace(' ', '').lower()
            for key in adict.keys():
                val = adict[key]
                if type(val) == type(''):
                    adict[key] = adict[key].decode('Windows-1252', 'replace')

        return dicts

    def eventsByDay(self,
      start,
      end,
      oid=None,
      gcid=None,
      public=None,
      common=None,
      udf1=None,
      udf2=None):
        """
        Returns a day-keyed dictionary of days between start and end with events.
        Each day in the sequence is returned as a event list sorted by startTime.
        Also, optionally, selects by several criteria
        """
        days = {}
        query = self.eventsByDateRange(start, end, oid=oid, gcid=gcid, public=public, common=common, udf1=udf1, udf2=udf2)
        # get the dates, taking recurrence into account
        for result in query:
            recurs = getattr(result, 'recurs', 'daily')
            estart = result['start']
            ldate = min(end, result['end'])
            if recurs == 'weekly':
                dates = caldate.weekly(start, ldate, estart)
            elif recurs == 'biweekly':
                dates = caldate.biweekly(start, ldate, estart)
            elif recurs == 'monthly':
                dates = caldate.monthly(start, ldate, estart)
            else:  # daily
                dates = caldate.daily(start, ldate, estart)
            for d in dates:
                days.setdefault(d, []).append(result)

        return days

    def eventMonth(self, year=None, month=None, **kwa):
        """
            returns a sequence of weeks, each week being a sequence of days
            with each day being a dict with keys:
                day - timedate date
                events - a sequence of events in startTime order
                today - True if day is today
            Each event is a dictionary of event attributes
        """

        today = date.today()

        if year is None:
            year = today.year
        if month is None:
            month = today.month

        # find day of month for today, if it's in this month
        if (today.month == month) and (today.year == year):
            dom = today.day
        else:
            dom = 0

        cal = calendar.Calendar()
        cal.firstweekday = self.portal_calendar.getFirstWeekDay()
        month = cal.monthdatescalendar(year, month)

        start = month[0][0]
        end = month[-1][-1]
        events = self.eventsByDay(start, end, **kwa)

        emonth = []
        for week in month:
            thisweek = []
            for day in week:
                isday = day.day
                thisweek.append({
                    'day': isday,
                    'events': events.get(day, []),
                    'today': isday == dom
                    })
            emonth.append(thisweek)

        return emonth

    def getWeekdays(self):
        """Returns a list of Messages for the weekday names."""
        weekdays = []
        # list of ordered weekdays as numbers
        for day in self.portal_calendar.getDayNumbers():
            weekdays.append(PLMF(self._ts.day_msgid(day, format='s'),
                                 default=self._ts.weekday_english(day, format='a')))

        return weekdays
