import calendar
from datetime import date
from datetime import timedelta

from Acquisition import aq_get, aq_base
from zope.i18nmessageid import MessageFactory
from zope.interface import implements, Interface
from zope.component import getMultiAdapter
from Shared.DC.ZRDB.Results import Results

from Products.Five import BrowserView

from Products.CMFCore.utils import getToolByName

# from dcn.eventreader import eventreaderMessageFactory as _

import caldate

PLMF = MessageFactory('plonelocales')


cal_params = {
    'mode': set(['month', 'week', 'day', 'upcoming']),
    'date': 'date',
    'org': 'int_list',
    'gcid': 'int',
    'public': set(['y', 'n', 'b']),
    'common': set(['y', 'n', 'b']),
    'udf1': set(['y', 'n']),
    'udf2': set(['y', 'n']),
    'days': 'int',
}


class IEventQueryView(Interface):
    """
    EventQuery view interface
    """

    def getWeekdays():
        """Returns a list of Messages for the weekday names."""

    def eventMonth():
        """
            returns a sequence of weeks, each week being a sequence of days.
            If year/month is None, uses today
            with each day being a dict with keys:
                day - timedate date
                events - a sequence of events in startTime order
                today - True if day is today
            Each event is a dictionary of event attributes
        """

    def eventList(self):
        """ get events in a simple list, based on params """

    def getParams():
        """ return params """

    def myUrl():
        """
            Assemble a URL that will reproduce the
            current calendar
        """

    def monthUrl():
        """ url for the full month """

    def weekUrl():
        """ url for the week """

    def dayUrl():
        """ url for the day """

    def nextUrl():
        """ url for next month, week or day """

    def prevUrl():
        """ url for previous month, week or day """

    def eventUrl(self, eid):
        """ url to display event """


def cleanDate(adate):
    return adate.strftime('%Y-%m-%d')


