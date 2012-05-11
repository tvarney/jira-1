"""
This module implements a friendly (well, friendlier) interface between the raw JSON
responses from JIRA and the Resource/dict abstractions provided by this library. Users
will construct a JIRA object as described below.
"""

import requests
import json
from jira.exceptions import JIRAError
from jira.resources import Resource, Issue, Comments, Comment, Project, Attachment, Component, Dashboards, Dashboard, Filter, Votes, Watchers, Worklog, IssueLink, IssueLinkType, IssueType, Priority, Version, Role, Resolution, SecurityLevel, Status, User, CustomFieldOption, RemoteLink

class JIRA(object):
    """
    User interface to JIRA.

    Clients interact with JIRA by constructing an instance of this object and calling its methods. For addressable
    resources in JIRA -- those with "self" links -- an appropriate subclass of Resource will be returned with
    customized update() and delete() methods, along with attribute access to fields. This means that calls of the
    form 'issue.fields.summary' will be resolved into the proper lookups to return the JSON value at that mapping.
    Methods that do not return resources will return a dict constructed from the JSON response or a scalar value;
    see each method's documentation for details on what that method returns.
    """

    DEFAULT_OPTIONS = {
        "server": "http://localhost:2990/jira",
        "rest_path": "api",
        "rest_api_version": "2"
    }

    def __init__(self, options=None, basic_auth=None, oauth=None):
        """
        Construct a JIRA client instance.

        Without any arguments, this client will connect anonymously to the JIRA instance
        started by the Atlassian Plugin SDK from one of the 'atlas-run', 'atlas-debug',
        or 'atlas-run-standalone' commands. By default, this instance runs at
        http://localhost:2990/jira. The 'options' argument can be used to set the JIRA instance to use.

        Authentication is handled with the 'basic_auth' argument. If authentication is supplied (and is
        accepted by JIRA), the client will remember it for subsequent requests.

        For quick command line access to a server, see the 'jirashell' script included with this distribution.

        Keyword arguments:
        options -- Specify the server and properties this client will use. Use a dict with any
            of the following properties:
            * server -- the server address and context path to use. Defaults to 'http://localhost:2990/jira'.
            * rest_path -- the root REST path to use. Defaults to 'api', where the JIRA REST resources live.
            * rest_api_version -- the version of the REST resources under rest_path to use. Defaults to '2'.
        basic_auth -- A tuple of username and password to use when establishing a session via HTTP BASIC
        authentication.
        """
        if options is None:
            options = {}

        self._options = dict(JIRA.DEFAULT_OPTIONS.items() + options.items())

        if basic_auth:
            self._create_http_basic_session(*basic_auth)
        elif oauth:
            self._create_oauth_session(oauth)
        else:
            verify = self._options['server'].startswith('https')
            self._session = requests.session(headers={'content-type': 'application/json'}, verify=verify)

### Information about this client

    def client_info(self):
        """Get the server this client is connected to."""
        return self._options['server']

### Universal resource loading

    def find(self, resource_format, ids=None):
        """
        Get a Resource object for any addressable resource on the server.

        This method is a universal resource locator for any RESTful resource in JIRA. The
        argument 'resource_format' is a string of the form 'resource', 'resource/{0}',
        'resource/{0}/sub', 'resource/{0}/sub/{1}', etc. The format placeholders will be
        populated from the 'ids' argument if present. The existing authentication session
        will be used.

        The return value is an untyped Resource object, which will not support specialized
        update() or delete() behavior. Moreover, it will not know to return an issue Resource
        if the client uses the resource issue path. For this reason, it is intended to support
        resources that are not included in the standard Atlassian REST API.

        Keyword arguments:
        ids -- a tuple of values to substitute in the 'resource_format' string
        """
        resource = Resource(resource_format, self._options, self._session)
        resource.find(ids)
        return resource

### Application properties

    # non-resource
    def application_properties(self, key=None):
        """
        Return the mutable server application properties.

        Keyword arguments:
        key -- the single property to return a value for
        """
        params = {}
        if key is not None:
            params['key'] = key
        return self._get_json('application-properties', params=params)

    def set_application_property(self, key, value):
        """Set the application property to the specified value."""
        url = self._options['server'] + '/rest/api/2/application-properties/' + key
        payload = {
            'id': key,
            'value': value
        }
        r = self._session.put(url, headers={'content-type': 'application/json'}, data=json.dumps(payload))
        self._raise_on_error(r)

