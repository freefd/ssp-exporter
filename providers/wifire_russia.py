""" Wifire Russia exporter module """

from dataclasses import dataclass, InitVar

import json
import requests

from logger import Logger

@dataclass
class WifireRussia:
    """ Wifire Russia exporter class """

    class_type: str = 'provider'
    messages: list[str] = None
    user_agent: str = None
    identifier: str = None
    labels: dict[str, (str, int, float)] = None
    password: str = None
    disabled: bool = False
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
            self._lgr.logger.warning('%s: Identifier disabled', self.identifier)
            self.last_balance = self.messages['disabled']

        session_object = requests.Session()
        self._lgr.logger.info('%s: Request session from my.wifire.ru',
            self.identifier)

        try:
            response = session_object.get(
                f'https://my.wifire.ru/api/v1/get-way?'
                f'accountNumber={self.identifier}',
                headers={
                    'User-Agent': self.user_agent
                },
                verify=bool(self.tls_verify)
            )
        except requests.exceptions.RequestException as connection_error:
            self._lgr.logger.error('%s: Cannot connect to my.wifire.ru: %s',
                self.identifier, connection_error)
            self.last_balance = self.messages['connection_error']

        if response.status_code == requests.codes.ok: # pylint: disable=no-member

            self._lgr.logger.info('%s: Sign in to my.wifire.ru',
                self.identifier)

            try:
                response = session_object.post(
                    'https://my.wifire.ru/api/v2/login',
                    json={
                        'accountNumber': self.identifier,
                        'password': self.password,
                        'captchaCode': '',
                        'save': 'true'
                    },
                    headers={
                        'User-Agent': self.user_agent
                    },
                    verify=bool(self.tls_verify)
                )
            except requests.exceptions.RequestException as connection_error:
                self._lgr.logger.error('%s: Cannot connect to my.wifire.ru: %s',
                    self.identifier, connection_error)
                self.last_balance = self.messages['connection_error']

            if (response.status_code == requests.codes.ok and  # pylint: disable=no-member
                    response.json().get('resultCode') == 0):

                self._lgr.logger.info(
                    '%s: Request current balance from my.wifire.ru',
                    self.identifier)

                try:
                    response = session_object.get(
                        'https://my.wifire.ru/api/v1/get-balance',
                        headers={
                            'User-Agent': self.user_agent
                        },
                        verify=bool(self.tls_verify)
                    )
                except requests.exceptions.RequestException as connection_error:
                    self._lgr.logger.error(
                        '%s: Cannot connect to my.wifire.ru: %s',
                        self.identifier, connection_error)
                    self.last_balance = self.messages['connection_error']

                if response.status_code == requests.codes.ok: # pylint: disable=no-member
                    if response.json().get('statusCode') == 0:
                        balance = response.json().get('accountBalance')

                        if (balance is not None
                            and isinstance(balance, (int, float))):
                            self._lgr.logger.info(
                                '%s: Balance has been collected',
                                self.identifier)
                            self._lgr.logger.debug('%s: Balance is %s',
                                self.identifier, balance)
                            self.last_balance = float(balance)

                            self._lgr.logger.info(
                                '%s: Logging out from my.wifire.ru',
                                self.identifier)

                            try:
                                response = session_object.get(
                                    'https://my.wifire.ru/logout',
                                    headers={
                                        'User-Agent': self.user_agent
                                    },
                                    verify=bool(self.tls_verify)
                                )
                            except requests.exceptions.RequestException \
                                    as connection_error:
                                self._lgr.logger.error(
                                    '%s: Cannot logout from my.wifire.ru: %s',
                                    self.identifier, connection_error)
                                self.last_balance = \
                                    self.messages['connection_error']

                        else:
                            self._lgr.logger.error(
                                '%s: Cannot extract balance value',
                                self.identifier)
                            self.last_balance = self.messages['parsing_error']

                    else:
                        self._lgr.logger.error(
                            '%s: Cannot extract balance value',
                            self.identifier)
                        self.last_balance = self.messages['parsing_error']

                else:
                    self._lgr.logger.error(
                        '%s: Cannot load page with balance: %s',
                        self.identifier, response.status_code)
                    self.last_balance = self.messages['cannot_proceed']

            else:
                self._lgr.logger.error(
                    '%s: Cannot log in to Self Service Portal: %s',
                    self.identifier, response.status_code)
                self.last_balance = self.messages['cannot_proceed']

        else:
            self._lgr.logger.error('%s: Cannot connect to Self Service Portal',
                self.identifier)
            self.last_balance = self.messages['no_answer']
