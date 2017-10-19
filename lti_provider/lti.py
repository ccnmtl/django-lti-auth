from django.conf import settings
from pylti.common import (
    LTIException, LTINotInSessionException, LTI_SESSION_KEY,
    verify_request_common, LTIRoleException, LTI_ROLES, LTI_PROPERTY_LIST)

from lti_provider.models import LTICourseContext


LTI_PROPERTY_LIST_EX = [
    'custom_canvas_user_login_id',
    'context_title',
    'lis_course_offering_sourcedid',
    'custom_canvas_api_domain'
]


class LTI(object):
    """
    LTI Object represents abstraction of current LTI session. It provides
    callback methods and methods that allow developer to inspect
    LTI basic-launch-request.

    This object is instantiated by the LTIMixin
    """

    def __init__(self, request_type, role_type):
        self.request_type = request_type
        self.role_type = role_type

    def clear_session(self, request):
        """
        Invalidate the session
        """
        request.session.flush()

    def initialize_session(self, request, params):
        # All good to go, store all of the LTI params into a
        # session dict for use in views
        for prop in LTI_PROPERTY_LIST:
            if params.get(prop, None):
                request.session[prop] = params[prop]

        for prop in LTI_PROPERTY_LIST_EX:
            if params.get(prop, None):
                request.session[prop] = params[prop]

    def verify(self, request):
        """
        Verify if LTI request is valid, validation
        depends on arguments

        :raises: LTIException
        """
        if self.request_type == 'session':
            self._verify_session(request)
        elif self.request_type == 'initial':
            self._verify_request(request)
        elif self.request_type == 'any':
            self._verify_any(request)
        else:
            raise LTIException('Unknown request type')

        return True

    def _verify_any(self, request):
        """
        Verify that request is in session or initial request

        :raises: LTIException
        """
        try:
            self._verify_session(request)
        except LTINotInSessionException:
            self._verify_request(request)

    @staticmethod
    def _verify_session(request):
        """
        Verify that session was already created

        :raises: LTIException
        """
        if not request.session.get(LTI_SESSION_KEY, False):
            raise LTINotInSessionException('Session expired or unavailable')

    def _verify_request(self, request):
        """
        Verify initial LTI request

        :raises: LTIException is request validation failed
        """
        if request.method == 'POST':
            params = dict(request.POST.iteritems())
        else:
            params = dict(request.GET.iteritems())

        try:
            verify_request_common(self.consumers(),
                                  request.build_absolute_uri(),
                                  request.method, request.META,
                                  params)

            self._validate_role()

            self.clear_session(request)
            self.initialize_session(request, params)
            request.session[LTI_SESSION_KEY] = True
            return True
        except LTIException:
            self.clear_session(request)
            request.session[LTI_SESSION_KEY] = False
            raise

    def consumers(self):
        """
        Gets consumer's map from config
        :return: consumers map
        """
        config = getattr(settings, 'PYLTI_CONFIG', dict())
        consumers = config.get('consumers', dict())
        return consumers

    def _validate_role(self):
        """
        Check that user is in accepted/specified role

        :exception: LTIException if user is not in roles
        """
        if self.role_type != u'any':
            if self.role_type in LTI_ROLES:
                role_list = LTI_ROLES[self.role_type]

                # find the intersection of the roles
                roles = set(role_list) & set(self.user_roles())
                if len(roles) < 1:
                    raise LTIRoleException('Not authorized.')
            else:
                raise LTIException("Unknown role {}.".format(self.role_type))

        return True

    def custom_course_context(self, request):
        """
        Returns the custom LTICourseContext id as provided by LTI

        throws: KeyError or ValueError or LTICourseContext.DoesNotExist
        :return: context -- the LTICourseContext instance or None
        """
        return LTICourseContext.objects.get(
            enable=True,
            uuid=self.custom_course_context(request))

    def canvas_domain(self, request):
        return request.session.get('custom_canvas_api_domain', None)

    def consumer_user_id(self, request):
        return "%s-%s" % \
            (self.oauth_consumer_key(request), self.user_id(request))

    def course_context(self, request):
        return request.session.get('context_id', None)

    def course_title(self, request):
        return request.session.get('context_title', None)

    def is_administrator(self, request):
        return 'administrator' in request.session.get('roles', '').lower()

    def is_instructor(self, request):
        roles = request.session.get('roles', '').lower()
        return 'instructor' in roles or 'staff' in roles

    def lis_outcome_service_url(self, request):
        return request.session.get('lis_outcome_service_url', None)

    def lis_result_sourcedid(self, request):
        return request.session.get('lis_result_sourcedid', None)

    def oauth_consumer_key(self, request):
        return request.session.get('oauth_consumer_key', None)

    def user_email(self, request):
        return request.session.get('lis_person_contact_email_primary', None)

    def user_fullname(self, request):
        name = request.session.get('lis_person_name_full', None)
        if not name or len(name) < 1:
            name = self.user_id(request)

        return name or ''

    def user_id(self, request):
        return request.session.get('user_id', None)

    def user_identifier(self, request):
        return request.session.get('custom_canvas_user_login_id', None)

    def user_roles(self, request):  # pylint: disable=no-self-use
        """
        LTI roles of the authenticated user

        :return: roles
        """
        roles = request.session.get('roles', None)
        if not roles:
            return []
        return roles.lower().split(',')

    def sis_course_id(self, request):
        return request.session.get('lis_course_offering_sourcedid', None)