### Attachments

    def attachment(self, id):
        """Get an attachment Resource from the server for the specified ID."""
        return self._find_for_resource(Attachment, id)

    # non-resource
    def attachment_meta(self):
        """Get the attachment metadata."""
        return self._get_json('attachment/meta')

### Components

    def component(self, id):
        """Get a component Resource from the server for the specified ID."""
        return self._find_for_resource(Component, id)

    def create_component(self, name, project, description=None, leadUserName=None, assigneeType=None,
                         isAssigneeTypeValid=False):
        """
        Create an issue component inside the specified project and return a Resource for it.
        The component name and project name are required.

        Keyword arguments:
        description -- a description of the component
        leadUserName -- the username of the user responsible for this component
        assigneeType -- see the ComponentBean.AssigneeType class for valid values
        isAssigneeTypeValid -- boolean specifying whether the assignee type is acceptable
        """
        data = {
            'name': name,
            'project': project,
            'isAssigneeTypeValid': isAssigneeTypeValid
        }
        if description is not None:
            data['description'] = description
        if leadUserName is not None:
            data['leadUserName'] = leadUserName
        if assigneeType is not None:
            data['assigneeType'] = assigneeType

        url = self._get_url('component')
        r = self._session.post(url, data=json.dumps(data))
        self._raise_on_error(r)

        component = Component(self._options, self._session, raw=json.loads(r.text))
        return component


    def component_count_related_issues(self, id):
        """Get the count of related issues for the specified component ID."""
        return self._get_json('component/' + id + '/relatedIssueCounts')['issueCount']

### Custom field options

    def custom_field_option(self, id):
        """Get a custom field option Resource from the server for the specified ID."""
        return self._find_for_resource(CustomFieldOption, id)

### Dashboards

    # TODO: Should this be _get_json instead of resource?
    def dashboards(self, filter=None, startAt=0, maxResults=20):
        """
        Return a list of Dashboard resources matching the specified parameters.

        Keyword arguments
        filter -- either "favourite" or "my"
        startAt -- index of the first dashboard to return
        maxResults -- maximum number of dashboards to return:
        """
        dashboards = Dashboards(self._options, self._session)
        params = {}
        if filter is not None:
            params['filter'] = filter
        params['startAt'] = startAt
        params['maxResults'] = maxResults
        dashboards.find(params=params)
        return dashboards

    def dashboard(self, id):
        """Get a dashboard Resource from the server for the specified ID."""
        return self._find_for_resource(Dashboard, id)

### Fields

    # non-resource
    def fields(self):
        """Return a list of all issue fields."""
        return self._get_json('field')

### Filters

    def filter(self, id):
        """Get a filter Resource from the server for the specified ID."""
        return self._find_for_resource(Filter, id)

    def favourite_filters(self):
        """Get a list of filter Resources which are the favourites of the currently authenticated user."""
        r_json = self._get_json('filter/favourite')
        filters = [Filter(self._options, self._session, raw_filter_json) for raw_filter_json in r_json]
        return filters

### Groups

    # non-resource
    def groups(self, query=None, exclude=None):
        """
        Return a list of groups matching the specified criteria.

        Keyword arguments:
        query -- filter groups by name with this string
        exclude -- filter out groups by name with this string
        """
        params = {}
        if query is not None:
            params['query'] = query
        if exclude is not None:
            params['exclude'] = exclude
        return self._get_json('groups/picker', params=params)

