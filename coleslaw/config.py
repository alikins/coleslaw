import logging
import os.path
import pprint
import yaml

from . import config_file
from . import models

log = logging.getLogger(__name__)

DEFAULT_CONFIG_FILENAME = 'default_coleslaw.yml'
DEFAULT_CONFIG_FILE_PATH = os.path.join(os.path.dirname(__file__), DEFAULT_CONFIG_FILENAME)

PATH_ITEMS = ['templates_dir', 'output_dir']

# FIXME: use Path stuff


def hydrate_config_data(config_data):
    def stanzas(config_data):
        yield config_data['warehouse_defaults']
        for stanza in config_data['warehouses']:
            yield stanza

    for stanza in stanzas(config_data):
        for item in PATH_ITEMS:
            try:
                stanza[item] = os.path.normpath(os.path.expanduser(stanza[item]))
            except KeyError:
                pass
        # collections = []
        # for collection_pattern in stanza.get('collections', []):
        #     collections.extend(glob.glob(collection_pattern, recursive=True))
        # stanza['collections'] = collections
    return config_data


def from_file(config_file_path):
    try:
        config_data = config_file.load(config_file_path)
    except FileNotFoundError:
        log.warning('Tried loading config file %s but that file does not exist', config_file_path)

    log.debug('config_data (post file): %s', pprint.pformat(config_data))
    log.debug('config warehouses: %s', pprint.pformat(config_data['warehouses']))

    config_info = models.ConfigInfo.from_dict(config_data)
    return config_info


with open(DEFAULT_CONFIG_FILE_PATH, 'r') as config_file_fo:
    _default_config_data = yaml.safe_load(config_file_fo)

    default_config = _default_config_data
    # TODO: probably want to def
    # default_config = hydrate_config_data(_default_config_data)
