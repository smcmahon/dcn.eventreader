import calendar
from datetime import date
from datetime import timedelta

from Acquisition import aq_get, aq_base
from zope.i18nmessageid import MessageFactory
from zope.interface import implements, Interface
from zope.component import getMultiAdapter

from plone.memoize.instance import memoize

from Products.Five import BrowserView
from Products.CMFCore.utils import getToolByName

import param_utils
from dbaccess import IEventDatabaseProvider
from dbaccess import decodeString
from dbaccess import decodeStrings

import caldate

# from dcn.eventreader import eventreaderMessageFactory as _
PLMF = MessageFactory('plonelocales')


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

    def eventDayList(max=0):
        """ return upcoming events as list of day lists """

    def getParams():
        """ return params """

    def myUrl():
        """
            Assemble a URL that will reproduce the
            current calendar
        """

    def monthUrl():
        """ url for month-mode calendar """

    def weekUrl():
        """ url for week-mode calendar """

    def dayUrl():
        """ url for day-mode calendar """

    def nextUrl():
        """ url for next calendar """

    def todayUrl():
        """ url to get today's calendar """

    def prevUrl():
        """ url for previous calendar """

    def getMode():
        """ return the current display mode: month, week, day """

    def getMonthYear():
        """ return the displayed month and year, suitable for presentation """

    def getFullDate():
        """ return the full date of the current display, suitable for presentation """

    def getCats():
        """ return a list of categories in alpha order unless suppressed """

    def getDisplayCats():
        """ returns a list of categories for display """
    def allCatsUrl():
        """ url with no gcid """

    def allCatsCurrent():
        """ returns true if there's no gcid in the params """

    def showEventUrl():
        """ base url to display individual events """

    def useAcronyms():
        """ should we display acronyms? """

    def setParam(self, **kwa):
        """ set params directly, typically from a template """


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
        self.database = IEventDatabaseProvider(context)
        self.portal_calendar = getToolByName(context, 'portal_calendar')
        self.portal_state = getMultiAdapter((self.context, self.request), name=u'plone_portal_state')
        self.navigation_root = self.portal_state.navigation_root()
        # get db_org_id from the nav root or set to 0
        self.db_org_id = getattr(aq_base(self.navigation_root), 'dbOrgId', 0)
        # get dbOrgList from anywhere in aq chain
        self.db_org_list = param_utils.strToIntList(
            aq_get(self.navigation_root, 'dbOrgList', '')
            )
        if not self.db_org_list and self.db_org_id:
            self.db_org_list = [self.db_org_id]
        self.context_state = getMultiAdapter((self.context, self.request), name=u'plone_context_state')
        self.today = date.today()

        # get params from request
        vals = param_utils.getQueryParams(request)
        # get params from nav root
        svals = param_utils.getSiteParams(self.navigation_root)
        self.site_params = svals
        # consolidate with site params winning collisions
        param_utils.consolidateParams(vals, svals)

        # If no org set, always show public, community
        if not (self.db_org_list or vals.get('org')):
            vals['public'] = 'y'
            vals['common'] = 'y'
            # so they don't show up on URLs:
            self.site_params['public'] = 'y'
            self.site_params['common'] = 'y'

        self.params = vals

    @memoize
    def getOrgData(self):
        """
        Returns organization's data as a dict
        """

        return self.database.getOrgData(self.db_org_id)

    def eventsByDateRange(self, start, end):
        """
        Returns a sequence of Events with
        dates between start and end.
        Also, optionally, selects by several criteria
        """

        return self.database.eventsByDateRange(
            start, end, self.db_org_list, **self.params
            )

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
            recurs = result.get('recurs', 'daily')
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

    @memoize
    def getWeekdays(self):
        """Returns a list of Messages for the weekday names."""
        weekdays = list(calendar.day_name)
        weekdays.insert(0, weekdays.pop())
        return weekdays

    def getParams(self):
        """ get params """

        return self.params

    @memoize
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

    @memoize
    def eventList(self):
        """ get events in a simple list, based on params.
            list format [(date, eventdict),...] """

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
            elist.append([key, edict[key]])
        return elist

    def eventDayList(self, max=0):
        """ return upcoming events as list of day lists.
            Format is [[date, [eventdict,...]]...] """

        self.params['mode'] = 'upcoming'
        events = self.eventList()
        day = []
        rez = []
        last_date = date(1900, 1, 1)
        found = 0
        for e in events:
            sdate = e[0]
            if sdate != last_date:
                if day:
                    rez.append([last_date, day])
                    day = []
                last_date = sdate
            day += e[1]
            found += len(day)
            if found >= max:
                break
        if day:
            rez.append([last_date, day])
        return rez

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
        """ url for month-mode calendar """
        return self.myUrl(mode='month')

    def weekUrl(self):
        """ url for week-mode calendar """
        return self.myUrl(mode='week')

    def dayUrl(self):
        """ url for day-mode calendar """
        return self.myUrl(mode='day')

    def nextUrl(self):
        """ url for next calendar """
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
        """ url to get today's calendar """
        return self.myUrl(date=self.today)

    def prevUrl(self):
        """ url for previous calendar """
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

    def getCats(self, oid=0, include_all=True):
        """ return a list of categories in alpha order unless suppressed """

        current_gcid = self.params.get('gcid', -1)
        if include_all:
            res = [{
                'title': u'All',
                'url': self.allCatsUrl(),
                'current': current_gcid == -1
                }]
        else:
            res = []
        for item in self.database.getCats(oid=oid):
            res.append({
                'title': decodeString(item.title),
                'gcid': item.gcid,
                'url': self.myUrl(gcid=item.gcid),
                'current': item.gcid == current_gcid,
                })
        return res

    @memoize
    def getDisplayCats(self):
        """ return an appropriate list of cats for display """

        if self.params.get('nocat-display'):
            return []
        db_org_id = self.db_org_id
        if db_org_id == 0:
            return self.getCats(oid=0)
        cat_options = getattr(self.navigation_root, 'catOptions', [])
        if 'useOrgCats' in cat_options:
            return self.getCats(oid=db_org_id)
        if 'useMajorCats' in cat_options:
            return self.getCats(oid=0)
        return []

    def allCatsUrl(self):
        """ url with no gcid """
        return self.myUrl(gcid=None)

    def allCatsCurrent(self):
        """ returns true if there's no gcid in the params """
        return self.params.get('gcid', None) is None

    @memoize
    def showEventUrl(self):
        """ base url to display individual events """

        return "%s/showEvent?eid=" % self.portal_state.navigation_root_url()

    @memoize
    def useAcronyms(self):
        """ should we display acronyms? """

        return not (self.db_org_id or self.db_org_list) and self.getMode() != 'day'


    def setParam(self, **kwa):
        """ set params directly, typically from a template """

        for key, value in kwa.items():
            val = param_utils.sanitizeParam(key, value)
            if val is not None:
                self.params[key] = val
                # also set site_params so that the flag
                # won't show in the query params returned
                # by myURL(). This is based on the assumption
                # that this method is called from a template.
                self.site_params[key] = val