### Issues

    def issue(self, id, fields=None, expand=None):
        """
        Get an issue Resource from the server for the specified ID.

        Keyword arguments:
        fields -- comma-separated string of issue fields to include in the results
        expand -- extra information to fetch inside each resource
        """
        issue = Issue(self._options, self._session)

        params = {}
        if fields is not None:
            params['fields'] = fields
        if expand is not None:
            params['expand'] = expand
        issue.find(id, params=params)
        return issue

    def create_issue(self, **kw):
        pass

    def createmeta(self, projectKeys=None, projectIds=None, issuetypeIds=None, issuetypeNames=None, expand=None):
        """
        Gets the metadata required to create issues, filtered by the specified projects and issue types.

        Keyword arguments:
        projectKeys -- keys of the projects to filter the results with. Can be a single value or a comma-delimited string.
        May be combined with projectIds.
        projectIds -- IDs of the projects to filter the results with. Can be a single value or a comma-delimited string.
        May be combined with projectKeys.
        issuetypeIds -- IDs of the issue types to filter the results with. Can be a single value or a comma-delimited string.
        May be combined with issuetypeNames.
        iisuetypeNames -- Names of the issue types to filter the results with. Can be a single value or a comma-delimited string.
        May be combined with issuetypeIds.
        expand -- extra information to fetch inside each resource.
        """
        params = {}
        if projectKeys is not None:
            params['projectKeys'] = projectKeys
        if projectIds is not None:
            params['projectIds'] = projectIds
        if issuetypeIds is not None:
            params['issuetypeIds'] = issuetypeIds
        if issuetypeNames is not None:
            params['issuetypeNames'] = issuetypeNames
        if expand is not None:
            params['expand'] = expand
        return self._get_json('issue/createmeta', params)

    # non-resource
    def assign_issue(self, issue, assignee):
        """Assign the issue to the specified user."""
        url = self._options['server'] + '/rest/api/2/issue/' + issue + '/assignee'
        payload = {'name': assignee}
        r = self._session.put(url, data=json.dumps(payload))
        self._raise_on_error(r)

    # TODO: Should this be _get_json instead of resource?
    def comments(self, issue):
        """Get a list of comment Resources from the specified issue."""
        resource = Comments(self._options, self._session)
        resource.find(issue)

        comments = [Comment(self._options, self._session, raw_comment_json) for raw_comment_json in resource.raw['comments']]
        return comments

    def comment(self, issue, comment):
        """Get a comment Resource from the server for the specified ID."""
        return self._find_for_resource(Comment, (issue, comment))

    def add_comment(self, issue, body, role=None):
        pass

    # non-resource
    def editmeta(self, issue):
        """Get the edit metadata for the specified issue."""
        return self._get_json('issue/' + issue + '/editmeta')

    def remote_links(self, issue):
        """Get a list of remote link Resources from the specified issue."""
        r_json = self._get_json('issue/' + issue + '/remotelink')
        remote_links = [RemoteLink(self._options, self._session, raw_remotelink_json) for raw_remotelink_json in r_json]
        return remote_links

    def remote_link(self, issue, id):
        """Get a remote link Resource from the server for the specified ID."""
        return self._find_for_resource(RemoteLink, (issue, id))

    # non-resource
    def transitions(self, issue, id=None, expand=None):
        """
        Get a list of the transitions available on the specified issue to the current user.

        Keyword arguments:
        id -- get only the transition matching this ID
        expand -- extra information to fetch inside each transition
        """
        params = {}
        if id is not None:
            params['transitionId'] = id
        if expand is not None:
            params['expand'] = expand
        return self._get_json('issue/' + issue + '/transitions', params)['transitions']

    def votes(self, issue):
        """Get a votes Resource from the server for the specified issue."""
        return self._find_for_resource(Votes, issue)

    def watchers(self, issue):
        """Get a watchers Resource from the server for the specified issue."""
        return self._find_for_resource(Watchers, issue)

    def add_watcher(self, watcher):
        pass

    # also have delete_watcher?

    def worklogs(self, issue):
        """Get a list of worklog Resources from the server for the specified issue."""
        r_json = self._get_json('issue/' + issue + '/worklog')
        worklogs = [Worklog(self._options, self._session, raw_worklog_json) for raw_worklog_json in r_json['worklogs']]
        return worklogs

    def worklog(self, issue, id):
        """Get a worklog Resource from the server for the specified issue and worklog ID."""
        return self._find_for_resource(Worklog, (issue, id))

    def add_worklog(self, issue, timeSpent=None, adjustEstimate=None,
                    newEstimate=None, reduceBy=None):
        """Create a new worklog entry on the specified issue.

        Keyword arguments:
        timeSpent -- Add a worklog entry with this amount of time spent, e.g. "2d"
        adjustEstimate -- (optional) allows you to provide specific instructions to update the remaining time estimate
        of the issue. The value can either be new, leave, manual or auto (default).
        newEstimate -- the new value for the remaining estimate field. e.g. "2d"
        reduceBy -- the amount to reduce the remaining estimate by e.g. "2d"
        """
        params = {}
        if adjustEstimate is not None:
            params['adjustEstimate'] = adjustEstimate
        if newEstimate is not None:
            params['newEstimate'] = newEstimate
        if reduceBy is not None:
            params['reduceBy'] = reduceBy

        data = {}
        if timeSpent is not None:
            data['timeSpent'] = timeSpent

        url = self._get_url('issue/{}/worklog'.format(issue))
        r = self._session.post(url, params=params, data=json.dumps(data))
        self._raise_on_error(r)

