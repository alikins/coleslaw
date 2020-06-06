import logging
import pathlib
import attr

from galaxy_importer import schema

log = logging.getLogger(__name__)


def convert_path(path):
    return pathlib.Path(path).expanduser().resolve()


def convert_list_to_path_list(val):
    '''Convert a list of dicts with file info into list of CollectionArtifactFile'''

    return [convert_path(path_item) for path_item in val]


def convert_none_to_path(default):
    converter = attr.converters.default_if_none(default=default)

    def path_converter(val):
        val = converter(val)
        return convert_path(val)

    return path_converter


def convert_none_to_empty_dict(val):
    ''' if val is None, return an empty dict'''

    # if val is not a dict or val 'None' return val
    # and let the validators raise errors later
    if val is None:
        return {}
    return val


@attr.s(frozen=True)
class ArtifactInfo(object):
    filename = attr.ib()
    full_path = attr.ib(converter=convert_path)
    sha256 = attr.ib()
    size = attr.ib(type=int)
    mtime = attr.ib()


@attr.s()
class LoaderResult(schema.ImportResult):
    artifact_info = attr.ib(type=ArtifactInfo, default=None)
    b_manifest = attr.ib(default=None, type=bytes)
    b_file_manifest = attr.ib(default=None, type=bytes)
    file_manifest_filename = attr.ib(default=None)


@attr.s
class ServerInfo():
    url = attr.ib(default="http://localhost/")

    @classmethod
    def from_dict(cls, data):
        return cls(url=data['url'])


@attr.s
class WarehouseInfo():
    warehouse_name = attr.ib()
    # a path to a dir where the warehouses are located
    district_dir = attr.ib(converter=convert_none_to_path(default='./output/'))

    server = attr.ib(type=ServerInfo)

    galaxy_importer_config = attr.ib(factory=dict,
                                     validator=attr.validators.instance_of(dict),
                                     converter=attr.converters.default_if_none(factory=dict))

    # base of url paths as referenced in *_href, download_url, etc
    url_prefix = attr.ib(default="",
                         converter=attr.converters.default_if_none(""))

    # templates_dir = attr.ib(default="templates/",
    #                        converter=convert_path)
    templates_dir = attr.ib(default="./templates/",
                            converter=convert_none_to_path(default='./templates/'))

    incremental = attr.ib(default=True,
                          converter=attr.converters.default_if_none(True))

    collections = attr.ib(factory=list,
                          validator=attr.validators.deep_iterable(
                              member_validator=attr.validators.instance_of(pathlib.Path),
                              iterable_validator=attr.validators.instance_of(list)),
                          converter=convert_list_to_path_list)

    @classmethod
    def from_dict(cls, data, name):
        server_info = ServerInfo.from_dict(data.get('server', {}))
        instance = cls(warehouse_name=name,
                       district_dir=data.get('output_dir'),
                       server=server_info,
                       galaxy_importer_config=data.get('galaxy_importer_config'),
                       url_prefix=data.get('url_prefix'),
                       templates_dir=data.get('templates_dir'),
                       incremental=data.get('incremental'),
                       collections=data.get('collections', []))
        return instance


@attr.s
class ConfigInfo():
    warehouse_defaults = attr.ib(type=WarehouseInfo,
                                 validator=attr.validators.instance_of(WarehouseInfo))

    app = attr.ib(factory=dict,
                  validator=attr.validators.instance_of(dict),
                  converter=attr.converters.default_if_none(factory=dict))

    warehouses = attr.ib(factory=dict,
                         validator=attr.validators.instance_of(dict),
                         converter=attr.converters.default_if_none(factory=dict))

    @classmethod
    def from_dict(cls, data):
        app_data = data.get('app', {})
        wh_defaults_data = data.get('warehouse_defaults', {})
        whs_data = data.get('warehouses', {})
        warehouses = {}
        for wh_name, wh_data in whs_data.items():
            # Merge the wh defaults
            import_config = wh_defaults_data['galaxy_importer_config'].copy()
            import_config.update(wh_data.get('galaxy_importer_config', {}))

            server_config = wh_defaults_data['server'].copy()
            server_config.update(wh_data.get('server', {}))

            merged_wh_data = {}
            merged_wh_data.update(wh_defaults_data)
            merged_wh_data.update(wh_data)

            # merged_wh_data['galaxy_importer_config'] = wh_defaults_data['galaxy_importer_config']
            # merged_wh_data['galaxy_importer_config'].update(wh_data['galaxy_importer_config'])

            merged_wh_data['galaxy_importer_config'] = import_config
            merged_wh_data['server'] = server_config

            import pprint
            log.debug('merged_wh_data: %s', pprint.pformat(merged_wh_data))

            warehouse = WarehouseInfo.from_dict(merged_wh_data, wh_name)
            warehouses[wh_name] = warehouse

        wh_defaults = WarehouseInfo.from_dict(wh_defaults_data, 'warehouse_defaults')
        instance = cls(app=app_data,
                       warehouse_defaults=wh_defaults,
                       warehouses=warehouses)
        return instance


@attr.s()
class IndexPageMeta(object):
    count = attr.ib(type=int)


@attr.s()
class IndexPageLinks(object):
    first = attr.ib()
    last = attr.ib()
    next = attr.ib(default=None)
    prev = attr.ib(default=None)


@attr.s()
class IndexPage(object):
    """Represents an index / page

    See https://petstore.swagger.io/?url=https://raw.githubusercontent.com/ansible/galaxy_ng/master/openapi/openapi.yaml
    PageInfo, PageMeta, PageLinks schema
    """

    meta = attr.ib(type=IndexPageMeta)
    links = attr.ib(type=IndexPageLinks)
    data = attr.ib(factory=list)


@attr.s(frozen=True)
class APIRoot(object):
    available_versions = attr.ib(factory=dict)


@attr.s()
class CollectionVersionListItem(object):
    # could make a Version type of some sort
    version = attr.ib()
    href = attr.ib()

    # dates, but just strings for now
    created_at = attr.ib()
    modified_at = attr.ib()
