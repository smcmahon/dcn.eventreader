"""

    Event Organization Edit Form

"""

# XXX To-do: validate count of org-specific categories
# Make redirect smarter
# figure out a way to make messages survive the overlay redirect


from zope import interface
from zope import schema
from zope.component import getMultiAdapter
from zope.schema.vocabulary import SimpleVocabulary

from z3c.form import button

from plone.directives import form
from plone.app.layout.navigation.interfaces import INavigationRoot

from dbaccess import IEventDatabaseProvider, IEventDatabaseWriteProvider

from Products.statusmessages.interfaces import IStatusMessage

cat_options = SimpleVocabulary.fromItems((
    (u'Use Organization-Specific Categories', 'useOrgCats'),
    (u'Use Community Calendar Categories', 'useMajorCats')
    ))


@interface.implementer(schema.interfaces.IContextSourceBinder)
class majorCatSource(object):
    def __call__(self, context):
        cats = context._database.getCats()
        items = [
            (i.title, i.gcid)
            for i in cats
        ]
        return SimpleVocabulary.fromItems(items)


class IEventOrgSchema(form.Schema):
    """ Define form fields """

    name = schema.TextLine(
        title=u"Organization name",
        required=True,
        )

    acronym = schema.TextLine(
        title=u"Acronym",
        description=u"Very short identifier for this organization in the community calendar",
        required=True,
        )

    description = schema.TextLine(
        title=u"Organization description",
        required=False,
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

    ccal_link = schema.Choice(
        title=u"Community Calendar Link",
        description=u"""
            Should we provide a link from the pooled community calendar
            to your organization's calendar?
            """,
        vocabulary=SimpleVocabulary.fromItems((
            (u'Yes', 1),
            (u'No', 0)
            )),
        default=0,
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
        default=set(['useMajorCats']),
        )

    org_categories = schema.List(
        title=u"Organization-Specific Categories",
        description=u"""
            If your are using organization-specific categories, you may
            specify up to 13 categories here. These will show up on your
            calendar, but not the community calendar.
        """,
        value_type=schema.TextLine(),
        required=False,
        default=[],
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
        value_type=schema.Choice(source=majorCatSource()),
        default=set([]),
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
        'name',
        'description',
        'acronym',
        'url',
        'alt_cal_url',
        'contact',
        'email',
        'phone',
        'ccal_link',
        )

    def __init__(self, context, request):
        assert(INavigationRoot.providedBy(context))
        super(EventOrgEditForm, self).__init__(context, request)
        self.database = IEventDatabaseProvider(context)
        request['disable_border'] = 1
        request['disable_plone.rightcolumn'] = 1
        # self.evq_view = getMultiAdapter((self.context, self.request), name=u'eventquery_view')

    def getContent(self):
        """
        fill and return a content object
        """

        obj = OrgContext()
        # orgCatSource will need to be able to get at the database
        obj._database = self.database

        for key in EventOrgEditForm.context_attributes:
            value = getattr(self.context, key, '')
            setattr(obj, key, value)

        if self.database.db_org_id:
            org_data = self.database.getOrgData()
            for key in EventOrgEditForm.database_attributes:
                value = org_data.get(key)
                setattr(obj, key, value)
            obj.org_categories = [c.title for c in self.database.getOrgCats()]
        else:
            obj.name = getattr(self.context, 'title', u"Organization Name")
            obj.description = getattr(self.context, 'description', u"Organization Description")

        return obj

    @button.buttonAndHandler(u'Save')
    def handleApply(self, action):
        data, errors = self.extractData()

        # get write access to the database
        portal_state = getMultiAdapter(
            (self.context, self.request),
            name=u'plone_portal_state'
            )
        navigation_root = portal_state.navigation_root()
        writer = IEventDatabaseWriteProvider(navigation_root)

        if errors:
            self.status = self.formErrorsMessage
            return

        for key in EventOrgEditForm.context_attributes:
            value = data.get(key)
            setattr(self.context, key, value)

        org_data = {}
        for key in EventOrgEditForm.database_attributes:
            org_data[key] = data.get(key)
        if writer.db_org_id == 0:
            db_org_id = writer.insertOrg(**org_data)
            setattr(navigation_root, 'dbOrgId', db_org_id)
        else:
            writer.updateOrgData(**org_data)

        writer.updateOrgCats(data.get('org_categories', []))

        messages = IStatusMessage(self.request)
        messages.add(u"Organization event settings updated", type=u"info")

        self.request.response.redirect("@@caledit")

    @button.buttonAndHandler(u"Cancel")
    def handleCancel(self, action):
        """User cancelled. Redirect back to the front page.
        """

        self.request.response.redirect("@@caledit")