### Attachments

    def add_attachment(self, issue, attachment):
        pass

### Issue links

    def create_issue_link(self, **kw):
        pass

    def issue_link(self, id):
        """Get an issue link Resource from the server for the specified ID."""
        return self._find_for_resource(IssueLink, id)

### Issue link types

    def issue_link_types(self):
        """Get a list of issue link type Resources from the server."""
        r_json = self._get_json('issueLinkType')
        link_types = [IssueLinkType(self._options, self._session, raw_link_json) for raw_link_json in r_json['issueLinkTypes']]
        return link_types

    def issue_link_type(self, id):
        """Get an issue link Resource from the server for the specified ID."""
        return self._find_for_resource(IssueLinkType, id)

### Issue types

    def issue_types(self):
        """Get a list of issue type Resources from the server."""
        r_json = self._get_json('issuetype')
        issue_types = [IssueType(self._options, self._session, raw_type_json) for raw_type_json in r_json]
        return issue_types

    def issue_type(self, id):
        """Get an issue type Resource from the server for the specified ID."""
        return self._find_for_resource(IssueType, id)

### User permissions

    # non-resource
    def my_permissions(self, projectKey=None, projectId=None, issueKey=None, issueId=None):
        """
        Get a dict of all available permissions on the server.

        Keyword arguments:
        projectKey -- limit returned permissions to the specified project
        projectId -- limit returned permissions to the specified project
        issueKey -- limit returned permissions to the specified issue
        issueId -- limit returned permissions to the specified issue
        """
        params = {}
        if projectKey is not None:
            params['projectKey'] = projectKey
        if projectId is not None:
            params['projectId'] = projectId
        if issueKey is not None:
            params['issueKey'] = issueKey
        if issueId is not None:
            params['issueId'] = issueId
        return self._get_json('mypermissions', params=params)

### PrioritiesK

    def priorities(self):
        """Get a list of priority Resources from the server."""
        r_json = self._get_json('priority')
        priorities = [Priority(self._options, self._session, raw_priority_json) for raw_priority_json in r_json]
        return priorities

    def priority(self, id):
        """Get a priority Resource from the server for the specified ID."""
        return self._find_for_resource(Priority, id)

### Projects

    def projects(self):
        """Get a list of project Resources from the server visible to the current authenticated user."""
        r_json = self._get_json('project')
        projects = [Project(self._options, self._session, raw_project_json) for raw_project_json in r_json]
        return projects

    def project(self, id):
        """Get a project Resource from the server for the specified ID."""
        return self._find_for_resource(Project, id)

    # non-resource
    def project_avatars(self, project):
        """Get a dict of all avatars for the specified project visible to the current authenticated user."""
        return self._get_json('project/' + project + '/avatars')

    def create_temp_project_avatar(self, project, name, size, avatar_img):
        pass

    def confirm_project_avatar(self, project, **kw):
        pass

    def project_components(self, project):
        """Get a list of component Resources present on the specified project."""
        r_json = self._get_json('project/' + project + '/components')
        components = [Component(self._options, self._session, raw_comp_json) for raw_comp_json in r_json]
        return components

    def project_versions(self, project):
        """Get a list of version Resources present on the specified project."""
        r_json = self._get_json('project/' + project + '/versions')
        versions = [Version(self._options, self._session, raw_ver_json) for raw_ver_json in r_json]
        return versions

    # non-resource
    def project_roles(self, project):
        """Get a dict of role names to resource locations for the specified project."""
        return self._get_json('project/' + project + '/role')

    def project_role(self, project, id):
        """Get a role Resource for the specified project and ID."""
        return self._find_for_resource(Role, (project, id))

