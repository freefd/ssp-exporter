""" Megafon Russia B2C exporter module """

from dataclasses import dataclass, InitVar

import json
import requests

from logger import Logger

@dataclass
class MegafonRussiaB2C:
    """ Megafon Russia exporter class """

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
            self._lgr.logger.warning('%s: Identifier disabled', self.identifier)
            self.last_balance = self.messages['disabled']

        session_object = requests.Session()
        self._lgr.logger.info('%s: Request CSRF token from api.megafon.ru',
            self.identifier)

        try:
            response = session_object.get(
                'https://api.megafon.ru/mlk/api/auth/sessionCheck',
                headers={
                        'User-Agent': self.user_agent,
                        'X-App-Type': 'react_lk',
                        'X-Cabinet-Capabilities': 'web-2020',
                },
                verify=bool(self.tls_verify)
            )
        except requests.exceptions.RequestException as connection_error:
            self._lgr.logger.error('%s: Cannot connect to api.megafon.ru: %s',
                self.identifier, connection_error)
            self.last_balance = self.messages['connection_error']

        if response.status_code == requests.codes.ok: # pylint: disable=no-member
            cookies_dict = session_object.cookies.get_dict()

            self._lgr.logger.debug('%s: Cookies: %s',
                self.identifier, cookies_dict)

            if 'NEW-CSRF-TOKEN' in cookies_dict:

                self._lgr.logger.debug('%s: Collected СSRF token %s',
                    self.identifier, cookies_dict['NEW-CSRF-TOKEN'])
                self._lgr.logger.info('%s: Sign in to api.megafon.ru',
                    self.identifier)

                try:
                    response = session_object.post(
                        'https://api.megafon.ru/mlk/api/login',
                        data={
                            'login': self.identifier,
                            'password': self.password,
                        },
                        headers={
                            'User-Agent': self.user_agent,
                            'X-App-Type': 'react_lk',
                            'X-Cabinet-Capabilities': 'web-2020',
                            'X-CSRF-TOKEN': cookies_dict['NEW-CSRF-TOKEN']
                        },
                        cookies=cookies_dict,
                        verify=bool(self.tls_verify)
                    )
                except requests.exceptions.RequestException as connection_error:
                    self._lgr.logger.error(
                        '%s: Cannot connect to api.megafon.ru: %s',
                        self.identifier, connection_error)
                    self.last_balance = self.messages['connection_error']

                if 'Неправильный формат телефона' in response.text:
                    self._lgr.logger.error('%s: Invalid identifier format',
                        self.identifier)
                    self.last_balance = self.messages['cannot_proceed']

                if 'Неправильный номер телефона или пароль' in response.text:
                    self._lgr.logger.error('%s: Invalid identifier or password',
                        self.identifier)
                    self.last_balance = self.messages['cannot_proceed']

                if 'Введите код с картинки' in response.text:
                    self._lgr.logger.error('%s: Captcha request detected',
                        self.identifier)
                    self.last_balance = self.messages['captcha']

                if 'Как получить пароль' in response.text:
                    self._lgr.logger.error(
                        '%s: Cannot log in to Self Service Portal: '
                        'login form is missing', self.identifier)
                    self.last_balance = self.messages['cannot_proceed']

                if ('Превышено количество попыток входа с использованием пароля'
                        in response.text):
                    self._lgr.logger.error('%s: Rate limit exceeded',
                        self.identifier)
                    self.last_balance = self.messages['rate_limit']

                # print(f'REQUEST HEADERS:\n\t{response.request.headers}')
                # print(f'RESPONSE HEADERS:\n\t{response.headers}')
                # print(f'RESPONSE TEXT:\n{response.text}')

                if (response.status_code == requests.codes.ok
                    and 'jwtToken' in response.json()): # pylint: disable=no-member
                    jwt_token = response.json().get('jwtToken')

                    self._lgr.logger.info('%s: Collected JWT token',
                        self.identifier)

                    self._lgr.logger.info(
                        '%s: Request current balance from api.megafon.ru',
                        self.identifier)

                    try:
                        response = session_object.get(
                            'https://api.megafon.ru/mlk/api/main/balance',
                            headers={
                                'User-Agent': self.user_agent,
                                'X-Cabinet-Authorization':f'Bearer {jwt_token}',
                                'X-App-Type': 'react_lk',
                                'X-Cabinet-Capabilities': 'web-2020',
                            },
                            verify=bool(self.tls_verify)
                        )
                    except requests.exceptions.RequestException \
                            as connection_error:
                        self._lgr.logger.error(
                            '%s: Cannot connect to api.megafon.ru: %s',
                            self.identifier, connection_error)
                        self.last_balance = self.messages['connection_error']

                    if response.status_code == requests.codes.ok: # pylint: disable=no-member
                        if response.json().get('balanceWithLimit'):
                            balance = response.json().get('balanceWithLimit')

                            if (balance is not None
                                and isinstance(balance, (int, float))):
                                self._lgr.logger.info(
                                    '%s: Balance has been collected',
                                    self.identifier)
                                self._lgr.logger.debug('%s: Balance is %s',
                                    self.identifier, balance)

                                self.last_balance = float(balance)

                                self._lgr.logger.info(
                                    '%s: Logging out from api.megafon.ru',
                                    self.identifier)

                                try:
                                    response = session_object.get(
                                        'https://api.megafon.ru/mlk/api/logout',
                                        headers={
                                            'User-Agent': self.user_agent,
                                            'X-Cabinet-Authorization': f'Bearer'
                                                f' {jwt_token}',
                                            'X-App-Type': 'react_lk',
                                            'X-Cabinet-Capabilities':'web-2020',
                                        },
                                        verify=bool(self.tls_verify)
                                    )
                                except requests.exceptions.RequestException \
                                        as connection_error:
                                    self._lgr.logger.error(
                                    '%s: Cannot logout from api.megafon.ru: %s',
                                        self.identifier, connection_error)
                                    self.last_balance = \
                                        self.messages['connection_error']

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
                self._lgr.logger.error('%s: Cannot obtain CSRF token',
                    self.identifier)
                self.last_balance = self.messages['cannot_proceed']

        else:
            self._lgr.logger.error('%s: Cannot connect to Self Service Portal',
                self.identifier)
            self.last_balance = self.messages['no_answer']
