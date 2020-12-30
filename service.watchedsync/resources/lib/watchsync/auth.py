#
#
# Copyright 2019-2020 CSS
#
# This software is unpublished work which is proprietary to CSS.
# Any distribution is strictly forbidden
#
#

""" Authenticate functions for the client device """

import os
import sys
import logging
import threading
import requests
import base64
import json
from datetime import datetime, timedelta
from time import sleep
import boto3
import botocore.exceptions
import pytz
import xbmc
import xbmcaddon

LIB_RESOURCES_PATH = xbmc.translatePath(os.path.join(xbmcaddon.Addon().getAddonInfo('path').decode('utf-8'), 'resources'.decode('utf-8'), 'lib'.decode('utf-8')))
sys.path.append(LIB_RESOURCES_PATH)

""" Local module imports - need to be after LIB_RESOURCES_PATH """
from watchsync.logging import KodiLog
from watchsync.utils import *


""" Configuration Variables """
_auth_issuer = u'https://patxbgvzub.execute-api.eu-west-1.amazonaws.com'
_request_timeout = 15.0
""" End of Configuration Variables """

log = KodiLog(__file__, __name__)


class AuthSessionError(Exception):
    pass


class AuthSessionClientError(AuthSessionError):
    pass


class AuthSessionServerError(AuthSessionError):
    pass


class AuthSession(object):
    """ Authentication Session class

        To be used by other modules to handle token request & refresh
    """
    def __init__(self, client_id=None, client_secret=None, scope=None):
        self.issuer_url = self._cleanse_issuer_string(_auth_issuer)
        self.session = requests.Session()

        self.client_id = client_id or getSettingAsString('auth_client_id')
        self.client_secret = client_secret or getSettingAsString('auth_client_secret')
        self.scope = scope

        self.connected = False
        self.token_endpoint_url = None
        self.current_bearer_token = None
        self.current_bearer_token_expire_dt = None

        self.headers = {'user-agent': xbmc.getUserAgent()}

        self.update_lock = threading.Lock()

        self._set_auth_params()
        self.get_authorization_token()

    def _set_auth_params(self):
        """ Set the auth (HTTP Basic Auhtorization) params to use """
        with self.update_lock:
            if self.client_id and self.client_secret:
                self.session.auth = (self.client_id, self.client_secret)

    def _cleanse_issuer_string(self, issuer):
        """ Need to remove the last slash if present """
        if issuer[-1] == u'/':
            return issuer[:-1]
        else:
            return issuer

    def _get_token_endpoint(self):
        """ Retrieve token endpoint """
        if not self.token_endpoint_url:
            openid_url = self.issuer_url + '/.well-known/openid-configuration'
            result = requests.get(openid_url,
                                  headers=self.headers,
                                  timeout=_request_timeout)
            result.raise_for_status()
            result_json = result.json()
            self.token_endpoint_url = result_json['token_endpoint']

    def _request_token(self):
        """ Attempt request of token from token endpoint """
        self._get_token_endpoint()
        if self.token_endpoint_url:
            payload = {
                'grant_type': 'client_credentials',
                'client_id': self.client_id,
                'scope': self.scope
            }
            result = self.session.post(self.token_endpoint_url,
                                       headers=self.headers,
                                       timeout=_request_timeout,
                                       data=payload)

            if 400 <= result.status_code < 500:
                # Problem when requesting
                raise AuthSessionClientError("{} Client error during token authentication: {}".format(result.status_code, result.text))

            if 500 <= result.status_code < 600:
                # Unauthorised or Forbidden. Repeating this is not going to work without changing an input
                raise AuthSessionServerError("{} Server error during token authentication: {}".format(result.status_code, result.text))

            try:
                result.raise_for_status()
            except requests.RequestException as e:
                raise AuthSessionServerError("{} Server error during token authentication: {}".format(result.status_code, e))

            result_json = result.json()
            if "token_type" in result_json and result_json['token_type'].lower() == "bearer":
                return result_json['access_token']

        return None

    def base64urldecode(self, arg):
        filtered = arg.replace("-", "+").replace("_", "/")
        padded = filtered + "=" * ((len(filtered) * -1) % 4)
        return base64.b64decode(padded)

    def _get_expire_datetime_from_token(self, token):
        """ Return expiration time (exp) from token and return in Python datetime format """
        try:
            split_token = token.split('.')
            payload = split_token[1]
            decoded_payload = self.base64urldecode(payload)
            payload_obj = json.loads(decoded_payload)
            return datetime.utcfromtimestamp(payload_obj['exp'])
        except:
            return None

    def set_scope(self, scope):
        """ Set scope request """
        self.scope = scope

    def get_authorization_token(self):
        if not self.client_id:
            raise AuthSessionClientError("Missing client_id")

        if not self.client_secret:
            raise AuthSessionClientError("Missing client_secret")

        if not self.scope:
            raise AuthSessionClientError("Missing scope")

        with self.update_lock:
            if not self.current_bearer_token:

                # Fetch new token
                self.current_bearer_token = self._request_token()
                self.current_bearer_token_expire_dt = self._get_expire_datetime_from_token(self.current_bearer_token)

            if datetime.utcnow() > (self.current_bearer_token_expire_dt - timedelta(minutes=2)):

                # Token will expire shortly or has expired - fetch new token
                self.refresh_token()

                # Fetch new token
                self.current_bearer_token = self._request_token()
                self.current_bearer_token_expire_dt = self._get_expire_datetime_from_token(self.current_bearer_token)

        return self.current_bearer_token

    def get_authorization_header(self):
        return u"Bearer {}".format(self.get_authorization_token())

    def refresh_token(self):
        """ Refresh token on next call to get_authorization_header """
        self.current_bearer_token = None
        self.current_bearer_token_expire_dt = None