### Resolutions

    def resolutions(self):
        """Get a list of resolution Resources from the server."""
        r_json = self._get_json('resolution')
        resolutions = [Resolution(self._options, self._session, raw_res_json) for raw_res_json in r_json]
        return resolutions

    def resolution(self, id):
        """Get a resolution Resource from the server for the specified ID."""
        return self._find_for_resource(Resolution, id)

### Search

    def search_issues(self, jql_str, startAt=0, maxResults=50, fields=None, expand=None):
        """
        Get a list of issue Resources matching the specified JQL search string.

        Keyword arguments:
        startAt -- index of the first issue to return
        maxResults -- maximum number of issues to return
        fields -- comma-separated string of issue fields to include in the results
        expand -- extra information to fetch inside each resource
        """
        # TODO what to do about the expand, which isn't related to the issues?
        if fields is None:
            fields = []

        search_params = {
            "jql": jql_str,
            "startAt": startAt,
            "maxResults": maxResults,
            "fields": fields,
            "expand": expand
        }

        resource = self._get_json('search', search_params)
        issues = [Issue(self._options, self._session, raw_issue_json) for raw_issue_json in resource['issues']]
        return issues

### Security levels

    def security_level(self, id):
        """Get a security level Resource for the specified ID."""
        return self._find_for_resource(SecurityLevel, id)

### Server info

    # non-resource
    def server_info(self):
        """Get a dict of server information for this JIRA instance."""
        return self._get_json('serverInfo')

### Status

    def statuses(self):
        """Get a list of status Resources from the server."""
        r_json = self._get_json('status')
        statuses = [Status(self._options, self._session, raw_stat_json) for raw_stat_json in r_json]
        return statuses

    def status(self, id):
        """Get a status Resource from the server for the specified ID."""
        return self._find_for_resource(Status, id)

### Users

    def user(self, id, expand=None):
        """
        Get a user Resource from the server with the specified username.

        Keyword arguments:
        expand -- extra information to fetch inside each resource
        """
        user = User(self._options, self._session)
        params = {}
        if expand is not None:
            params['expand'] = expand
        user.find(id, params=params)
        return user

    def search_assignable_users_for_projects(self, username, projectKeys, startAt=0, maxResults=50):
        """
        Get a list of user Resources that match the search string and can be assigned issues for the
        specified projects.

        Keyword arguments:
        startAt -- index of the first user to return
        maxResults -- maximum number of users to return
        """
        params = {
            'username': username,
            'projectKeys': projectKeys,
            'startAt': startAt,
            'maxResults': maxResults
        }
        r_json = self._get_json('user/assignable/multiProjectSearch', params)
        users = [User(self._options, self._session, raw_user_json) for raw_user_json in r_json]
        return users

    def search_assignable_users_for_issues(self, username, project=None, issueKey=None, expand=None, startAt=0, maxResults=50):
        """
        Get a list of user Resources that match the search string for assigning or creating issues.

        This method is intended to find users that are eligible to create issues in a project or be assigned
        to an existing issue. When searching for eligible creators, specify a project. When searching for eligible
        assignees, specify an issue key.

        Keyword arguments:
        project -- filter returned users by permission in this project (expected if a result will be used to create
        an issue)
        issueKey -- filter returned users by this issue (expected if a result will be used to edit this issue)
        expand -- extra information to fetch inside each resource
        startAt -- index of the first user to return
        maxResults -- maximum number of users to return
        """
        params = {
            'username': username,
            'startAt': startAt,
            'maxResults': maxResults,
        }
        if project is not None:
            params['project'] = project
        if issueKey is not None:
            params['issueKey'] = issueKey
        if expand is not None:
            params['expand'] = expand
        r_json = self._get_json('user/assignable/search', params)
        users = [User(self._options, self._session, raw_user_json) for raw_user_json in r_json]
        return users

    # non-resource
    def user_avatars(self, username):
        """Get a dict of avatars for the specified user."""
        return self._get_json('user/avatars', params={'username': username})

    def create_temp_user_avatar(self, user, filename, size, avatar_img):
        pass

    def confirm_user_avatar(self, user, **kw):
        pass

    def search_users(self, user, startAt=0, maxResults=50):
        """
        Get a list of user Resources that match the specified search string.

        Keyword arguments:
        startAt -- index of the first user to return
        maxResults -- maximum number of users to return
        """
        params = {
            'username': user,
            'startAt': startAt,
            'maxResults': maxResults
        }
        r_json = self._get_json('user/search', params)
        users = [User(self._options, self._session, raw_user_json) for raw_user_json in r_json]
        return users

    def search_allowed_users_for_issue(self, user, issueKey=None, projectKey=None, startAt=0, maxResults=50):
        params = {
            'username': user,
            'startAt': startAt,
            'maxResults': maxResults,
        }
        if issueKey is not None:
            params['issueKey'] = issueKey
        if projectKey is not None:
            params['projectKey'] = projectKey
        r_json = self._get_json('user/viewissue/search', params)
        users = [User(self._options, self._session, raw_user_json) for raw_user_json in r_json]
        return users

