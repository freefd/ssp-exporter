''' Aruba Cloud exporter module '''

from dataclasses import dataclass, InitVar

import json
import requests

from logger import Logger

@dataclass
class ArubaCloud:
    ''' Aruba Cloud exporter class '''

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
        self._lgr.logger.info(
            '%s: Request current balance from api.dc3.computing.cloud.it',
            self.identifier)

        try:
            response = session_object.post(
                'https://api.dc3.computing.cloud.it/WsEndUser/v2.9/'
                'WsEndUser.svc/json/GetCredit',
                data=json.dumps({
                    'Username': self.identifier,
                    'Password': self.password
                }),
                headers={
                    'Content-Type': 'application/json',
                    'User-Agent': self.user_agent
                },
                verify=bool(self.tls_verify)
            )

        except requests.exceptions.RequestException as connection_error:
            self._lgr.logger.error(
                '%s: Cannot connect to api.dc3.computing.cloud.it: %s',
                self.identifier, connection_error)
            self.last_balance = self.messages['connection_error']

        if response.status_code == requests.codes.ok: # pylint: disable=no-member
            if response.json().get('Value').get('Value'):

                balance = abs(float(response.json().get('Value').get('Value')))

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
                self._lgr.logger.error('%s: Cannot extract balance value',
                    self.identifier)
                self.last_balance = self.messages['parsing_error']

        else:
            self._lgr.logger.error('%s: Cannot connect to Self Service Portal',
                self.identifier)
            self.last_balance = self.messages['no_answer']
