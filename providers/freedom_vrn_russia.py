""" Freedom-VRN Russia exporter module """

from dataclasses import dataclass, InitVar

import json
import requests

from logger import Logger

@dataclass
class FreedomVrnRussia:
    """ Freedom-VRN Russia exporter class """

    class_type: str = 'provider'
    messages: list[str] = None
    user_agent: str = None
    identifier: str = None
    labels: dict[str, (bool, int, float, str)] = None
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
            self._lgr.logger.warning('%s: Identifier disabled',
                self.identifier)
            self.last_balance = self.messages['disabled']

        session_object = requests.Session()
        self._lgr.logger.info('%s: Request session from lk-api.freedom-vrn.ru',
            self.identifier)

        try:
            response = session_object.post(
                'https://lk-api.freedom-vrn.ru/lk/api/v1',
                headers={
                    'User-Agent': self.user_agent
                },
                json={
                    'method': 'auth',
                    'params': {
                        'username': self.identifier,
                        'password': self.password
                    }
                },
                verify=bool(self.tls_verify)
            )

        except requests.exceptions.RequestException as connection_error:
            self._lgr.logger.error(
                '%s: Cannot connect to lk-api.freedom-vrn.ru: %s',
                self.identifier, connection_error)
            self.last_balance = self.messages['connection_error']

        if (response.status_code == requests.codes.ok
            and response.json().get('error') == 0 and
            len(response.json().get('token')) > 0): # pylint: disable=no-member

            access_token = response.json().get('token')

            self._lgr.logger.info(
                '%s: Request current balance from lk-api.freedom-vrn.ru',
                self.identifier)

            try:
                response = session_object.post(
                    'https://lk-api.freedom-vrn.ru/lk/api/v1',
                    headers={
                        'Ic-Token': access_token,
                        'User-Agent': self.user_agent
                    },
                    json={
                        'method': 'getClient',
                        'params': {}
                    },
                    verify=bool(self.tls_verify)
                )
            except requests.exceptions.RequestException as connection_error:
                self._lgr.logger.error(
                    '%s: Cannot connect to lk-api.freedom-vrn.ru: %s',
                    self.identifier, connection_error)
                self.last_balance = self.messages['connection_error']

            if (response.status_code == requests.codes.ok and
                'client' in response.json() and
                'billing' in response.json().get('client') and
                'balance' in response.json().get('client').get('billing')): # pylint: disable=no-member
                balance = response.json().get('client').get(
                                                    'billing').get('balance')

                if balance is not None and isinstance(balance, (int, float)):
                    self._lgr.logger.info('%s: Balance has been collected',
                        self.identifier)
                    self._lgr.logger.debug('%s: Balance is %s',
                        self.identifier, balance)

                    self.last_balance = float(balance)

                else:
                    self._lgr.logger.error('%s: Cannot extract balance value',
                        self.identifier)

                    self.last_balance = self.messages['parsing_error']

            else:
                self._lgr.logger.error('%s: Cannot load page with balance: %s',
                    self.identifier, response.status_code)
                self.last_balance = self.messages['cannot_proceed']

        else:
            self._lgr.logger.error('%s: Cannot connect to Self Service Portal',
                self.identifier)
            self.last_balance = self.messages['no_answer']