def strToIntList(val):
    if type(val) == int:
        return [val]
    else:
        vlist = []
        for v in val.split(','):
            try:
                vlist.append(int(v))
            except ValueError:
                pass
        return vlist


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
        self.portal_state = getMultiAdapter((self.context, self.request), name=u'plone_portal_state')
        self.navigation_root = self.portal_state.navigation_root()
        # see if the nav root has a dbOrgId attribute. If it does, this
        # will override any org specified in request
        self.db_org_id = strToIntList(getattr(aq_base(self.navigation_root), 'dbOrgId', ''))
        self.context_state = getMultiAdapter((self.context, self.request), name=u'plone_context_state')
        self.today = date.today()

        # get params from request
        vals = self.getQueryParams()
        # get params from nav root
        svals = self.getSiteParams()
        self.site_params = svals
        # consolidate with site params winning collisions
        for key in svals:
            vals[key] = svals[key]
        self.params = vals

    def sql_quote(self, astring):
        return self.dbCal.sql_quote__(astring)

    def eventsByDateRange(self, start, end):
        """
        Returns a sequence of Events with
        dates between start and end.
        Also, optionally, selects by several criteria
        """

        kwa = self.params

        oid = self.db_org_id or kwa.get('org')
        if oid:
            oid_test = "AND e.oid in (%s)" % ','.join([str(int(i)) for i in oid])
        else:
            oid_test = ""

        public = kwa.get('public', 'b')
        if public != 'b':
            public_test = "AND e.public = %s" % self.sql_quote(public)
        else:
            public_test = ""

        common = kwa.get('common', 'b')
        if common != 'b':
            common_test = "AND e.community = %s" % self.sql_quote(common)
        else:
            common_test = ""

        udf1 = kwa.get('udf1')
        if udf1 is None:
            udf1_test = ""
        else:
            udf1_test = "AND e.udf1 = %s" % self.sql_quote(udf1)

        udf2 = kwa.get('udf2')
        if udf2 is None:
            udf2_test = ""
        else:
            udf2_test = "AND e.udf2 = %s" % self.sql_quote(udf2)

        gcid = kwa.get('gcid')
        if gcid is None:
            gcid_test = ""
            gcid_from = ""
        else:
            gcid_test = "AND EvCats.eid = ev.eid AND EvCats.gcid = %d" % gcid
            gcid_from = ", EvCats"

        query = """
            SELECT DISTINCT e.eid, e.title, e.description, e.startTime, e.endTime, e.location,
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

    def eventsByDay(self, start, end):
        """
        Returns a day-keyed dictionary of days between start and end with events.
        Each day in the sequence is returned as a event list sorted by startTime.
        Also, optionally, selects by several criteria
        """
        days = {}
        query = self.eventsByDateRange(start, end)
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

    def getEventsForMonthDates(self, month_dates):
        """
            Take a structured month list of week lists of days
            and fill it in with each day being a dict with keys:
                day - timedate date
                events - a sequence of events in startTime order
                today - True if day is today
            Each event is a dictionary of event attributes
        """

        today = self.today

        start = month_dates[0][0]
        end = month_dates[-1][-1]
        events = self.eventsByDay(start, end)

        emonth = []
        for week in month_dates:
            thisweek = []
            for day in week:
                thisweek.append({
                    'day': day.day,
                    'events': events.get(day, []),
                    'today': day == today
                    })
            emonth.append(thisweek)

        return emonth

    def getEventMonth(self, target):
        """
            returns a sequence of weeks, each week being a sequence of days;
            return is in getEventsForMonthDates format
        """

        cal = calendar.Calendar()
        cal.firstweekday = self.portal_calendar.getFirstWeekDay()
        month_dates = cal.monthdatescalendar(target.year, target.month)
        return self.getEventsForMonthDates(month_dates)

    def getEventWeek(self, target):
        """
            returns a sequence of weeks, each week being a sequence of days;
            return is in getEventsForMonthDates format
        """

        month_dates = [caldate.weekDatesCalendar(target)]
        return self.getEventsForMonthDates(month_dates)

    def getEventDay(self, target):
        """
            returns a sequence of weeks, each week being a sequence of days;
            return is in getEventsForMonthDates format
        """

        month_dates = [[target]]
        return self.getEventsForMonthDates(month_dates)

    def getWeekdays(self):
        """Returns a list of Messages for the weekday names."""
        weekdays = list(calendar.day_name)
        weekdays.insert(0, weekdays.pop())
        return weekdays
        # # list of ordered weekdays as numbers
        # for day in self.portal_calendar.getDayNumbers():
        #     weekdays.append(PLMF(self._ts.day_msgid(day, format='s'),
        #                          default=self._ts.weekday_english(day)))

        # return weekdays

    def sanitizeParamDict(self, params):
        """ make sure everything in the params dict is expected and
            in acceptable format."""

        for key in params.keys():
            val = params.get(key)
            if val is not None:
                constraint = cal_params.get(key)
                if constraint is not None:
                    if constraint == 'date':
                        try:
                            val = caldate.parseDateString(val)
                        except (TypeError, ValueError):
                            val = None
                    elif constraint == 'int':
                        try:
                            val = int(val)
                        except ValueError:
                            val = None
                    elif constraint == 'int_list':
                        val = strToIntList(val)
                    elif type(constraint) == set:
                        val = val.strip().lower()
                        if val not in constraint:
                            val = None
                    else:
                        val = None
                else:
                    val = None

                if val is None:
                    del params[key]
                else:
                    params[key] = val
        return params

    def getQueryParams(self):
        """ Examine the HTTP query and pick up params for cal display """

        params = {}
        form = self.request.form
        for key in cal_params:
            val = form.get(key, form.get('%s-calendar' % key, None))
            if val is not None:
                params[key] = val

        return self.sanitizeParamDict(params)

    def getSiteParams(self):
        """ examine the attributes of the site nav root for params
            for cal """

        # get the nav root
        ps = getMultiAdapter((self.context, self.request), name=u'plone_portal_state')
        nr = aq_base(ps.navigation_root())

        params = {}
        for key in cal_params.keys():
            val = getattr(nr, key, None)
            if val is not None:
                params.setdefault(key, val)

        return self.sanitizeParamDict(params)

    def getParams(self):
        """ get params """

        return self.params

    def eventMonth(self):
        """ get events in a month data structure, based on params """

        target = self.params.get('date', self.today)
        mode = self.params.get('mode', 'month')
        if mode == 'day':
            return self.getEventDay(target)
        elif mode == 'week':
            return self.getEventWeek(target)
        else:
            return self.getEventMonth(target)

    def eventList(self):
        """ get events in a simple list, based on params """

        target = self.params.get('date', self.today)
        mode = self.params.get('mode', 'month')
        if mode == 'day':
            edict = self.eventsByDay(target, target)
        elif mode == 'week':
            edict = self.eventsByDay(caldate.startOfWeek(target), caldate.endOfWeek(target))
        elif mode == 'upcoming':
            end = self.today + timedelta(self.params.get('days', 30))
            edict = self.eventsByDay(self.today, end)
        else:
            edict = self.eventsByDay(caldate.startOfMonth(target), caldate.endOfMonth(target))
        keys = edict.keys()
        keys.sort()
        elist = []
        for key in keys:
            elist += edict[key]
        return elist

    def myUrl(self, **overrides):
        """
            Assemble a URL that will reproduce the
            current calendar with optional overrides.
            override with a None value to remove an
            item.
        """

        params = self.params.copy()
        # consolidate overrides
        for s in overrides:
            oval = overrides[s]
            if oval is None:
                # delete it from params
                try:
                    del params[s]
                except KeyError:
                    pass
            else:
                params[s] = overrides[s]
        # remove keys present in site params
        for s in params.keys():
            if s in self.site_params:
                del params[s]

        # generate query params when the setting isn't the default
        val = params.get('date')
        if val and val != self.today:
            s = "date=%s;" % val.isoformat()
        else:
            s = ''
        val = params.get('mode', 'month')
        if val != 'month':
            s = "%smode=%s;" % (s, val)
        val = params.get('gcid')
        if val:
            s = "%sgcid=%s;" % (s, val)
        val = params.get('public', 'b')
        if val != 'b':
            s = "%spublic=%s;" % (s, val)
        val = params.get('common', 'b')
        if val != 'b':
            s = "%scommon=%s;" % (s, val)
        val = params.get('udf1', 'n')
        if val != 'n':
            s = "%sudf1=%s;" % (s, val)
        val = params.get('udf2', 'n')
        if val != 'n':
            s = "%sudf2=%s;" % (s, val)
        val = params.get('org', self.db_org_id)
        if val != self.db_org_id:
            s = "%sorg=%s;" % (s, ','.join([str(int(i)) for i in val]))

        if s:
            s = "?%s" % s
        return "%s%s" % (self.context_state.current_base_url(), s)

    def monthUrl(self):
        return self.myUrl(mode='month')

    def weekUrl(self):
        return self.myUrl(mode='week')

    def dayUrl(self):
        return self.myUrl(mode='day')

    def nextUrl(self):
        mode = self.params.get('mode', 'month')
        cdate = self.params.get('date', date.today())
        if mode == 'day':
            cdate += timedelta(1)
        elif mode == 'week':
            cdate += timedelta(7)
        elif mode == 'month':
            cdate = caldate.startOfNextMonth(cdate)
        return self.myUrl(date=cdate)

    def todayUrl(self):
        return self.myUrl(date=self.today)

    def prevUrl(self):
        mode = self.params.get('mode', 'month')
        cdate = self.params.get('date', self.today)
        if mode == 'day':
            cdate -= timedelta(1)
        elif mode == 'week':
            cdate -= timedelta(7)
        elif mode == 'month':
            cdate = caldate.startOfMonth(cdate) - timedelta(1)
        return self.myUrl(date=cdate)

    def getMode(self):
        """ return the current display mode: month, week, day """

        return self.params.get('mode', 'month')

    def getMonthYear(self):
        """ return the displayed month and year, suitable for presentation """

        return self.params.get('date', self.today).strftime("%B, %Y")

    def getFullDate(self):
        """ return the full date of the current display, suitable for presentation """

        return self.params.get('date', self.today).strftime("%B %d, %Y").replace(' 0', ' ')

    def getCats(self):
        """ return a list of categories in alpha order """

        # who for? Use 0 for global categories
        oid = self.db_org_id or self.params.get('org', [0])
        if len(oid) > 1:
            oid = 0
        else:
            oid = oid[0]

        query = """
            select title, gcid from GlobalCategories
            where oid = %i
            order by title
        """ % oid

        current_gcid = self.params.get('gcid', -1)
        res = []
        for item in Results(self.reader.query(query)):
            res.append({
                'title': item.title,
                'url': self.myUrl(gcid=item.gcid),
                'current': item.gcid == current_gcid,
                })
        return res

    def allCatsUrl(self):
        """ url with no gcid """
        return self.myUrl(gcid=None)

    def showEventUrl(self):
        """ base url to display individual events """

        return "%s/showEvent?eid=" % self.portal_state.navigation_root_url()
