"""Custom adaption of connection module from python_irodsclient 2.2.0

"""
from __future__ import absolute_import
import socket
import logging
import datetime
import irods.auth
import re
from irods.connection import Connection

PAM_PW_ESC_PATTERN = re.compile(r'([@=&;])')


from irods.message import (
    iRODSMessage, Error, GetTempPasswordOut)
import irods.exception as ex
from irods.message import (PamAuthRequest, PamAuthRequestOut)

from irods import (
    AUTH_USER_KEY, AUTH_PWD_KEY, AUTH_TTL_KEY,
    NATIVE_AUTH_SCHEME,
    PAM_AUTH_SCHEME, PAM_AUTH_SCHEMES)

from irods.api_number import api_number

logger = logging.getLogger(__name__)

class Connection2(Connection):

    DISALLOWING_PAM_PLAINTEXT = True

    def __init__(self, pool, account):

        self.pool = pool
        self.socket = None
        self.account = account
        self._client_signature = None
        self._server_version = self._connect()
        self._disconnected = False

        scheme = self.account._original_authentication_scheme

        # These variables are just useful diagnostics.  The login_XYZ() methods should fail by
        # raising exceptions if they encounter authentication errors.
        auth_module = auth_type = ''

        # EvW: we changed the original code to just legacy login
        # use legacy (iRODS pre-4.3 style) authentication
        auth_type = scheme
        if scheme == NATIVE_AUTH_SCHEME:
            self._login_native()
        elif scheme in PAM_AUTH_SCHEMES:
            self.native_password = self._login_pam().result_
        else:
            auth_type = None

        if not auth_type:
            msg = "Authentication failed: scheme = {scheme!r}, auth_type = {auth_type!r}, auth_module = {auth_module!r}, ".format(**locals())
            raise ValueError(msg)

        self.create_time = datetime.datetime.now()
        self.last_used_time = self.create_time
   
            
    def _login_pam(self):
        """Do PAM login to iRODS

        Raises:
            PlainTextPAMPasswordError: _description_
            RuntimeError: _description_

        Returns:
            Pam_Response_Class: _description_
            
        We are mainly interested in the result_ field of
        the return value, that contains the temporary native iRODS password
        """        
        time_to_live_in_hours = 24
        # For certain characters in the pam password, if they need escaping with '\' then do so.
        new_pam_password = PAM_PW_ESC_PATTERN.sub(lambda m: '\\'+m.group(1), self.account.password)

        # Generate a new PAM password.
        ctx_user = '%s=%s' % (AUTH_USER_KEY, self.account.client_user)
        ctx_pwd = '%s=%s' % (AUTH_PWD_KEY, new_pam_password)
        ctx_ttl = '%s=%s' % (AUTH_TTL_KEY, str(time_to_live_in_hours))

        ctx = ";".join([ctx_user, ctx_pwd, ctx_ttl])

        if type(self.socket) is socket.socket:
            if getattr(self,'DISALLOWING_PAM_PLAINTEXT',True):
                raise PlainTextPAMPasswordError

        message_body = PamAuthRequest( pamUser = self.account.client_user,
                                        pamPassword = self.account.password,
                                        timeToLive = time_to_live_in_hours)

        auth_req = iRODSMessage(
            msg_type='RODS_API_REQ',
            msg=message_body,
            int_info=api_number['PAM_AUTH_REQUEST_AN']
        )

        self.send(auth_req)
        # Getting the new password
        try:
            output_message = self.recv()
        except irods.exception.PAM_AUTH_PASSWORD_INVALID_TTL as exc:
            # TODO (#480): In Python3 will be able to do: 'raise RuntimeError(...) from exc' for more succinct error messages
            raise RuntimeError('Client-configured TTL is outside server parameters (password min and max times)')

        Pam_Response_Class = PamAuthRequestOut

        auth_out = output_message.get_main_message( Pam_Response_Class )

        self.disconnect()
        self._connect()

        self._login_native(password = auth_out.result_)
       
        return auth_out