class AuthBoto3Direct(object):
    """ Authentication class to enable direct access to AWS through boto3

        Enables direct access to AWS services using AssumeRoleWithWebIdentity
        authentication while periodically refreshing token in background

        To be used by other modules to interface with AWS services
    """
    def __init__(self, auth_session, assume_role_arn, role_session_name, session_duration=3600):
        self._auth_session = auth_session
        self._sts_credentials = None
        self._assume_role_arn = assume_role_arn
        self._role_session_name = role_session_name
        self._session_duration = session_duration
        self._sts_token_expires = datetime.now(tz=pytz.utc) - timedelta(minutes=2)

        # Get temporary access token to AWS
        self._refresh_session_access_tokens()

    def _get_aws_security_token(self):
        # Web token will raise it's own exceptions
        web_token = self._auth_session.get_authorization_token()
        try:
            sts_service = boto3.client('sts')
            credentials = sts_service.assume_role_with_web_identity(
                RoleArn=self._assume_role_arn,
                RoleSessionName=self._role_session_name,
                DurationSeconds=self._session_duration,
                WebIdentityToken=web_token
            )
            self._sts_credentials = credentials['Credentials']

        except botocore.exceptions.ClientError as e:
            raise AuthSessionClientError("Client error during AWS security token authentication: {}".format(e))

    def _refresh_session_access_tokens(self):
        """
            Refresh the AWS session (if required)
        """
        if datetime.now(tz=pytz.utc) > self._sts_token_expires:

            # Token will expire within the next 2 mins or has already expired - fetch new token
            self._get_aws_security_token()
            self._sts_token_expires = self._sts_credentials['Expiration'] - timedelta(minutes=2)
            log.debug("AWS STS token refreshed. New token expires {}".format(self._sts_token_expires))

    def get_resource_access_arguments(self):
        """
            Return keyword arguments to pass into boto3 resource constructor

        :return dict:fossil
        """
        # resource(service_name, region_name=None, api_version=None, use_ssl=True, verify=None, endpoint_url=None,
        #          aws_access_key_id=None, aws_secret_access_key=None, aws_session_token=None, config=None)[source]
        self._refresh_session_access_tokens()
        access_kwargs = {
            'aws_access_key_id': self._sts_credentials['AccessKeyId'],
            'aws_secret_access_key': self._sts_credentials['SecretAccessKey'],
            'aws_session_token': self._sts_credentials['SessionToken']
        }
        return access_kwargs

    def get_client_access_arguments(self):
        """
            Return keyword arguments to pass into boto3 client constructor

        :return dict:
        """
        # client(service_name, region_name=None, api_version=None, use_ssl=True, verify=None, endpoint_url=None,
        #        aws_access_key_id=None, aws_secret_access_key=None, aws_session_token=None, config=None)
        return self.get_resource_access_arguments()


if __name__ == '__main__':
    sys.exit("This module is designed to be imported. It should not be called directly")