import calendar
from datetime import date
from datetime import timedelta
import types

from Acquisition import aq_get, aq_base
from zope.i18nmessageid import MessageFactory
from zope.interface import implements, Interface
from zope.component import getMultiAdapter
from Shared.DC.ZRDB.Results import Results
from DateTime import DateTime

from plone.memoize.instance import memoize

from Products.Five import BrowserView

from Products.CMFCore.utils import getToolByName

import param_utils

# from dcn.eventreader import eventreaderMessageFactory as _

import caldate

PLMF = MessageFactory('plonelocales')


# decode string from win1252
def decodeString(val):
    return val.decode('Windows-1252', 'replace')


# decode a dict of strings from win1252
def decodeStrings(adict):
    for key in adict.keys():
        val = adict[key]
        if type(val) == type(''):
            adict[key] = decodeString(adict[key])


# encode string from win1252
def encodeString(val):
    return val.encode('Windows-1252', 'replace')


# decode a dict of strings from win1252
def encodeStrings(adict):
    for key in adict.keys():
        val = adict[key]
        if type(val) == type(u''):
            adict[key] = encodeString(adict[key])


class IEventQueryView(Interface):
    """
    EventQuery view interface
    """

    def getOrgData(self):
        """
        Returns organization's data as a dict
        """

    def updateOrgData(self, **kwa):
        """
            kwa should be a dict with keys matching orgs columns
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

    def getGlobalCats():
        """ returns a list of global categories """

    def getOrgCats():
        """ returns a list of this organization's categories """

    def getOrgCatList(self):
        """ returns a list of this organization's category titles-only """

    def allCatsUrl():
        """ url with no gcid """

    def allCatsCurrent():
        """ returns true if there's no gcid in the params """

    def showEventUrl():
        """ base url to display individual events """

    def dbOrgId():
        """ return dbOrgId as specified in nav root;
            returns 0 if not specified or was a list.
        """

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
        self.dbCal = aq_get(context, 'dbCal')
        self.reader = self.dbCal()
        self.portal_calendar = getToolByName(context, 'portal_calendar')
        self._ts = getToolByName(self.context, 'translation_service')
        self.portal_state = getMultiAdapter((self.context, self.request), name=u'plone_portal_state')
        self.navigation_root = self.portal_state.navigation_root()
        # see if the nav root has a dbOrgId attribute. If it does, this
        # will override any org specified in request
        self.db_org_id = param_utils.strToIntList(getattr(aq_base(self.navigation_root), 'dbOrgId', ''))
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
        if not (self.db_org_id or vals.get('org')):
            vals['public'] = 'y'
            vals['common'] = 'y'
            # so they don't show up on URLs:
            self.site_params['public'] = 'y'
            self.site_params['common'] = 'y'

        self.params = vals

    def sql_quote(self, astring):
        return self.dbCal.sql_quote__(astring)

    @memoize
    def getOrgData(self):
        """
        Returns organization's data as a dict
        """

        query = """
            SELECT * FROM Orgs WHERE oid = %s
        """ % (self.db_org_id[0])

        dicts = Results(self.reader.query(query)).dictionaries()
        if len(dicts) == 1:
            adict = dicts[0]
            decodeStrings(adict)
            return adict
        else:
            return None

    def updateOrgData(self, **kwa):
        """
            kwa should be a dict with keys matching orgs columns
        """

        assignments = []
        for key in kwa.keys():
            assert(key.replace('_', '').isalnum())
            val = kwa[key]
            if val is None:
                val = ''
            if type(val) == type(u''):
                val = encodeString(val)
            assignments.append("""%s=%s""" % (key, self.sql_quote(val)))
        query = """
            UPDATE Orgs
            SET %s
            WHERE oid=%s
        """ % (", ".join(assignments), int(self.dbOrgId()))
        self.reader.query(query)

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

        free = kwa.get('free', 'b')
        if free != 'b':
            free_test = "AND e.free = %s" % self.sql_quote(free)
        else:
            free_test = ""

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
            SELECT DISTINCT e.eid, e.title, e.description, e.startTime, e.endTime, e.location, e.eventUrl,
             o.acronym, o.name as orgname, o.url,
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
               %s %s %s %s %s %s
            ORDER BY ev.sdate, e.startTime, e.title
        """ % (gcid_from, cleanDate(start), cleanDate(end), oid_test, public_test, free_test, common_test, udf1_test, udf2_test, gcid_test)

        dicts = Results(self.reader.query(query)).dictionaries()

        # convert dates to DateTimes and all strings from Windows-1252 to Unicode
        for adict in dicts:
            for s in ('start', 'end'):
                adict[s] = caldate.parseDateString(adict[s])
            for s in ('begins', 'ends'):
                adict[s] = adict[s].replace(' ', '').lower()
            decodeStrings(adict)

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

    @memoize
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

        if self.params.get('nocat-display'):
            return []

        query = """
            select title, gcid from GlobalCategories
            where oid = %i
            order by title
        """ % oid

        current_gcid = self.params.get('gcid', -1)
        if include_all:
            res = [{
                'title': u'All',
                'url': self.allCatsUrl(),
                'current': current_gcid == -1
                }]
        else:
            res = []
        for item in Results(self.reader.query(query)):
            res.append({
                'title': decodeString(item.title),
                'gcid': item.gcid,
                'url': self.myUrl(gcid=item.gcid),
                'current': item.gcid == current_gcid,
                })
        return res

    @memoize
    def getGlobalCats(self):
        return self.getCats(oid=0)

    @memoize
    def getOrgCats(self):
        return self.getCats(oid=self.dbOrgId())

    def updateOrgCats(self, newlist):
        """
            We've received a new list of categories. We need
            to compare it with the existing list to see what's
            changed. Additions need to be added to the global
            category list; deletions need to be removed from
            that list and the evCats table that ties events to
            categories.
        """

        # Get the old list, put it into a dict keyed on titles
        db_org_id = self.dbOrgId()
        query = """
            select title, gcid from GlobalCategories
            where oid = %i
        """ % db_org_id
        old_cats = {}
        for item in Results(self.reader.query(query)):
            old_cats[decodeString(item.title)] = str(item.gcid)
        to_add = []
        for cat in newlist:
            if cat in old_cats:
                del old_cats[cat]
            else:
                to_add.append(self.sql_quote(cat))
        to_delete = old_cats.values()

        # add new categories
        if to_add:
            inserts = []
            for cat in to_add:
                cat = self.sql_quote(encodeString(cat))
                inserts.append("(0, %s, %s, 0)" % (cat, db_org_id))
            query = """
                INSERT INTO GlobalCategories values
                %s""" % ", ".join(inserts)
            self.reader.query(query)

        # delete old, unused categories
        if to_delete:
            query = """
                DELETE from GlobalCategories
                WHERE gcid IN (%s)""" % ", ".join(to_delete)
            self.reader.query(query)
            # and category/event links
            query = """
                DELETE from EvCats
                WHERE gcid IN (%s)""" % ", ".join(to_delete)
            self.reader.query(query)

    def getOrgCatList(self):
        res = []
        for cat in self.getCats(oid=self.dbOrgId()):
            title = cat['title']
            if title != 'All':
                res.append(title)
        return res

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

    def dbOrgId(self):
        """ return dbOrgId as specified in nav root;
            returns 0 if not specified or was a list.
        """
        return len(self.db_org_id) == 1 and self.db_org_id[0] or 0

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

