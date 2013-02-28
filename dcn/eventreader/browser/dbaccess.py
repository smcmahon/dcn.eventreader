"""

Database access

"""

import Acquisition

from zope.component import getMultiAdapter
from zope import interface

from Shared.DC.ZRDB.Results import Results

from plone.app.layout.navigation.interfaces import INavigationRoot

import caldate


class IEventDatabaseProvider(interface.Interface):

    def getOrgData(self):
            """
            Returns organization's data as a dict
            """

    def updateOrgData(self, **kwa):
        """
            kwa should be a dict with keys matching orgs columns
        """

    def getCats(self, oid=0):
        """
            return a list of category objects in alpha title order.
            obj attributes: title, gcid
        """

    def getOrgCats(self):
        """
            return a list of category objects for the
            context organization
        """
    def updateOrgCats(self, newlist):
        """
            We've received a new list of categories. We need
            to compare it with the existing list to see what's
            changed. Additions need to be added to the global
            category list; deletions need to be removed from
            that list and the evCats table that ties events to
            categories.
        """

    def eventsByDateRange(self, start, end, org_list, **kwa):
        """
        Returns a sequence of Events with
        dates between start and end
        for organizations in org_list.
        Also, optionally, selects by several criteria from kwa.
        """

    def getEvent(self, eid):
        """ return an event object matching eid """

    def getEventDates(self, eid):
        """ return a list of the dates associated with the
            event as objects.
        """


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


def cleanDate(adate):
    return adate.strftime('%Y-%m-%d')


class EventDatabaseProvider(object):
    """
        Provides event database access methods
    """

    interface.implements(IEventDatabaseProvider)

    def __init__(self, context):
        self.context = context
        self.dbCal = Acquisition.aq_get(context, 'dbCal')
        self.reader = self.dbCal()
        if INavigationRoot.providedBy(context):
            self.db_org_id = getattr(context, 'dbOrgId', 0)
        else:
            self.db_org_id = 0

    def _sql_quote(self, astring):
        return self.dbCal.sql_quote__(astring)

    def getOrgData(self, oid=0):
        """
        Returns organization's data as a dict
        """

        oid = oid or self.db_org_id
        assert(oid != 0)

        query = """
            SELECT * FROM Orgs WHERE oid = %s
        """ % (self._sql_quote(oid))

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

        assert(self.db_org_id != 0)

        assignments = []
        for key in kwa.keys():
            assert(key.replace('_', '').isalnum())
            val = kwa[key]
            if val is None:
                val = ''
            if type(val) == type(u''):
                val = encodeString(val)
            assignments.append("""%s=%s""" % (key, self._sql_quote(val)))
        query = """
            UPDATE Orgs
            SET %s
            WHERE oid=%s
        """ % (", ".join(assignments), int(self.db_org_id))
        self.reader.query(query)

    def getCats(self, oid=0):
        """
            return a list of category objects in alpha title order.
            obj attributes: title, gcid
        """

        query = """
            select title, gcid from GlobalCategories
            where oid = %i
            order by title
        """ % oid

        return Results(self.reader.query(query))

    def getOrgCats(self):
        """
            return a list of category objects for the
            context organization
        """

        return self.getCats(oid=self.db_org_id)

    def updateOrgCats(self, newlist):
        """
            We've received a new list of categories. We need
            to compare it with the existing list to see what's
            changed. Additions need to be added to the global
            category list; deletions need to be removed from
            that list and the evCats table that ties events to
            categories.
        """

        assert(self.db_org_id != 0)

        # Get the old list, put it into a dict keyed on titles
        query = """
            select title, gcid from GlobalCategories
            where oid = %i
        """ % self.db_org_id
        old_cats = {}
        for item in Results(self.reader.query(query)):
            old_cats[decodeString(item.title)] = str(item.gcid)
        to_add = []
        for cat in newlist:
            if cat in old_cats:
                del old_cats[cat]
            else:
                to_add.append(cat)
        to_delete = old_cats.values()

        # add new categories
        if to_add:
            inserts = []
            for cat in to_add:
                cat = self._sql_quote(encodeString(cat))
                inserts.append("(0, %s, %s, 0)" % (cat, self.db_org_id))
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

    def eventsByDateRange(self, start, end, org_list, **kwa):
        """
        Returns a sequence of Events with
        dates between start and end
        for organizations in org_list.
        Also, optionally, selects by several criteria from kwa.
        """

        if org_list:
            oid_test = "AND e.oid in (%s)" % ','.join(
                [str(int(i)) for i in org_list]
                )
        else:
            oid_test = ""

        public = kwa.get('public', 'b')
        if public != 'b':
            public_test = "AND e.public = %s" % self._sql_quote(public)
        else:
            public_test = ""

        free = kwa.get('free', 'b')
        if free != 'b':
            free_test = "AND e.free = %s" % self._sql_quote(free)
        else:
            free_test = ""

        common = kwa.get('common', 'b')
        if common != 'b':
            common_test = "AND e.community = %s" % self._sql_quote(common)
        else:
            common_test = ""

        udf1 = kwa.get('udf1')
        if udf1 is None:
            udf1_test = ""
        else:
            udf1_test = "AND e.udf1 = %s" % self._sql_quote(udf1)

        udf2 = kwa.get('udf2')
        if udf2 is None:
            udf2_test = ""
        else:
            udf2_test = "AND e.udf2 = %s" % self._sql_quote(udf2)

        gcid = kwa.get('gcid')
        if gcid is None:
            gcid_test = ""
            gcid_from = ""
        else:
            gcid_test = "AND EvCats.eid = ev.eid AND EvCats.gcid = %d" % gcid
            gcid_from = ", EvCats"

        query = """
            SELECT DISTINCT
             e.eid, e.title, e.description, e.startTime, e.endTime,
             e.location, e.eventUrl,
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
        """ % (
            gcid_from, cleanDate(start), cleanDate(end),
            oid_test, public_test, free_test, common_test,
            udf1_test, udf2_test, gcid_test,
            )

        dicts = Results(self.reader.query(query)).dictionaries()

        for adict in dicts:
            for s in ('start', 'end'):
                adict[s] = caldate.parseDateString(adict[s])
            for s in ('begins', 'ends'):
                adict[s] = adict[s].replace(' ', '').lower()
            decodeStrings(adict)

        return dicts

    def getEvent(self, eid):
        """ return an event object matching eid """

        query = """
            SELECT *,
             TIME_FORMAT(startTime, "%%l:%%i %%p") as begins,
             TIME_FORMAT(endTime, "%%l:%%i %%p") as ends
            FROM Events
            WHERE eid = %i
        """ % (eid)

        dicts = Results(self.reader.query(query)).dictionaries()
        if len(dicts):
            res = dicts[0]
            decodeStrings(res)
            return res
        else:
            return None

    def getEventDates(self, eid):
        """ return a list of the dates associated with the
            event as objects.
        """

        query = """
            SELECT * from EvDates
            WHERE eid = %i
            ORDER BY sdate
        """ % (eid)
        return Results(self.reader.query(query))
