# -*- coding: utf-8 -*-
from Products.CMFCore.utils import getToolByName
from Products.Five.browser.pagetemplatefile import ViewPageTemplateFile
from plone.app.vocabularies import SlicableVocabulary
from zope.browser.interfaces import ITerms
from zope.component.hooks import getSite
from zope.formlib.interfaces import ISourceQueryView
from zope.interface import implements, classProvides
from zope.schema.interfaces import ISource, IContextSourceBinder
from zope.schema.interfaces import IVocabularyFactory
from zope.schema.vocabulary import SimpleTerm

class PrincipalsSource(object):
     """

#       >>> from zope.component import queryUtility
#       >>> from plone.app.vocabularies.tests.base import create_context
#       >>> from plone.app.vocabularies.tests.base import DummyTool
#       >>> from plone.app.vocabularies.users import UsersSource
#
#       >>> name = 'plone.app.vocabularies.Groups'
#       >>> util = queryUtility(IVocabularyFactory, name)
#       >>> context = create_context()
#
#       >>> len(util(context))
#       0
#
#       >>> class DummyGroup(object):
#       ...     def __init__(self, id, name):
#       ...         self.id = id
#       ...         self.name = name
#       ...
#       ...     def getGroupId(self):
#       ...         return self.id
#       ...
#       ...     def getGroupTitleOrName(self):
#       ...         return self.name
#
#       >>> tool = DummyTool('portal_groups')
#       >>> def listGroups():
#       ...     return (DummyGroup('editors', 'Editors'),
#       ...             DummyGroup('viewers', 'Viewers'))
#       >>> tool.listGroups = listGroups
#       >>> context.portal_groups = tool
#
#       >>> groups = util(context)
#       >>> groups
#       <zope.schema.vocabulary.SimpleVocabulary object at ...>
#       >>> len(groups.by_token)
#       2
#
#       >>> tool = DummyTool('acl_users')
#       >>> users = ('user1', 'user2')
#       >>> def getUserById(value, default):
#       ...     return value in users and value or default
#       >>> tool.getUserById = getUserById
#       >>> def searchUsers(fullname=None):
#       ...     return [dict(userid=u) for u in users]
#       >>> tool.searchUsers = searchUsers
#       >>> context.acl_users = tool
#
#       >>> source = UsersSource(context)
#       >>> source
#       <plone.app.vocabularies.users.UsersSource object at ...>
#
#       >>> len(source.search(None))
#       2
#       >>> psource = PrincipalsSource(context)
#       >>> psource
#       <plone.app.vocabularies.principals.PrincipalsSource object at ...>
#
#       >>> len(psource.search(None))
#       4
#
#     """
     implements(ISource)
     classProvides(IContextSourceBinder)

     def __init__(self, context):
         self.context = context
         self.users = getToolByName(context, "acl_users")

     def __contains__(self, value):
         """Return whether the value is available in this source
         """
         if self.get(value) is None:
             return False
         return True

     def search(self, query):
         return self.users.searchPrincipals(fullname=query)

     def get(self, value):
         return self.users.searchPrincipals(value, None)

class PrincipalsVocabulary(SlicableVocabulary):

    def __init__(self, terms, context, *interfaces):
        super(PrincipalsVocabulary, self).__init__(terms, *interfaces)
        self._users = getToolByName(context, "acl_users")

    @classmethod
    def fromItems(cls, items, context, *interfaces):
        def lazy(items):
            for item in items:
                principal_id = item.get('userid') or item.get('groupid')
                yield cls.createTerm(principal_id, item['principal_type'], context)
        return cls(lazy(items), context, *interfaces)
    fromValues = fromItems

    @classmethod
    def createTerm(cls, userid, principal_type, context):
        acl_users = getToolByName(context, "acl_users")
        # Check if we are a user or group
        if principal_type == 'user':
            user = acl_users.getUserById(userid, None)
            if user:
                fullname = user.getProperty('fullname', None) or userid
                return SimpleTerm(userid, userid, fullname)
        if principal_type == 'group':
            group = acl_users.searchGroups(id=userid, exact_match=True)[0]
            return SimpleTerm(group['id'], group['id'], group['title'])

    def __contains__(self, value):
        return self._users.searchPrincipals(id=value, exact_match=True) and True or False

    def getTerm(self, userid):
        principals = self._users.searchPrincipals(id=userid, exact_match=True)
        principal = principals[0]
        user = principal.get('userid')
        group = principal.get('groupid')
        if user:
            user_obj = self._users.getUserById(user, None)
            fullname = user_obj.getProperty('fullname', None) or user
            return SimpleTerm(user, user, fullname)
        if group:
            group = self._users.searchGroups(id=group, exact_match=True)[0]
            return SimpleTerm(group['id'], group['id'], group['title'])

    getTermByToken = getTerm

    def __iter__(self):
        return self._terms


class PrincipalsFactory(object):
    """
    """
    implements(IVocabularyFactory)

    def __call__(self, context, query=''):
        if context is None:
            context = getSite()
        acl_users = getToolByName(context, "acl_users")
        users = acl_users.searchUsers(fullname=query)
        groups = acl_users.searchGroups(fullname=query)
        principals = users + groups
        return PrincipalsVocabulary.fromItems(
            principals, context)


class PrincipalsSourceQueryView(object):
    """ Just a copy from UsersSourceQueryView. Needs refactor
    """
    implements(ITerms,
               ISourceQueryView)

    template = ViewPageTemplateFile('searchabletextsource.pt')

    def __init__(self, context, request):
        self.context = context
        self.request = request

    def getTerm(self, value):
        user = self.context.get(value)
        token = value
        title = value
        if user is not None:
            title = user.getProperty('fullname', None) or user.getId()
        return SimpleTerm(value, token=token, title=title)

    def getValue(self, token):
        if token not in self.context:
            raise LookupError(token)
        return token

    def render(self, name):
        return self.template(name=name)

    def results(self, name):
        # check whether the normal search button was pressed
        if name + ".search" in self.request.form:
            query_fieldname = name + ".query"
            if query_fieldname in self.request.form:
                query = self.request.form[query_fieldname]
                if query != '':
                    return self.context.search(query)
