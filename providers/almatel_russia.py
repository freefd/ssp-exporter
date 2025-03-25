""" Almatel Russia exporter module """

from dataclasses import dataclass, InitVar

import locale
import json
import requests

from lxml import html
from logger import Logger

locale.setlocale(locale.LC_NUMERIC, 'ru_RU.UTF-8')

@dataclass
class AlmatelRussia:
    """ Almatel Russia exporter class """

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
        self._lgr.logger.info('%s: Sign in to almatel.ru', self.identifier)
        try:
            response = session_object.post(
                'https://almatel.ru/lk/login.php',
                data={
                    'login': self.identifier,
                    'password': self.password
                },
                headers={
                    'Referer': 'https://almatel.ru/lk/login.php',
                    'X-Requested-With': 'XMLHttpRequest',
                    'User-Agent': self.user_agent
                },
                verify=bool(self.tls_verify)
            )
        except requests.exceptions.RequestException as connection_error:
            self._lgr.logger.error('%s: Cannot connect to almatel.ru: %s',
                self.identifier, connection_error)
            self.last_balance = self.messages['connection_error']

        if response.status_code == requests.codes.ok: # pylint: disable=no-member
            if response.json().get('ok') is True:
                self._lgr.logger.info(
                    '%s: Request current balance from almatel.ru',
                    self.identifier)
                response = session_object.get(
                    'https://almatel.ru/lk/',
                    headers={
                        'User-Agent': self.user_agent
                    },
                    verify=bool(self.tls_verify)
                )

                if response.status_code == requests.codes.ok: # pylint: disable=no-member
                    if 'lk__profile-balance' in response.text:
                        tree = html.fromstring(response.text)

                        try:
                            balance = float(locale.atof(tree.xpath(
                                '//div[@class="lk__profile--block '
                                'lk__profile-balance"]/div/div/span'
                                '[@class="question-block-value"]/text()'
                            )[0]))
                        except ValueError as err:
                            self._lgr.logger.error(
                                '%s: Cannot get balance value: %s',
                                self.identifier, err)
                            self.last_balance = self.messages['parsing_error']

                        if (balance is not None
                            and isinstance(balance, (int, float))):
                            self._lgr.logger.info(
                                '%s: Balance has been collected',
                                self.identifier)
                            self._lgr.logger.debug('%s: Balance is %s',
                                self.identifier, balance)

                            self.last_balance = float(balance)

                        else:
                            self._lgr.logger.error(
                                '%s: Cannot extract balance value',
                                self.identifier)

                            self.last_balance = self.messages['parsing_error']
                    else:
                        self._lgr.logger.error(
                            '%s: Cannot find balance value on the page',
                            self.identifier)
                        self.last_balance = self.messages['cannot_proceed']

                else:
                    self._lgr.logger.error(
                        '%s: Cannot load page with balance: %s',
                        self.identifier, response.status_code)
                    self.last_balance = self.messages['cannot_proceed']

            else:
                self._lgr.logger.error(
                    '%s: Cannot log in to Self Service Portal',
                    self.identifier)
                self.last_balance = self.messages['cannot_proceed']

        else:
            self._lgr.logger.error('%s: Cannot connect to Self Service Portal',
                self.identifier)
            self.last_balance = self.messages['no_answer']
