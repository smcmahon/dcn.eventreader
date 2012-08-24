from Acquisition import aq_get, aq_base
from zope.interface import implements, Interface
from zope.component import getMultiAdapter
from Shared.DC.ZRDB.Results import Results

from Products.Five import BrowserView

# from Products.CMFCore.utils import getToolByName


class IEventView(Interface):
    """
    Event view interface
    """

    def getEvent():
        """ find an event by eid """


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

    def getEvent(self):
        """ find an event by eid """

        eid = self.request.form.get('eid')
        if eid is None:
            return None

        query = """
            SELECT * from Events
            WHERE eid = %i
        """ % (int(eid))

        dicts = Results(self.reader.query(query)).dictionaries()
        if len(dicts):
            return dicts[0]
        else:
            return None
