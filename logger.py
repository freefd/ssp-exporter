#!/usr/bin/env python3
""" Self Service Portal Exporter: Logger Module """

import re
import sys
import json
import logging

class SensitiveDataFormatter(logging.Formatter):
    """ Logging Sensitive Data Formatter """

    @staticmethod
    def _filter(message: str=None):
        filters = [
            [r"'password': '.+?'", "'password': '*****'"],
            [r'"password": ".+?"', '"password": "*****"'],
            [r'"password":\s+{\n\s+"value": ".+?"',
                '"password": {\n\t"value": "*****"'],
            [r'password=.+?', 'password=*****']
        ]
        for filter_pattern in filters:
            message = re.sub(filter_pattern[0], filter_pattern[1], message)
        return message

    def format(self, record: str=''):
        original = logging.Formatter.format(self, record)
        return self._filter(original)

class Logger:
    """ Logger class """

    def __init__(self, log_level: int = 20, class_name: str=None):
        self.logger = logging.getLogger(class_name)
        self._console_handler = logging.StreamHandler(sys.stdout)
        self._console_handler.setFormatter(
            SensitiveDataFormatter(
                '[%(asctime)s] %(levelname)s %(module)s.py::'
                '%(name)s::%(funcName)s(): %(message)s',
            )
        )
        self.logger.addHandler(self._console_handler)
        self.logger.setLevel(log_level)

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
        self_dict = {}

        for key, value in self.__dict__.items():
            if isinstance(value, bool | int | float | str | dict | list | None):
                self_dict[key]=value                

        return self_dict

if __name__ == '__main__':

    Logger().logger.critical(
        'This module must not be run as a standalone application')

    # sysexits.h: EX_OSERR
    sys.exit(71)