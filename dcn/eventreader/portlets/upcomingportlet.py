from zope import schema
from zope.interface import implements
from zope.component import getMultiAdapter

from plone.portlets.interfaces import IPortletDataProvider
from plone.app.portlets.portlets import base

# TODO: If you define any fields for the portlet configuration schema below
# do not forget to uncomment the following import
#from zope import schema
from zope.formlib import form

from Products.Five.browser.pagetemplatefile import ViewPageTemplateFile

from dcn.eventreader import eventreaderMessageFactory as _


class IUpcomingPortlet(IPortletDataProvider):
    """A portlet
    """

    count = schema.Int(title=_(u'Number of items to display'),
                       description=_(u'How many items to list.'),
                       required=True,
                       default=5)


class Assignment(base.Assignment):
    """Portlet assignment.

    This is what is actually managed through the portlets UI and associated
    with columns.
    """

    implements(IUpcomingPortlet)

    def __init__(self, count=5):
        self.count = count

    @property
    def title(self):
        """This property is used to give the title of the portlet in the
        "manage portlets" screen.
        """
        return "Upcoming Events Portlet"


class Renderer(base.Renderer):
    """Portlet renderer.

    This is registered in configure.zcml. The referenced page template is
    rendered, and the implicit variable 'view' will refer to an instance
    of this class. Other methods can be added and referenced in the template.
    """

    render = ViewPageTemplateFile('upcomingportlet.pt')

    def __init__(self, *args):
        base.Renderer.__init__(self, *args)
        self.eventquery = getMultiAdapter((self.context, self.request), name=u'eventquery_view')

    def eventDayList(self):
        return self.eventquery.eventDayList(max=self.data.count)


class AddForm(base.AddForm):
    """Portlet add form.

    This is registered in configure.zcml. The form_fields variable tells
    zope.formlib which fields to display. The create() method actually
    constructs the assignment that is being added.
    """
    form_fields = form.Fields(IUpcomingPortlet)
    label = _(u"Add Events Portlet")
    description = _(u"This portlet lists upcoming Events.")

    def create(self, data):
        return Assignment(count=data.get('count', 5))


class EditForm(base.EditForm):
    """Portlet edit form.

    This is registered with configure.zcml. The form_fields variable tells
    zope.formlib which fields to display.
    """
    form_fields = form.Fields(IUpcomingPortlet)