### Versions

    def create_version(self, **kw):
        pass

    def move_version(self, id, **kw):
        pass

    def version(self, id, expand=None):
        """
        Get a version Resource that matches the specified ID.

        Keyword arguments:
        expand -- extra information to fetch inside each resource
        """
        version = Version(self._options, self._session)
        params = {}
        if expand is not None:
            params['expand'] = expand
        version.find(id, params=params)
        return version

    def version_count_related_issues(self, id):
        """Get a dict of the counts of issues fixed and affected by the version with the specified ID."""
        r_json = self._get_json('version/' + id + '/relatedIssueCounts')
        del r_json['self']   # this isn't really an addressable resource
        return r_json

    def version_count_unresolved_issues(self, id):
        """Get the number of unresolved issues for the version with the specified ID."""
        return self._get_json('version/' + id + '/unresolvedIssueCount')['issuesUnresolvedCount']

### Session authentication

    def session(self):
        """Get a dict of the current authenticated user's session information."""
        url = '{server}/rest/auth/1/session'.format(**self._options)
        r = self._session.get(url)
        self._raise_on_error(r)

        user = User(self._options, self._session, json.loads(r.text))
        return user

    def kill_session(self):
        """Destroy the session of the current authenticated user."""
        url = self._options['server'] + '/rest/auth/1/session'
        r = self._session.delete(url)
        self._raise_on_error(r)

### Websudo

    def kill_websudo(self):
        """Destroy the user's current WebSudo session."""
        url = self._options['server'] + '/rest/auth/1/websudo'
        r = self._session.delete(url)
        self._raise_on_error(r)

### Utilities

    def _create_http_basic_session(self, username, password):
        url = self._options['server'] + '/rest/auth/1/session'
        payload = {
            'username': username,
            'password': password
        }

        verify = self._options['server'].startswith('https')
        self._session = requests.session(headers={'content-type': 'application/json'}, verify=verify)
        r = self._session.post(url, data=json.dumps(payload))
        self._raise_on_error(r)

    def _create_oauth_session(self, oauth):
        raise NotImplementedError("oauth support isn't implemented yet")

    def _get_url(self, path):
        return '{}/rest/api/2/{}'.format(self._options['server'], path)

    def _get_json(self, path, params=None):
        url = self._get_url(path)
        r = self._session.get(url, params=params)
        self._raise_on_error(r)

        r_json = json.loads(r.text)
        return r_json

    def _find_for_resource(self, resource_cls, ids, expand=None):
        resource = resource_cls(self._options, self._session)
        params = {}
        if expand is not None:
            params['expand'] = expand
        resource.find(ids, params)
        return resource

    def _raise_on_error(self, r):
        if r.status_code >= 400:
            raise JIRAError("Couldn't complete server call", r.status_code, r.url)
