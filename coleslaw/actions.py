"""Main module."""

import logging
import logging.config
import os.path
import pprint
import yaml

import anytree
import attr

from . import config
from . import readers
from . import writers

log = logging.getLogger(__name__)


def setup_logging():
    PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))
    logging_config = yaml.safe_load(open(os.path.join(PROJECT_DIR, 'logging.yaml'), 'r'))
    logging.config.dictConfig(logging_config)


def read_config(config_file_path):
    config_data = config.default_config
    log.debug('default config_data: %s', config_data)
    log.debug('default config_data: %s', pprint.pformat(config_data))

    config_info = config.from_file(config_file_path)
    log.debug('config_info: %s', config_info)

    log.debug('config_info:\n%s', pprint.pformat(attr.asdict(config_info)))
    return config_info


def build_tree(config_info, collection_filenames):
    base_reader = readers.TreeReader()
    base_node = base_reader.populate(config_info.app['output_dir'],
                                     config_info.app['url_prefix'])

    for warehouse_name, warehouse_info in config_info.warehouses.items():
        warehouse_reader = readers.WarehouseTreeReader(warehouse_info, config_info)
        collection_file_patterns = list(collection_filenames) + warehouse_info.collections

        log.debug('updating collections for warehouse: %s', warehouse_info.warehouse_name)

        r = anytree.Resolver("name")
        content_path = "content/"
        content_node = r.get(base_node, content_path)

        wh_node = warehouse_reader.populate(parent_node=content_node)
        wh_node = warehouse_reader.populate_collections(wh_node, collection_file_patterns)

        wh_export = writers.TreeExport(wh_node)
        snapshot_dir = os.path.join(config_info.app['snapshot_dir'], warehouse_info.warehouse_name)
        os.makedirs(snapshot_dir, exist_ok=True)
        snapshot_path = os.path.join(snapshot_dir, "SNAPSHOT.json")
        wh_export.snapshot(snapshot_path)

        # snapshot
        # tree_exporter.snapshot(warehouse_name=warehouse_info.warehouse_name)
    return base_node


def export_tree(base_node):
    tree_exporter = writers.TreeExport(base_node)
    tree_exporter.export()
