"""

    Event Edit Form

"""

# XXX: force oid check on event update

from datetime import date
import parsedatetime

from zope import interface
from zope import schema
import zope.component
from zope.component import getMultiAdapter
from zope.schema.vocabulary import SimpleVocabulary

import z3c.form
from z3c.form import button
from z3c.form import validator

from plone.directives import form
from plone.app.layout.navigation.interfaces import INavigationRoot

from dbaccess import IEventDatabaseProvider, IEventDatabaseWriteProvider
from dbaccess import decodeString

from caldate import parseDateString

# from Products.CMFCore.interfaces import INavigationRoot
# from Products.statusmessages.interfaces import IStatusMessage


def struct_time2str(st):
    # ##:## time from struct_time
    return "%02d:%02d" % st[3:5]


@interface.implementer(schema.interfaces.IContextSourceBinder)
class majorCatSource(object):
    def __call__(self, context):
        cats = context._database.getCats()
        items = [
            (decodeString(i.title), i.gcid)
            for i in cats
        ]
        return SimpleVocabulary.fromItems(items)


@interface.implementer(schema.interfaces.IContextSourceBinder)
class orgCatSource(object):
    def __call__(self, context):
        cats = context._database.getOrgCats()
        items = [
            (decodeString(i.title), i.gcid)
            for i in cats
        ]
        return SimpleVocabulary.fromItems(items)


