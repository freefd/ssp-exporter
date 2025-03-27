"""
T2 Russia B2C exporter module

ATTENTION!
THIS MODULE STOPPED WORKING FROM MID-2024 DUE TO INTRODUCED 2FA WITH EMAIL/SMS
"""

from dataclasses import dataclass, InitVar

import json
import requests

from lxml import html
from logger import Logger

@dataclass
class T2RussiaB2C:
    """ T2 Russia exporter class """

    class_type: str = 'provider'
    messages: list[str] = None
    user_agent: str = None
    identifier: str = None
    labels: dict[str, (bool, int, float, str)] = None
    password: str = None
    disabled: bool = True
    tls_verify: bool = False
    poll_interval: int = 3600
    last_balance: float = None
    log_level: InitVar[int] = 20

    def __post_init__(self, log_level: int = 20) -> None:
        self._lgr = Logger(
            log_level=log_level, class_name=self.__class__.__name__)

    def __str__(self) -> str:
        """ Human readable print of the current class """

        return_obj = {}

        for key, value in self.__dict__.items():
            if isinstance(value, bool | int | float | str | dict | list | None):
                return_obj[key] = {
                    'value': value,
                    'type': type(value).__name__
                }

        return json.dumps(return_obj, ensure_ascii=False, indent=4)

    def as_dict(self) -> dict:
        """ Return current class as a dictionary """

        self_dict = {}

        for key, value in self.__dict__.items():
            if isinstance(value, bool | int | float | str | dict | list | None):
                self_dict[key]=value

        return self_dict

    def get_balance(self) -> float | int:
        """ Return last balance """

        return self.last_balance

    def update_balance(self) -> None:
        """ Collect current balance for identifier """

        if self.disabled is True:
            self._lgr.logger.warning('%s: Identifier disabled',
                self.identifier)
            self.last_balance = self.messages['disabled']

        session_object = requests.Session()
        self._lgr.logger.info(
            '%s: Request CSRF token and/or Session Cookie from msk.t2.ru',
            self.identifier)

        try:
            response = session_object.get(
                'https://msk.t2.ru/lk',
                headers={
                    'User-Agent': self.user_agent
                },
                verify=bool(self.tls_verify),
            )
        except requests.exceptions.RequestException as connection_error:
            self._lgr.logger.error('%s: Cannot connect to msk.t2.ru: %s',
                self.identifier, connection_error)
            self.last_balance = self.messages['connection_error']

        if response.status_code == requests.codes.ok: # pylint: disable=no-member
            cookies_dict = session_object.cookies.get_dict()

            request_headers = {
                'Content-Type': 'application/x-www-form-urlencoded',
                'Authority': 'msk.t2.ru',
                'x-requested-with': 'XMLHttpRequest',
                'User-Agent': self.user_agent
            }

            if 'csrf-token-name' in response.text:

                tree = html.fromstring(response.text)

                try:
                    csrf_token_name = tree.xpath(
                        '//meta[@name="csrf-token-name"]/@content')[0]
                    csrf_token_value = tree.xpath(
                        '//meta[@name="csrf-token-value"]/@content')[0]
                except ValueError as err:
                    self._lgr.logger.warning(
                        '%s: Cannot find CSRF token name and/or value: %s',
                        self.identifier, err)
                    self.last_balance = self.messages['cannot_proceed']

                cookies_dict.update(
                    {
                        'csrf-token-name': csrf_token_name,
                        'csrf-token-value': csrf_token_value
                    }
                )

                request_headers.update(
                    {
                        'x-csrftoken': csrf_token_value
                    }
                )

                self._lgr.logger.debug('%s: Collected СSRF token %s',
                    self.identifier, csrf_token_value)

            if 'session-cookie' in cookies_dict:
                self._lgr.logger.debug('%s: Collected session cookie: %s',
                    self.identifier, cookies_dict['session-cookie'])
                self._lgr.logger.info('%s: Sign in to msk.t2.ru',
                    self.identifier)

                try:
                    response = session_object.post(
                        'https://msk.t2.ru/auth/realms/tele2-b2c/protocol/'
                        'openid-connect/token',
                        cookies=cookies_dict,
                        data={
                            'username': self.identifier,
                            'password': self.password,
                            'client_id': 'digital-suite-web-app',
                            'grant_type': 'password',
                            'password_type': 'password'
                        },
                        headers=request_headers,
                        verify=bool(self.tls_verify)
                    )
                except requests.exceptions.RequestException as connection_error:
                    self._lgr.logger.error(
                        '%s: Cannot connect to msk.t2.ru: %s',
                        self.identifier, connection_error)
                    self.last_balance = self.messages['connection_error']

                if response.status_code == requests.codes.ok: # pylint: disable=no-member
                    self._lgr.logger.info('%s: Obtain access token',
                        self.identifier)

                    if response.json().get('access_token'):
                        access_token = response.json().get('access_token')

                        self._lgr.logger.debug('%s: Extracted access token: %s',
                            self.identifier, access_token)
                        self._lgr.logger.info(
                            '%s: Request current balance from msk.t2.ru',
                            self.identifier)

                        try:
                            response = session_object.get(
                                f'https://msk.t2.ru/api/subscribers/'
                                f'{self.identifier}/balance',
                                headers={
                                    'Authorization': f'Bearer {access_token}',
                                    'User-Agent': self.user_agent
                                },
                                verify=bool(self.tls_verify)
                            )
                        except requests.exceptions.RequestException \
                                as connection_error:
                            self._lgr.logger.error(
                                '%s: Cannot connect to msk.t2.ru: %s',
                                self.identifier, connection_error)
                            self.last_balance = \
                                self.messages['connection_error']

                        if response.status_code == requests.codes.ok: # pylint: disable=no-member
                            if response.json().get('meta').get(
                                    'status') == 'OK':

                                balance = response.json().get(
                                    'data').get('value')

                                if (balance is not None
                                    and isinstance(balance, (int, float))):
                                    self._lgr.logger.info(
                                        '%s: Balance has been collected',
                                        self.identifier)
                                    self._lgr.logger.debug(
                                        '%s: Balance is %s',
                                        self.identifier, balance)

                                    self.last_balance = float(balance)

                                else:
                                    self._lgr.logger.error(
                                        '%s: Cannot extract balance value',
                                        self.identifier)

                                    self.last_balance = \
                                        self.messages['parsing_error']

                            else:
                                self._lgr.logger.error(
                                    '%s: Cannot extract balance value',
                                    self.identifier)
                                self.last_balance = \
                                    self.messages['parsing_error']

                        else:
                            self._lgr.logger.error(
                                '%s: Cannot load page with balance: %s',
                                self.identifier, response.status_code)
                            self.last_balance = self.messages['cannot_proceed']

                    else:
                        self._lgr.logger.error(
                            '%s: Cannot extract access token',
                            self.identifier)
                        self.last_balance = self.messages['cannot_proceed']

                else:
                    self._lgr.logger.error('%s: Cannot obtain access token: %s',
                        self.identifier, response.status_code)
                    self.last_balance = self.messages['cannot_proceed']

            else:
                self._lgr.logger.error('%s: Cannot obtain session cookie',
                    self.identifier)
                self.last_balance = self.messages['cannot_proceed']

        else:
            self._lgr.logger.error('%s: Cannot connect to Self Service Portal',
                self.identifier)
            self.last_balance = self.messages['no_answer']
