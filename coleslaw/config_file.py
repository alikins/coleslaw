import logging
import yaml

log = logging.getLogger(__name__)


def load(config_file_path):
    log.debug('cfp: %s', config_file_path)

    with open(config_file_path, 'r') as config_file:
        config_data = yaml.safe_load(config_file)

    log.debug('config_data: %s', config_data)

    return config_data