class IEventEditForm(form.Schema):
    """ Define form fields """

    eid = schema.Int(
        title=u"Event ID",
        default=0,
        required=False,
        )

    title = schema.TextLine(
        title=u"Event Title",
        description=u"Keep it short! Turn off the caps-lock.",
        )

    description = schema.Text(
        title=u"Event Description",
        )

    start = schema.Date(
        title=u"Starting Date",
        )

    recurs = schema.Choice(
        title=u"Occurs",
        description=u"""
            Frequency of the event.
            Monthly means same week/day-of-week, for example 'Third Tuesday'.
        """,
        vocabulary=SimpleVocabulary.fromItems((
            (u'Daily', 'daily'),
            (u'Weekly', 'weekly'),
            (u'Bi-Weekly', 'biweekly'),
            (u'Monthly', 'monthly'),
            )),
        )

    end = schema.Date(
        title=u"Until",
        description=u"""
            For a one-day event, leave the "until" date empty or set
            it to the same date as the start date.
        """,
        required=False,
        )

    begins = schema.TextLine(
        title=u"Starting Time",
        description=u"Leave starting and ending time empty for all-day events.",
        required=False,
        )

    ends = schema.TextLine(
        title=u"Ending Time",
        required=False,
        )

    location = schema.TextLine(
            title=u"Event Location",
            required=False,
        )

    public = schema.Bool(
            title=u"Is the event public?",
            default=True,
        )

    free = schema.Bool(
            title=u"Is the event free?",
            default=True,
        )

    community = schema.Bool(
            title=u"Should the event be listed on the Community Calendar?",
            default=False,
        )

    ##############
    # Contact Fieldset
    form.fieldset(
        'contactinfo',
        label=u"Event Contact",
        description=u"""
            Contact information for this event.
            Standard organization-specific contact information
            will be shown if there is no event-specific information.
            """,
        fields=['eventUrl', 'eventContact', 'eventEmail', 'eventPhone']
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

    ##############
    # Categories Fieldset
    form.fieldset(
        'categories',
        label=u"Categories",
        description=u"""
            Your events may be tagged as belonging to categories.
            Community-calendar categories only show on the community calendar.
            The organization-specific categories will only
            show on your own calendar.
            """,
        fields=['majorCats', 'orgCats']
    )

    majorCats = schema.Set(
        title=u"Community Calendar Categories",
        description=u"""
            Choose the community-calendar categories that should
            be used as tags for this event.
        """,
        required=False,
        value_type=schema.Choice(source=majorCatSource())
        )

    orgCats = schema.Set(
        title=u"Organization-specific Categories",
        description=u"""
            Choose the organization-specific categories that should
            be used as tags for this event.
        """,
        required=False,
        value_type=schema.Choice(source=orgCatSource())
        )


class TimeValidator(validator.SimpleFieldValidator):
    """ z3c.form validator class for international phone numbers """

    def validate(self, value):
        """ Validate time field """
        if value is None:
            value = '0:00'
        rez, flag = self.view.pdtcal.parse(value)
        if flag == 2:
            # 2 is valid time; every other flag is something else
            self.request.form['%s_time' % self.field.getName()] = rez
        else:
            raise zope.interface.Invalid(u"Please specify a time in hh:mm am/pm format.")


class BeginTimeValidator(TimeValidator):
    """ simple subclass """

# Set conditions for which fields the validator class applies
validator.WidgetValidatorDiscriminators(
    BeginTimeValidator,
    field=IEventEditForm['begins']
    )
# Register the validator so it will be looked up by z3c.form machinery
zope.component.provideAdapter(BeginTimeValidator)


class EndTimeValidator(TimeValidator):
    """ simple subclass """

    def validate(self, value):
        super(EndTimeValidator, self).validate(value)
        form = self.request.form
        begins = form.get('begins_time')
        ends = form.get('ends_time')
        if begins is not None and ends is not None:
            if begins > ends:
                raise zope.interface.Invalid(u"End time must be at or after start time.")

# Set conditions for which fields the validator class applies
validator.WidgetValidatorDiscriminators(
    EndTimeValidator,
    field=IEventEditForm['ends']
    )
# Register the validator so it will be looked up by z3c.form machinery
zope.component.provideAdapter(EndTimeValidator)


class EventContext(object):
    interface.implements(IEventEditForm)


class EventEditForm(form.SchemaForm):
    """ Define Form handling
    """

    schema = IEventEditForm
    ignoreContext = False

    # attributes we'll get from the database view
    database_attributes = (
        'eid',
        'title',
        'description',
        'location',
        'eventUrl',
        'eventContact',
        'eventEmail',
        'eventPhone',
        'begins',
        'ends',
        )

    def __init__(self, context, request):
        assert(INavigationRoot.providedBy(context))
        super(EventEditForm, self).__init__(context, request)
        self.database = IEventDatabaseProvider(context)
        # get eid from 'eid' or 'form.widgets.eid'
        self.eid = int(
            request.form.get('eid',
                request.form.get('form.widgets.eid', '0').replace(',', '')
                )
            )
        self.pdtcal = parsedatetime.Calendar()
        request['disable_border'] = 1
        request['disable_plone.rightcolumn'] = 1

    def updateWidgets(self):
        super(EventEditForm, self).updateWidgets()
        self.widgets['eid'].mode = z3c.form.interfaces.HIDDEN_MODE

    def updateActions(self):
            super(EventEditForm, self).updateActions()

            delete_action = self.actions.get('handleDelete')
            if delete_action:
                delete_action.onclick = u"return confirm('Delete this event?')"

    def getContent(self):
        """
        fill and return a content object
        """

        obj = EventContext()
        obj._database = self.database

        eid = self.eid
        if eid:
            event_data = self.database.getEvent(eid)
            assert(self.database.db_org_id == event_data['oid'])
            for key in EventEditForm.database_attributes:
                value = event_data.get(key)
                setattr(obj, key, value)
            for key in ('public', 'free', 'community'):
                setattr(obj, key, event_data[key] == "Y")

            cats = [c.gcid for c in self.database.getEventCats(eid)]
            my_cats = [c.gcid for c in self.database.getOrgCats()]
            org_cats = []
            major_cats = []
            for gcid in cats:
                if gcid in my_cats:
                    org_cats.append(gcid)
                else:
                    major_cats.append(gcid)
            obj.majorCats = major_cats
            obj.orgCats = org_cats

            dates = self.database.getEventDates(eid)
            obj.start = parseDateString(dates[0].start)
            obj.end = parseDateString(dates[0].end)
            obj.recurs = dates[0].recurs
        else:
            obj.start = date.today()
            obj.end = date.today()
            portal_state = getMultiAdapter(
                (self.context, self.request), name=u'plone_portal_state')
            navigation_root = portal_state.navigation_root()
            obj.majorCats = getattr(navigation_root, 'defaultMajorCats', [])

        return obj

    def _getWriter(self):
        """
            return a database writer
        """

        portal_state = getMultiAdapter(
            (self.context, self.request),
            name=u'plone_portal_state'
            )
        navigation_root = portal_state.navigation_root()
        return IEventDatabaseWriteProvider(navigation_root)

    @button.buttonAndHandler(u'Save Event')
    def handleApply(self, action):
        data, errors = self.extractData()
        if errors:
            self.status = self.formErrorsMessage
            return

        # get write access to the database
        writer = self._getWriter()
        form = self.request.form
        portal_state = getMultiAdapter(
            (self.context, self.request),
            name=u'plone_portal_state'
            )
        member = portal_state.member()

        eid = data['eid']

        event_data = {}
        for key in EventEditForm.database_attributes:
            if key != 'eid':
                if key == 'begins':
                    # ##:## time from struct_time
                    event_data['startTime'] = struct_time2str(form['begins_time'])
                elif key == 'ends':
                    event_data['endTime'] = struct_time2str(form['ends_time'])
                else:
                    event_data[key] = data.get(key)
        for key in ('public', 'free', 'community'):
            event_data[key] = data.get(key) and "Y" or "N"

        if eid:
            writer.updateEvent(eid, member, **event_data)
            writer.deleteEventCats(eid)
            writer.deleteEventDates(eid)
        else:
            eid = writer.eventInsert(member, **event_data)

        writer.evCatsInsert(eid, list(data['orgCats'].union(data['majorCats'])))
        writer.evDatesInsert(eid, ((data['start'], data['end'], data['recurs']), ))

        # Set status on this form page
        # (this status message is not bound to the session
        # and does not go thru redirects)
        self.status = "Thank you very much!"

    @button.buttonAndHandler(u"Delete Event",
        name="handleDelete",
        condition=lambda form: form.eid != 0)
    def handleDelete(self, action):
        """
            Delete this event.
        """

        eid = self.eid
        assert(eid != 0)

        writer = self._getWriter()
        writer.deleteEventCats(eid)
        writer.deleteEventDates(eid)
        writer.deleteEvent(eid)

        self.status = "Event deleted."

    @button.buttonAndHandler(u"Cancel Edits")
    def handleCancel(self, action):
        """User cancelled. Redirect back to the front page.
        """
