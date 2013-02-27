"""

    Event Edit Form

"""

# from five import grok
from plone.directives import form

from zope import schema
from z3c.form import button

# from Products.CMFCore.interfaces import INavigationRoot
# from Products.statusmessages.interfaces import IStatusMessage


class IEventEditForm(form.Schema):
    """ Define form fiels """

    name = schema.TextLine(
            title=u"Your name",
        )


class EventEditForm(form.SchemaForm):
    """ Define Form handling
    """

    schema = IEventEditForm
    ignoreContext = True

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
