#!/usr/bin/env python3

"""  Self Service Portal Exporter """

from dataclasses import dataclass


import argparse
import json
import logging
import os
import random
import signal
import sys
import time

from pathlib import Path
from types import ModuleType
from typing import Callable
from prometheus_client import start_http_server
from prometheus_client.core import GaugeMetricFamily, REGISTRY

import jsonschema
import schedule
import yaml
import providers

from logger import Logger

def min_string_length(min_length: int=0) -> Callable | Exception:
    """ String length validation """

    def validate(param):
        if isinstance(param, str) and len(param) >= min_length:
            return param
        raise argparse.ArgumentTypeError(
            f'String must be at least {min_length} characters long')
    return validate

def env_variable_check(name: str=None, min_length: int=1,
                default: int|str|bool=None) -> int | str | bool | None:
    """ Check Environment Variable fits to conditions """

    if os.environ.get(name) and len(os.environ.get(name)) >= min_length:
        lgr.logger.warning('Use value `%s` for `%s`', default, name)
        return os.environ.get(name)
    if default:
        lgr.logger.warning('Use default value `%s` for `%s`', default, name)
        return default

    # logging.warning(
    #         'Use value "None" for `%s`', name)
    return None

def human_readable_refresh_time(seconds, granularity=2) -> str:
    """ Human-readable time frames """

    result = []

    intervals = (
        ('w', 604800),
        ('d', 86400),
        ('h', 3600),
        ('m', 60),
        ('s', 1),
    )

    for name, count in intervals:
        value = seconds // count
        if value:
            seconds -= value * count
            if value == 1:
                name = name.rstrip('s')
            result.append(f'{value}{name}')
    return ''.join(result[:granularity])

def terminate_signal(signal_number: int = None, _: str = None) -> None:
    """ Terminate by SIGTERM """

    lgr.logger.critical('Received the termination signal: %s', signal_number)
    lgr.logger.critical('Gracefully terminated')
    sys.exit(0)

def get_args(show_usage: bool = False) -> argparse.Namespace:
    """ Parse command line arguments """

    args_parser = argparse.ArgumentParser(
        description="Ntfy messages to D-Bus org.freedesktop.Notifications"
    )
    args_parser.add_argument('--config', '-c',
                             help='Path to configuration file. '
                                'Environment variable name: '
                                'SSP_EXPORTER_CONFIG_FILE. Default: '
                                f'{os.path.dirname(__file__)}/config/'
                                'production_exporter.yaml',
                             required=False,
                             type=min_string_length(1),
                             default=env_variable_check(
                                name='SSP_EXPORTER_CONFIG_FILE',
                                min_length=1,
                                default=f'{os.path.dirname(__file__)}/config/'
                                    f'production_exporter.yaml'
                                )
                             )
    args_parser.add_argument('--schema', '-s',
                             help='Path to JSON schema file. '
                                'Environment variable name: '
                                'SSP_EXPORTER_SCHEMA_FILE. Default: '
                                f'{os.path.dirname(__file__)}/config/'
                                'schema.yaml',
                             required=False,
                             type=min_string_length(2),
                             default=env_variable_check(
                                name='SSP_EXPORTER_SCHEMA_FILE',
                                min_length=2,
                                default=f'{os.path.dirname(__file__)}/config/'
                                    f'schema.yaml'
                                )
                             )
    args_parser.add_argument('--address', '-a',
                             help='Local address to bind.'
                                    'Environment variable name: '
                                    'SSP_EXPORTER_BIND_ADDRESS. Default: '
                                    'localhost',
                             required=False,
                             type=min_string_length(1),
                             default=env_variable_check(
                                name='SSP_EXPORTER_BIND_ADDRESS',
                                min_length=1,
                                default='localhost'
                                )
                             )
    args_parser.add_argument('--port', '-p',
                             help='Local port to bind. '
                                    'Environment variable name: '
                                    'SSP_EXPORTER_BIND_PORT. Default: 9868',
                             required=False,
                             type=int,
                             default=env_variable_check(
                                name='SSP_EXPORTER_BIND_PORT',
                                min_length=1,
                                default=10032
                                )
                             )
    args_parser.add_argument('--loglevel', '-l',
                             help='Logging level. Environment variable name: '
                                    'SSP_EXPORTER_LOG_LEVEL. Default: INFO',
                             required=False,
                             type=str,
                             choices=[
                                'NOTSET', 'DEBUG', 'INFO',
                                'WARNING', 'ERROR', 'CRITICAL'],
                             default=env_variable_check(
                                name='SSP_EXPORTER_LOG_LEVEL',
                                min_length=4,
                                default='INFO'
                                )
                             )

    # Special switcher to show usage
    if show_usage:
        args_parser.print_help()
        # syscxits.h: EX_USAGE
        sys.exit(64)

    return args_parser

