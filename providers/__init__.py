""" Build a dynamic list of available exporter modules """

import os

from importlib import import_module
from inspect import isclass
from pkgutil import iter_modules
from logger import Logger

modules = {}
current_directory = os.path.dirname(__file__)
lgr = Logger(class_name=__name__)

for (_, module_name, _) in iter_modules([current_directory]):
    module = import_module(f'{__name__}.{module_name}')

    for attribute_name in dir(module):
        attribute = getattr(module, attribute_name)
        if (isclass(attribute)
            and hasattr(attribute, 'class_type')
            and attribute.class_type == 'provider'):

            lgr.logger.info('Load provider %s (%s/%s.py)',
                            attribute.__name__, __name__, module_name)
            modules[attribute_name] = attribute
