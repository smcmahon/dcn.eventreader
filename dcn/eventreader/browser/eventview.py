# -*- coding: utf-8 -*-

from Acquisition import aq_get, aq_base
from zope.interface import implements, Interface
from zope.component import getMultiAdapter
from Shared.DC.ZRDB.Results import Results

from Products.Five import BrowserView

from DateTime import DateTime

import param_utils

# from Products.CMFCore.utils import getToolByName


def dtToStr(dt):
    parts = dt.parts()
    return "%i/%i/%i" % (parts[1], parts[2], parts[0] % 1000)


def csetFix(adict):
    # convert dates to DateTimes and all strings from Windows-1252 to Unicode
    for key in adict.keys():
        val = adict[key]
        if type(val) == type(''):
            adict[key] = adict[key].decode('Windows-1252', 'replace')


class IEventView(Interface):
    """
    Event view interface
    """

    def getEvent():
        """ find an event by eid """

    def getEventDates():
        """ find an event by eid """

    def displayTime(self, event):
        """ start/end time for display; None if all-day """

    def needOrg(self):
        """ do we need to show organizational details? """

    def getOrg(self, oid):
        """ return a dict for the organization """


class EventView(BrowserView):
    """ Event View """

    implements(IEventView)

    def __init__(self, context, request):
        self.context = context
        self.request = request
        self.dbCal = aq_get(context, 'dbCal')
        self.reader = self.dbCal()
        self.portal_state = getMultiAdapter(
            (self.context, self.request),
            name=u'plone_portal_state'
            )
        self.navigation_root = self.portal_state.navigation_root()
        # see if the nav root has a dbOrgId attribute. If it does, this
        # will override any org specified in request
        db_org_id = getattr(
            aq_base(self.navigation_root),
            'dbOrgId', ''
            ).split(',')[0]
        if db_org_id:
            self.db_org_id = int(db_org_id)
        else:
            self.db_org_id = -1
        try:
            self.eid = int(self.request.form.get('eid'))
        except ValueError:
            self.eid = None

    def getEvent(self):
        """ find an event by eid """

        if self.eid is None:
            return None

        query = """
            SELECT *,
             TIME_FORMAT(startTime, "%%l:%%i %%p") as begins,
             TIME_FORMAT(endTime, "%%l:%%i %%p") as ends
            FROM Events
            WHERE eid = %i
        """ % (self.eid)

        dicts = Results(self.reader.query(query)).dictionaries()
        if len(dicts):
            csetFix(dicts[0])
            return dicts[0]
        else:
            return None

    def getEventDates(self):
        """ create a list of the dates associated with the
            event. consolidate ranges.
        """

        if self.eid is None:
            return None

        query = """
            SELECT * from EvDates
            WHERE eid = %i
            ORDER BY sdate
        """ % (self.eid)

        res = []
        in_series = False
        last_date = DateTime('1/1/1900')
        s = u''
        for item in Results(self.reader.query(query)):
            if item.sdate == item.edate:
                if item.sdate - last_date <= 1:
                    in_series = True
                else:
                    if in_series:
                        s = u"%s–%s" % (s, dtToStr(last_date))
                        in_series = False
                    # else:
                    #     s = dtToStr(item.sdate)
                    s = u"%s%s%s" % (s, s and ', ' or '', dtToStr(item.sdate))
            else:
                if in_series:
                    s = u"%s-%s" % (s, dtToStr(last_date))
                    in_series = False
                if s:
                    res.append(s)
                    s = u''
                res.append(
                    u"%s %s until %s" % (item.sdate, item.recurs, item.edate)
                    )
            last_date = item.sdate

        if in_series:
            s = "%s-%s" % (s, dtToStr(last_date))
        if s:
            res.append(s)
        return 'x, '.join(res)

    def displayTime(self, event):
        """ start/end time for display; None if all-day """

        begins = event['begins']
        ends = event['ends']

        if begins == ends:
            if begins == '12:00 AM':
                return None
            return begins
        if ends == '12:00 AM':
            return begins
        return u"%s–%s" % (begins, ends)

    def needOrg(self):
        """ do we need to show organizational details? """

        # Yes, unless organization was determined as
        # a site attribute
        return self.db_org_id == -1

    def getOrg(self, oid):
        """ return a dict for the organization """

        query = """
            SELECT * from Orgs
            WHERE oid = %i
        """ % int(oid)

        dicts = Results(self.reader.query(query)).dictionaries()
        if len(dicts):
            csetFix(dicts[0])
            return dicts[0]
        else:
            return None
