"""

    Event Edit Form

"""

from zope.component import getMultiAdapter
from zope import interface
from zope import schema
from zope.schema.vocabulary import SimpleVocabulary

from z3c.form import button

from plone.directives import form
from plone.app.layout.navigation.interfaces import INavigationRoot


# from Products.CMFCore.interfaces import INavigationRoot
# from Products.statusmessages.interfaces import IStatusMessage


class IEventEditForm(form.Schema):
    """ Define form fiels """

    title = schema.TextLine(
            title=u"Event Title",
            description=u"Keep it short! Turn off the caps-lock.",
        )

    description = schema.Text(
            title=u"Event Description",
        )

    location = schema.TextLine(
            title=u"Event Location",
            required=False,
        )

    eventUrl = schema.URI(
            title=u"Event web page or site",
            required=False,
        )

    eventContact = schema.TextLine(
            title=u"Name of event contact",
            required=False,
        )

    eventEmail = schema.TextLine(
            title=u"Email address of event contact",
            required=False,
        )

    eventPhone = schema.TextLine(
            title=u"Phone # of event contact",
            required=False,
        )


class EventContext(object):
    interface.implements(IEventEditForm)


class EventEditForm(form.SchemaForm):
    """ Define Form handling
    """

    schema = IEventEditForm
    ignoreContext = False

    # attributes we'll get from the database view
    database_attributes = (
        'title',
        'description',
        'location',
        'eventUrl',
        'eventContact',
        'eventEmail',
        'eventPhone',
        )

    def __init__(self, context, request):
        super(EventEditForm, self).__init__(context, request)
        request['disable_border'] = 1
        request['disable_plone.rightcolumn'] = 1
        # self.evq_view = getMultiAdapter((self.context, self.request), name=u'eventquery_view')
        self.event_view = getMultiAdapter((self.context, self.request), name=u'showEvent')
        self.db_org_id = self.event_view.db_org_id
        assert(INavigationRoot.providedBy(self.context))

    def getContent(self):
        """
        fill and return a content object
        """

        obj = EventContext()

        event_data = self.event_view.getEvent()
        assert(self.db_org_id == event_data['oid'])
        for key in EventEditForm.database_attributes:
            value = event_data.get(key)
            setattr(obj, key, value)

        return obj

    @button.buttonAndHandler(u'Ok')
    def handleApply(self, action):
        data, errors = self.extractData()
        if errors:
            self.status = self.formErrorsMessage
            return

        # Do something with valid data here

        # Set status on this form page
        # (this status message is not bound to the session
        # and does not go thru redirects)
        self.status = "Thank you very much!"

    @button.buttonAndHandler(u"Cancel")
    def handleCancel(self, action):
        """User cancelled. Redirect back to the front page.
        """