@dataclass
class Configuration:
    """ Configuration class """

    config_file: str = None
    schema_file: str = None

    def __post_init__(self) -> None:
        self.configuration = self._load_config(self.config_file)
        self.schema = self._load_config(self.schema_file)

        if self.configuration is None:
            lgr.logger.error('Configuration is not defined')
            # sysexits.h: EX_DATAERR
            sys.exit(65)

        if self.schema is None:
            lgr.logger.error('JSON schema is not defined')
            # sysexits.h: EX_DATAERR
            sys.exit(65)

        self._validate_config()

    def _validate_config(self) -> bool:
        """ Validate configuration file """

        # JSON Schema validator for configuration file
        validation_errors = jsonschema.Draft7Validator(
                    self.schema).iter_errors(self.configuration)

        configuration_errors = []
        for error in validation_errors:
            configuration_errors.append(error)

        if len(configuration_errors) > 0:
            for error in configuration_errors:
                error_path = ' - '.join([str(x) for x in error.path])
                lgr.logger.error('Configuration section [%s]: %s',
                                    error_path, error.message)

            lgr.logger.critical('The configuration format is malformed')
            # sysexits.h: EX_DATAERR
            sys.exit(65)

        lgr.logger.debug('Configuration file format is valid')

        identifiers_overall = sum(
                len(self.configuration['identifiers'][provider]) for
                        provider in self.configuration['identifiers']
            )

        identifiers_disabled = sum(
                item['disabled'] for provider in self.configuration['identifiers']
                    for item in self.configuration['identifiers'][provider]
                        if 'disabled' in item and item['disabled'] is True
            )

        if identifiers_overall == identifiers_disabled:
            lgr.logger.critical('All available identifiers are disabled')
            # sysexits.h: EX_CONFIG
            sys.exit(78)

    def get_configuration(self) -> dict:
        """ Return the configuration structure """

        return self.configuration

    def get_schema(self) -> dict:
        """ Return the schema structure """

        return self.schema

    def get_bind_address(self) -> str:
        """ Return collector bind address """

        return self.configuration['service']['bind_address']

    def get_bind_port(self) -> str:
        """ Return collector bind port """

        return self.configuration['service']['bind_port']

    def set_bind_address(self, bind_address: str = None) -> None:
        """ Set collector bind address """

        self.configuration['service']['bind_address'] = bind_address

    def set_bind_port(self, bind_port: str = None) -> None:
        """ Set collector bind port """

        self.configuration['service']['bind_port'] = bind_port

    @staticmethod
    def _load_config(file: str = None) -> dict | None:
        """ Read configuration file """

        if Path(file).is_file():
            lgr.logger.debug('Load configuration file `%s`', file)
            file_extension = Path(file).suffix.lower()

            if file_extension in ('.yaml', '.yml'):
                with open(file, 'r', encoding='utf8') as yaml_data:
                    return yaml.full_load(yaml_data)
            elif '.json' == file_extension:
                with open(file, 'r', encoding='utf8') as json_data:
                    return json.load(json_data)
            else:
                lgr.logger.critical('Cannot load configuration file `%s`', file)
                # sysexits.h: EX_DATAERR
                sys.exit(65)
        else:
            lgr.logger.critical('Cannot find configuration file `%s`', file)
            # sysexits.h: EX_OSFILE
            sys.exit(72)

