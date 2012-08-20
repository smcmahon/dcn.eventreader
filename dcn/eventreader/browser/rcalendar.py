#!/usr/bin/env python
# encoding: utf-8
"""
rcalendar.py

Created by Stephen McMahon on 2009-04-15.
"""

from time import localtime
import caldate

from DateTime import DateTime

from Acquisition import aq_inner
from zope.i18nmessageid import MessageFactory
from zope.component import getMultiAdapter

from Products.CMFCore.utils import getToolByName
from Products.Five import BrowserView
from Products.PythonScripts.standard import url_quote_plus
from Products.CMFPlone.utils import safe_unicode

PLMF = MessageFactory('plonelocales')


def _toampm(s):
    if s:
        t = (DateTime('1-1-2010 ' + s).AMPMMinutes())
        if t[0] == '0':
            t = t[1:]
        return t.replace(' ', '').replace('12:00am', '')
    return s


class RCalendar(BrowserView):

    def __init__(self, context, request):
        """
        This will initialize context and request object as they are given as view multiadaption parameters.
        """
        self.context = aq_inner(context)
        self.request = request

        self.calendar = getToolByName(self.context, 'portal_calendar')
        self._ts = getToolByName(self.context, 'translation_service')
        self.url_quote_plus = url_quote_plus

        self.now = localtime()
        self.yearmonth = yearmonth = self.getYearAndMonthToDisplay()
        self.year = year = yearmonth[0]
        self.month = month = yearmonth[1]
        self.showPrevMonth = yearmonth > (self.now[0] - 1, self.now[1])
        self.showNextMonth = yearmonth < (self.now[0] + 1, self.now[1])
        self.prevMonthYear, self.prevMonthMonth = self.getPreviousMonth(year, month)
        self.nextMonthYear, self.nextMonthMonth = self.getNextMonth(year, month)
        self.monthName = PLMF(self._ts.month_msgid(month),
                              default=self._ts.month_english(month))

    def ctool_getEventsForCalendar(self, month='1', year='2002', **kw):
        """ recreates a sequence of weeks, by days each day is a mapping.
            {'day': #, 'url': None}
        """
        year = int(year)
        month = int(month)
        # daysByWeek is a list of days inside a list of weeks, like so:
        # [[0, 1, 2, 3, 4, 5, 6],
        #  [7, 8, 9, 10, 11, 12, 13],
        #  [14, 15, 16, 17, 18, 19, 20],
        #  [21, 22, 23, 24, 25, 26, 27],
        #  [28, 29, 30, 31, 0, 0, 0]]
        daysByWeek = self.calendar._getCalendar().monthcalendar(year, month)
        weeks = []

        events = self.catalog_getevents(year, month, **kw)

        for week in daysByWeek:
            days = []
            for day in week:
                if day in events:
                    days.append(events[day])
                else:
                    days.append({'day': day, 'event': 0, 'eventslist': []})

            weeks.append(days)

        return weeks

    def catalog_getevents(self, year, month, **kw):
        """ given a year and month return a list of days that have events
        """
        # XXX: this method violates the rules for tools/utilities:
        # it depends on a non-utility tool
        year = int(year)
        month = int(month)
        last_day = self.calendar._getCalendar().monthrange(year, month)[1]
        first_date = self.calendar.getBeginAndEndTimes(1, month, year)[0]
        last_date = self.calendar.getBeginAndEndTimes(last_day, month, year)[1]

        query_args = {
            'portal_type': self.calendar.getCalendarTypes(),
            'review_state': self.calendar.getCalendarStates(),
            'start': {'query': last_date, 'range': 'max'},
            'end': {'query': first_date, 'range': 'min'},
            'sort_on': 'start'
        }
        query_args.update(kw)

        ctool = getToolByName(self, 'portal_catalog')
        query = ctool(**query_args)

        # compile a list of the days that have events
        eventDays = {}
        for daynumber in range(1, 32):  # 1 to 31
            eventDays[daynumber] = {'eventslist': [],
                                    'event': 0,
                                    'day': daynumber}
        includedevents = []
        for result in query:
            if result.getRID() in includedevents:
                break
            else:
                includedevents.append(result.getRID())

            # we need to deal with events that end after this month
            if (result.end.year(), result.end.month()) != (year, month):
                eventEndDay = last_day
                eventEndDate = last_date
            else:
                eventEndDay = result.end.day()
                eventEndDate = result.end

            # and events that started last month
            if (result.start.year(), result.start.month()) != (year, month):
                eventStartDay = 1
                eventStartDate = first_date
            else:
                eventStartDay = result.start.day()
                eventStartDate = result.start

            # and recurrence
            recurs = result.recurs
            start = result.start.earliestTime()
            if recurs == 'weekly':
                dates = caldate.weekly(eventStartDate, eventEndDate, start)
                allEventDays = [e.day() for e in dates]
            elif recurs == 'biweekly':
                dates = caldate.biweekly(eventStartDate, eventEndDate, start)
                allEventDays = [e.day() for e in dates]
            elif recurs == 'monthly':
                dates = caldate.monthly(eventStartDate, eventEndDate, start)
                allEventDays = [e.day() for e in dates]
            else:  # daily
                allEventDays = range(eventStartDay, eventEndDay + 1)

            # construct subject class selectors
            exclasses = ' '.join(["subject-%s" % url_quote_plus(s).replace('+', '-') for s in result.Subject])

            # construct dictionary to return for event
            st = result.start.AMPMMinutes().lstrip('0')
            event = {'end': None,
                     'start': st,
                     'title': result.Title or result.getId,
                     'desc': result.Description,
                     'url': result.getURL(),
                     'exclasses': exclasses,
                    }

            # put event in list
            for eventday in allEventDays:
                eventDays[eventday]['eventslist'].append(event)
                eventDays[eventday]['event'] = 1

        return eventDays

    def getEventsForCalendar(self):
        context = aq_inner(self.context)
        year = self.year
        month = self.month
        portal_state = getMultiAdapter((self.context, self.request), name=u'plone_portal_state')
        navigation_root_path = portal_state.navigation_root_path()
        weeks = self.ctool_getEventsForCalendar(month, year, path=navigation_root_path)
        for week in weeks:
            for day in week:
                daynumber = day['day']
                if daynumber == 0:
                    continue
                day['is_today'] = self.isToday(daynumber)
                if day['event']:
                    cur_date = DateTime(year, month, daynumber)
                    localized_date = [self._ts.ulocalized_time(cur_date, context=context, request=self.request)]
                    for e in day['eventslist']:
                        e['start'] = _toampm(e['start'])
                        e['end'] = _toampm(e['end'])
                    day['eventstring'] = '\n'.join(
                            localized_date + [' %s' % self.getEventString(e) for e in day['eventslist']]
                            )
                    day['date_string'] = '%s-%s-%s' % (year, month, daynumber)

        return weeks

    def getEventString(self, event):
        start = event['start'] and ':'.join(event['start'].split(':')[:2]) or ''
        end = event['end'] and ':'.join(event['end'].split(':')[:2]) or ''
        title = safe_unicode(event['title']) or u'event'

        if start and end:
            eventstring = "%s-%s %s" % (start, end, title)
        elif start:  # can assume not event['end']
            eventstring = "%s - %s" % (start, title)
        elif event['end']:  # can assume not event['start']
            eventstring = "%s - %s" % (title, end)
        else:  # can assume not event['start'] and not event['end']
            eventstring = title

        return eventstring

    def getYearAndMonthToDisplay(self):
        session = None
        request = self.request

        # First priority goes to the data in the REQUEST
        year = request.get('year', None)
        month = request.get('month', None)

        # Next get the data from the SESSION
        if self.calendar.getUseSession():
            session = request.get('SESSION', None)
            if session:
                if not year:
                    year = session.get('calendar_year', None)
                if not month:
                    month = session.get('calendar_month', None)

        # Last resort to today
        if not year:
            year = self.now[0]
        if not month:
            month = self.now[1]

        year, month = int(year), int(month)

        # Store the results in the session for next time
        if session:
            session.set('calendar_year', year)
            session.set('calendar_month', month)

        # Finally return the results
        return year, month

    def getPreviousMonth(self, year, month):
        if month == 0 or month == 1:
            month, year = 12, year - 1
        else:
            month -= 1
        return (year, month)

    def getNextMonth(self, year, month):
        if month == 12:
            month, year = 1, year + 1
        else:
            month += 1
        return (year, month)

    def getWeekdays(self):
        """Returns a list of Messages for the weekday names."""
        weekdays = []
        # list of ordered weekdays as numbers
        for day in self.calendar.getDayNumbers():
            weekdays.append(PLMF(self._ts.day_msgid(day, format='s'),
                                 default=self._ts.weekday_english(day, format='a')))

        return weekdays

    def isToday(self, day):
        """Returns True if the given day and the current month and year equals
           today, otherwise False.
        """
        return self.now[2] == day and self.now[1] == self.month and \
               self.now[0] == self.year

    def getReviewStateString(self):
        states = self.calendar.getCalendarStates()
        return ''.join(map(lambda x: 'review_state=%s&amp;' % self.url_quote_plus(x), states))

    def getQueryString(self):
        request = self.request
        query_string = request.get('orig_query',
                                   request.get('QUERY_STRING', None))
        if len(query_string) == 0:
            query_string = ''
        else:
            query_string = '%s&amp;' % query_string
        return query_string

    def getevents(self, first, last, **kwa):
        """ given start and end dates, return a list of days that have events
        """

        ctool = self.calendar
        catalog = getToolByName(self.context, 'portal_catalog')
        site_properties = getToolByName(self.context, 'portal_properties').site_properties

        ampm = site_properties.getProperty('localLongTimeFormat').find('%p') >= 0

        first_date = first.earliestTime()
        last_date = last.latestTime()

        query = catalog(
            portal_type=ctool.getCalendarTypes(),
            review_state=ctool.getCalendarStates(),
            start={'query': last_date, 'range': 'max'},
            end={'query': first_date, 'range': 'min'},
            sort_on='start',
            **kwa)

        # compile a list of the days that have events
        events = []

        for result in query:

            # get the dates, taking recurrence into account
            recurs = getattr(result, 'recurs', 'daily')
            start = result.start
            ldate = min(last_date, result.end.latestTime())
            if recurs == 'weekly':
                dates = caldate.weekly(first_date, ldate, start)
            elif recurs == 'biweekly':
                dates = caldate.biweekly(first_date, ldate, start)
            elif recurs == 'monthly':
                dates = caldate.monthly(first_date, ldate, start)
            else:  # daily
                dates = caldate.daily(first_date, ldate, start)

            if dates:
                if ampm:
                    st = result.start.AMPMMinutes().lstrip('0')
                else:
                    st = result.start.TimeMinutes()

                time = list(result.start.parts()[3:5])
                # put event in list
                for day in dates:
                    startdt = DateTime(*(list(day.parts()[0:3]) + time))
                    events.append((startdt, st, result))

        # sort without considering result part
        events.sort(
            lambda x, y: cmp(x[:2], y[:2])
            )
        return events

    def getNextDaysEvents(self, days, **kwa):
        date = kwa.get('date', None) or getattr(self.request, 'date', None)
        if date is not None:
            today = DateTime(date.replace('-', '/'))
        else:
            today = DateTime()
        return self.getevents(today, today + days, **kwa)

    def getNextMonthEvents(self, **kwa):
        return self.getNextDaysEvents(30, **kwa)

    def getNextWeekEvents(self, **kwa):
        return self.getNextDaysEvents(6, **kwa)

    def getTodayEvents(self, context, **kwa):
        return self.getNextDaysEvents(0, **kwa)
