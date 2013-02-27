"""

    Event Organization Edit Form

"""

# Next to-do: validate count of org-specific categories


from zope.component import getMultiAdapter
from zope import interface
from zope import schema
from zope.schema.vocabulary import SimpleVocabulary

from z3c.form import button

from plone.directives import form
from plone.app.layout.navigation.interfaces import INavigationRoot

# from Products.statusmessages.interfaces import IStatusMessage

cat_options = SimpleVocabulary.fromItems((
    (u'Use Organization-Specific Categories', 'useOrgCats'),
    (u'Use Community Calendar Categories', 'useMajorCats')
    ))


@interface.implementer(schema.interfaces.IContextSourceBinder)
class orgCatSource(object):
    def __call__(self, context):
        cats = context._view.getCats(include_all=False)
        items = [
            (i['title'], i['gcid'])
            for i in cats
        ]
        return SimpleVocabulary.fromItems(items)


class IEventOrgSchema(form.Schema):
    """ Define form fields """

    acronym = schema.TextLine(
        title=u"Acronym",
        description=u"Very short identifier for this organization in the community calendar",
        )

    url = schema.URI(
        title=u"Organization's web site",
        description=u"Leave empty to use this site. Include http:// or https://.",
        required=False,
        )

    alt_cal_url = schema.URI(
        title=u"Alternate calendar web site",
        description=u"""
            The web page on which you display your calendar.
            This is used on the community calendar to direct viewers to
            your calendar.
            Leave empty to use this site. Include http:// or https://.
            """,
        required=False,
        )

    contact = schema.TextLine(
        title=u"Public contact for events",
        description=u"""
            The name of your organization's contact person for events.
            This will only be shown if there is no contact for an individual
            event.
            """,
        required=False,
        )

    email = schema.TextLine(
        title=u"Email address of public contact for events",
        required=False,
        )

    phone = schema.TextLine(
        title=u"Phone number of public contact for events",
        required=False,
        )

    ##############
    # Categories Fieldset
    form.fieldset(
        'categories',
        label=u"Categories",
        description=u"""
            Your events may be tagged as belonging to categories.
            There is a pre-defined category set for the community
            calendar, and you may define your own organization-specific
            categories. The organization-specific categories will only
            show on your own calendar.
            """,
        fields=['catOptions', 'org_categories', 'defaultMajorCats']
    )

    catOptions = schema.Set(
        title=u"Category Use",
        description=u"""
            Which categories would you like to use when you enter events.
            Only major categories will show in the community calendar;
            organization-specific categories will show on your own
            calendar.
            """,
        value_type=schema.Choice(vocabulary=cat_options),
        required=False,
        )

    org_categories = schema.List(
        title=u"Organization-Specific Categories",
        description=u"""
            If your are using organization-specific categories, you may
            specify up to 13 categories here. These will show up on your
            calendar, but not the community calendar.
        """,
        value_type=schema.TextLine(),
        )

    defaultMajorCats = schema.Set(
        title=u"Default Community Calendar Categories",
        description=u"""
            Choose the community-calendar categories that you wish to
            be automatically set on new events.
            If you are using community calendar categories, you will be
            able to change this when an event is edited or created.
            If not, these will always be applied.
        """,
        required=False,
        value_type=schema.Choice(source=orgCatSource())
        )

    ##############
    # Flags Fieldset
    form.fieldset(
        'flags',
        label=u"Flags",
        description=u"""
            Supply one or two organization-specific flag names
            if you wish to add check-box fields to event forms.
            You may then select events that have (or don't have)
            these flags checked.""",
        fields=['udf1_name', 'udf2_name', ]
    )

    udf1_name = schema.TextLine(
        title=u"Flag One",
        required=False,
        )

    udf2_name = schema.TextLine(
        title=u"Flag Two",
        required=False,
        )


class OrgContext(object):
    interface.implements(IEventOrgSchema)


class EventOrgEditForm(form.SchemaForm):
    """ Define Form handling
    """

    schema = IEventOrgSchema
    ignoreContext = False

    label = u"Calendar settings"
    description = u"Community Calendar settings for this organization."
    # form_name = u"Calendar settings"

    # attributes we'll be setting and getting from the
    # context. The rest will come from the database.
    context_attributes = (
        'catOptions',
        'defaultMajorCats',
        'udf1_name',
        'udf2_name',
        )

    # attributes we'll get from the database view
    database_attributes = (
        'acronym',
        'url',
        'alt_cal_url',
        'contact',
        'email',
        'phone'
        )

    def __init__(self, context, request):
        super(EventOrgEditForm, self).__init__(context, request)
        request['disable_border'] = 1
        request['disable_plone.rightcolumn'] = 1
        self.evq_view = getMultiAdapter((self.context, self.request), name=u'eventquery_view')
        assert(INavigationRoot.providedBy(self.context))

    def getContent(self):
        """
        fill and return a content object
        """

        obj = OrgContext()
        # orgCatSource will need to be able to get at the events query view
        obj._view = self.evq_view

        for key in EventOrgEditForm.context_attributes:
            value = getattr(self.context, key, '')
            setattr(obj, key, value)

        org_data = self.evq_view.getOrgData()
        for key in EventOrgEditForm.database_attributes:
            value = org_data.get(key)
            setattr(obj, key, value)

        obj.org_categories = self.evq_view.getOrgCatList()

        return obj

    @button.buttonAndHandler(u'Ok')
    def handleApply(self, action):
        data, errors = self.extractData()

        if errors:
            self.status = self.formErrorsMessage
            return

        for key in EventOrgEditForm.context_attributes:
            value = data.get(key)
            setattr(self.context, key, value)

        org_data = {}
        for key in EventOrgEditForm.database_attributes:
            org_data[key] = data.get(key)
        self.evq_view.updateOrgData(**org_data)

        self.evq_view.updateOrgCats(data.get('org_categories', []))

        # Set status on this form page
        # (this status message is not bound to the session
        # and does not go thru redirects)
        self.status = "Organization event settings updated"

    @button.buttonAndHandler(u"Cancel")
    def handleCancel(self, action):
        """User cancelled. Redirect back to the front page.
        """