class SSPCollector:
    """ Self Service Portal collector class """

    def __init__(self, **kwargs: str) -> None:
        self.configuration = kwargs['configuration']
        self.log_level = kwargs['log_level']
        self.exporter = {}

        for prov_name, module in providers.modules.items():
            if (prov_name in self.configuration['identifiers']
                and self.configuration['identifiers'][prov_name] is not None
                and not isinstance(prov_name, Logger)):

                # In-memory storage: Provider -> Identifier -> Object
                self.exporter[prov_name] = {}

                # For each identifier within a module if not disabled
                for item in self.configuration['identifiers'][prov_name]:
                    if (item is not None
                        and ('disabled' not in item or not item['disabled'])):

                        lgr.logger.info(
                            'Initialize `%s` exporter for `%s` identifier',
                            prov_name, item['identifier'])

                        # Initialize provider instance per identifier
                        self.exporter[prov_name][item['identifier']] = module(
                            messages=self.configuration['service']['messages'],
                            user_agent=random.choice(
                                self.configuration['service']['user_agents']),
                            log_level=self.log_level,
                            **item
                        )

                        # Schedule a job per provider instance and identifier
                        self._schedule_job(
                            module=self.exporter[prov_name][item['identifier']]
                        )

                        # First explicit run of identifier
                        self._update_data(
                            module=self.exporter[prov_name][item['identifier']]
                        )

    def __str__(self) -> str:
        """ Human readable print of the current class """

        return_obj = {}

        for _, identifier in self.exporter.items():
            for key, value in identifier.items():
                return_obj[key] = {
                    'value': value.as_dict(),
                    'type': type(value).__name__
                }

        return json.dumps(return_obj, ensure_ascii=False, indent=4)

    def _schedule_job(self, module: ModuleType) -> None:
        """ Schedule the job """

        lgr.logger.info(
            'Add scheduler for identifier `%s`: run every %s seconds',
            module.identifier, module.poll_interval)

        # Add the scheduler per identifier
        schedule.every(module.poll_interval).seconds.do(
            self._update_data,
            module=module
        )

    def _update_data(self, module: ModuleType) -> None:
        """ Update provider data """

        lgr.logger.info('Update data for `%s` identifier `%s`',
            module.__class__.__name__, module.identifier
        )

        # Make a request to update the balance values
        module.update_balance()

        lgr.logger.debug('Identifier `%s` has value %s',
                module.identifier,
                module.get_balance()
            )

    def collect(self) -> None:
        """ Main collector """

        # For each identifier from each provider module
        for provider, identifier_obj in self.exporter.items():

            for identifier, instance in identifier_obj.items():

                if instance is not None and instance.disabled is not True:

                    # Add service labels
                    labels = ['identifier', 'provider', 'poll_interval']
                    values = [
                        str(identifier), str(provider),
                        str(human_readable_refresh_time(
                            instance.poll_interval
                        ))
                    ]

                    # Add custom labels
                    for label in sorted(instance.labels):
                        labels.append(label)
                        values.append(instance.labels[label])

                    lgr.logger.debug(
                        'Generate Gauge metric `%s` for provider `%s` '
                        'with identifier `%s`',
                        self.configuration['service']['metric_name'],
                        provider, identifier)

                    # Generate a metric
                    gmf_object = GaugeMetricFamily(
                        self.configuration['service']['metric_name'],
                        provider,
                        labels=labels
                    )

                    # Add the data value
                    gmf_object.add_metric(
                        values,
                        instance.get_balance()
                        )
                    yield gmf_object

if __name__ == '__main__':

    # Assign SIGTERM listener
    signal.signal(signal.SIGTERM, terminate_signal)

    lgr = Logger(class_name=__name__)
    arguments = get_args().parse_args()

    log_level = logging.getLevelName(arguments.loglevel.upper())
    lgr.logger.setLevel(log_level)

    # Discovery a configuration file path
    if Path(arguments.config).is_file():
        config_file = arguments.config
        lgr.logger.info('Set configuration file path to `%s`', config_file)
    else:
        lgr.logger.info('Configuration file path does not exist, exiting')
        # sysexits.h: EX_OSFILE
        sys.exit(72)

    # Discovery a JSON schema file path
    if Path(arguments.schema).is_file():
        schema_file = arguments.schema
        lgr.logger.info('Set schema file path to `%s`', schema_file)
    else:
        lgr.logger.critical('Schema file path does not exist, exiting')
        # sysexits.h: EX_OSFILE
        sys.exit(72)

    configuration = Configuration(
                        config_file=config_file,
                        schema_file=schema_file
                    )

    if arguments.address:
        configuration.set_bind_address(arguments.address)
        lgr.logger.info('Set bind address to `%s`', arguments.address)

    if arguments.port:
        configuration.set_bind_port(arguments.port)
        lgr.logger.info('Set bind port to `%s`', arguments.port)


    # Create the collector
    custom_collector = SSPCollector(
                        configuration=configuration.get_configuration(),
                        log_level=log_level
                    )

    collector_bind_address = configuration.get_bind_address()
    collector_bind_port = configuration.get_bind_port()

    # Server the collector
    start_http_server(addr=collector_bind_address, port=collector_bind_port)

    lgr.logger.info('Server started: http://%s:%s/metrics',
                            collector_bind_address, collector_bind_port)

    REGISTRY.register(custom_collector)

    while True:
        schedule.run_pending()
        time.sleep(1)
