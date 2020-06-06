import base64
import logging
import json
import pathlib

import attr
import jinja2

from anytree.exporter import JsonExporter, DictExporter
from anytree.importer import JsonImporter, DictImporter

from . import nodes

log = logging.getLogger(__name__)


class FancyJSONEncoder(json.JSONEncoder):
    def _attr_filter(self, attr, value):
        # log.debug('ATTR: %s', attr)
        if attr.name.startswith('b_') or isinstance(value, bytes):
            # log.debug('skipping ATTR: %s', attr)
            return False
        return True

    def default(self, obj):
        # I'm sure this will be fine and not run into any issues at all
        if isinstance(obj, bytes):
            return base64.encodebytes(obj).decode('utf-8')

        if isinstance(obj, pathlib.Path):
            return str(obj)

        if isinstance(obj, nodes.BaseNode):
            node_dict = obj.asdict()
            return node_dict

        if attr.has(obj.__class__):
            return attr.asdict(obj, filter=self._attr_filter)

        if isinstance(obj, jinja2.Environment):
            if isinstance(obj.loader, jinja2.ChoiceLoader):
                loaders = obj.loader.loaders
                loader_data = []
                for loader in loaders:
                    if isinstance(loader, jinja2.PackageLoader):
                        loader_data.append({'_type': loader.__class__.__name__,
                                            })
                    if isinstance(loader, jinja2.FileSystemLoader):
                        loader_data.append({'_type': loader.__class__.__name__,
                                            'loader': {'searchpath': loader.searchpath},
                                            })
                return loader_data

        try:
            return super().default(obj)
        except Exception as exc:
            log.exception(exc)
            log.debug('JSON export fail on:\n%s', obj)
            raise


def ignore_bytes_attr_ittr(k_v_iter):
    for attribute, value in k_v_iter:
        # log.debug('attribute:%s (%s) type(value): %s', attribute, type(attribute), type(value))
        if attribute.startswith('b_') or isinstance(value, bytes):
            # log.debug('SKIPPING %s type(value): %s', attribute, type(value))
            continue
        yield attribute, value


def json_exporter():
    dict_exporter = DictExporter(attriter=ignore_bytes_attr_ittr)
    exporter = JsonExporter(dictexporter=dict_exporter,
                            indent=4,
                            # sort_keys=True,
                            cls=FancyJSONEncoder)
    return exporter


def json_importer():
    dict_importer = DictImporter(nodecls=nodes.node_class_factory)
    importer = JsonImporter(dictimporter=dict_importer)
    return importer
