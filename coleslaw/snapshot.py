import logging

from . import jsonutils

log = logging.getLogger(__name__)


def snapshot_dump(node, snapshot_fo):
    exporter = jsonutils.json_exporter()
    exporter.write(node, snapshot_fo)


def snapshot_dumps(node):
    exporter = jsonutils.json_exporter()
    return exporter.export(node)


def snapshot_load(snapshot_fo):
    importer = jsonutils.json_importer()
    node = importer.read(snapshot_fo)
    return node


def snapshot_loads(snapshot_data):
    importer = jsonutils.json_importer()
    node = importer.import_(snapshot_data)
    return node
