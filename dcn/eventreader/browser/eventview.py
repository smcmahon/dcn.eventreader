# -*- coding: utf-8 -*-

from Acquisition import aq_get, aq_base
from zope.interface import implements, Interface
from zope.component import getMultiAdapter
from Shared.DC.ZRDB.Results import Results

from Products.Five import BrowserView

from DateTime import DateTime

import param_utils
from dbaccess import IEventDatabaseProvider

# from Products.CMFCore.utils import getToolByName


def dtToStr(dt):
    parts = dt.parts()
    return "%i/%i/%i" % (parts[1], parts[2], parts[0] % 1000)


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

    def getParams(self):
        """ get the useful params as a dict """


class EventView(BrowserView):
    """ Event View """

    implements(IEventView)

    def __init__(self, context, request):
        self.context = context
        self.request = request
        self.database = IEventDatabaseProvider(context)
        self.portal_state = getMultiAdapter(
            (self.context, self.request),
            name=u'plone_portal_state'
            )
        self.navigation_root = self.portal_state.navigation_root()
        self.db_org_id = getattr(aq_base(self.navigation_root), 'dbOrgId', 0)
        self.params = param_utils.getQueryParams(request)
        self.eid = self.params['eid']

    def getEvent(self):
        """ find an event by eid """

        return self.database.getEvent(self.eid)

    def getEventDates(self):
        """ create a list of the dates associated with the
            event. consolidate ranges.
        """

        dates = self.database.getEventDates(self.eid)
        res = []
        in_series = False
        last_date = DateTime('1/1/1900')
        s = u''
        for item in dates:
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

    def needOrg(self, oid):
        """ do we need to show organizational details? """

        # Yes, unless oid of event matches that from nav root
        return self.db_org_id != oid

    def getOrg(self, oid):
        """ return a dict for the organization """

        return self.database.getOrgData(oid)

    def getParams(self):
        """ get the useful params as a dict """

        return self.params
