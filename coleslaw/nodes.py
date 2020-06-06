import functools
import json
import logging
import os.path
import shutil

import attr

from anytree import (
    NodeMixin,
    Resolver,
    # PreOrderIter,
    # LevelOrderIter,
    ChildResolverError,
)

from anytree.exporter import (
    DictExporter,
)

import anytree.search

import semantic_version

from . import jsonutils
from . import models
from . import utils

log = logging.getLogger(__name__)

json_exporter = jsonutils.json_exporter()
dict_exporter = DictExporter()
dict_one_level_exporter = DictExporter(maxlevel=1)


def only_path_node_filter(nodes):
    for node in nodes:
        if isinstance(node, PathNode):
            yield node


def highest_version_node(versions_node):
    # versions_node is the node that is the parent to the '0.0.1' nodes ({names[ace/name/versions)
    # TODO: could maybe add a semantic_version.Version() to the collection version nodes
    #       do a sort(nodes, key=node.semver,...) ish

    # Find the version nodes up one and down one in ./versions/*/
    version_nodes = [x for x in versions_node.children if isinstance(x, PathNode) and hasattr(x, 'version')]

    # according to docs, SimpleSpec with trailing - will make the compares include pre-release
    spec = semantic_version.SimpleSpec('>=0.0.0-')
    version_map = dict([(semantic_version.Version(ver.version), ver) for ver in version_nodes])
    best = spec.select(version_map.keys())
    best_node = version_map[best]

    return best_node


# from anytree.search
def _filter_by_name(node, name, value):
    try:
        return getattr(node, name) == value
    except AttributeError:
        return False


def _filter_by_hasattr(node, name):
    return hasattr(node, name)


class BaseNode(NodeMixin, object):
    _exclude_attrs = ['_exclude_attrs']
    path_trailer = ""

    def __init__(self, name, parent=None, children=None, **kwargs):
        self.__dict__.update(kwargs)
        self.name = name
        self.parent = parent
        if children:
            self.children = children
        self._node_type = self.__class__.__name__

    @property
    def pth(self):
        return self.separator.join([str(node.name) for node in self.path])

    @property
    def fs_pth(self):
        _fs_root = getattr(self.root, "fs_prefix", "")
        path_parts = [str(node.name or _fs_root) for node in self.path]
        return os.path.normpath(self.separator.join(path_parts))

    @property
    def url_pth(self):
        _url_prefix = getattr(self.root, "url_prefix", "")
        path_parts = [str(node.name or _url_prefix) for node in self.path]
        return utils.urljoin(*path_parts, self.path_trailer)

    @property
    def label(self):
        return self.name

    def __lt__(self, other):
        return compare_nodes(self, other)

    # Method to use to insure we don't create siblings with the same name.
    def get_or_add_child(self, child_node):
        # log.debug('add_child self: %s, child_node: %s', self.name, child_node.name)
        name_resolver = Resolver('name')
        try:
            existing_child = name_resolver.get(self, child_node.name)
            return existing_child
        # singling with that name exists already
        except ChildResolverError:
            # log.debug('ResolverError for %s, already exist as sibling: %s', child_node.name, exc)
            # don't need to do anything, already have a PathNode by that name
            # log.exception(exc)
            child_node.parent = self
            return child_node

    def __repr__(self):
        return "%s(%s)" % (self.__class__.__name__,
                           self.separator.join([str(node.name) for node in self.path]))

    def _yield_attr_values(self):
        for k, v in self.__dict__.items():
            if k in ('_NodeMixin__children', '_NodeMixin__parent'):
                continue
            if k in self._exclude_attrs:
                continue
            if k.startswith('_excluded'):
                continue
            yield k, v

    def asdict(self):
        return dict(self._yield_attr_values())

    def get_field(self, field_name):
        for node in self.iter_path_reverse():
            # TODO: could use an Unset
            try:
                return getattr(node, field_name)
            except AttributeError:
                if node.is_root:
                    raise
                continue

    # convience for use in jinja
    def findall(self, filter_=None, stop=None, maxlevel=None, mincount=None, maxcount=None):
        '''filter_ is a callable that is passed node, attribute 'name', and value'''
        # or could just **kwargs...
        return anytree.search.findall(node=self, filter_=filter_,
                                      stop=stop, maxlevel=maxlevel,
                                      mincount=mincount, maxcount=maxcount)

    @staticmethod
    def filter_by_attr(name, value):
        # name = '_node_type'
        # value = 'IndexHtmlNode'
        return functools.partial(anytree.search._filter_by_name, name=name, value=value)

    @staticmethod
    def filter_by_hasattr(attr_name):
        return functools.partial(_filter_by_hasattr, name=attr_name)

    @staticmethod
    def noall(node):
        return True


# TODO: rename DirectoryNode? PartitionNode?
class PathNode(BaseNode):
    '''Node class that doesn't allow duplicate sibling names.

    Also in theory does fs_path and url_path creation stuff'''

    path_trailer = "/"

    def _makedir(self):
        # log.debug('MAKEDIRS %s', self.fs_pth)
        os.makedirs(self.fs_pth, exist_ok=True)

    def save(self):
        # log.debug('SAVE %s', self)
        log.debug('SAVEDIR %17s %s', self._node_type, self.fs_pth)
        self.reserve()

    def reserve(self):
        '''Reserve the file path by creating it (makedir, touch) if it doesn't exist.'''
        log.debug('RESERVING %15s %s', self._node_type, self.fs_pth)
        self._makedir()

    @property
    def label(self):
        return self.name + '/'


class IndexNode(BaseNode):
    path_trailer = ""

    def body(self, data=None):
        if data is not None:
            return data
        if self.data:
            return self.data
        return ""

    def save(self, data=None):
        log.debug('SAVE %20s %s', self._node_type, self.fs_pth)
        with open(self.fs_pth, 'w') as index_fo:
            index_fo.write(self.body(data=data))

    def reserve(self):
        '''Reserve the file path by creating it (makedir, touch) if it doesn't exist.'''
        log.debug('RESERVING %15s %s', self._node_type, self.fs_pth)
        with open(self.fs_pth, 'w') as index_fo:
            index_fo.close()


class IndexJsonNode(IndexNode):
    '''Node class for leaf node 'index.json' files'''

    def body(self, data=None):
        return json_exporter.export(self)


class CollectionIndexJsonNode(IndexJsonNode):
    def body(self, data=None):
        data = self.serialize()
        return json.dumps(data, indent=4)

    def serialize(self):
        return {'name': self.parent.name,
                'namespace': self.parent.parent.name,
                'deprecated': False,
                'href': self.parent.url_pth,
                'versions_url': self.versions_url,
                'highest_version': self.highest_version(),
                }

    def highest_version(self):
        # TODO: could maybe add a semantic_version.Version() to the collection version nodes
        #       do a sort(nodes, key=node.semver,...) ish

        # Find the version nodes up one and down one in ./versions/*/
        name_resolver = Resolver('name')
        versions_node = name_resolver.get(self.parent, 'versions')

        best_node = highest_version_node(versions_node)

        return {'version': best_node.version,
                'href': best_node.url_pth}


class ListIndexJsonNode(IndexJsonNode):
    '''Node class for an index list view'''
    def __init__(self, name, parent=None, children=None,
                 **kwargs):
        self._item_type = kwargs.pop('_item_type', 'PathNode')
        super().__init__(name, parent=parent, children=children, **kwargs)

    def serialize_item(self, node, *args, **kwargs):
        '''Build the datastructure based on the passed in node and return an instance'''
        res = dict_exporter.export(node)
        res = {'name': node.name, 'href': node.url_pth}
        # log.debug('serialize onelevel: %s', res)

        return res

    def body(self, data=None):
        item_list = []
        for sibling in self.index_of():
            # log.debug('version_sibling.fs_pth: %s', version_sibling.fs_pth)
            item_list.append(self.serialize_item(sibling))

        index_page_meta = models.IndexPageMeta(count=len(item_list))

        index_page_url = self.url_pth
        index_page_links = models.IndexPageLinks(first=index_page_url,
                                                 last=index_page_url)
        index_page = models.IndexPage(meta=index_page_meta,
                                      links=index_page_links,
                                      data=item_list)

        data = attr.asdict(index_page)
        return json.dumps(data, indent=4)

    def index_of(self):
        return sorted([x for x in self.siblings if x is not self and isinstance(x, NODE_TYPE_MAP[self._item_type])])


class VersionsIndexJsonNode(ListIndexJsonNode):
    '''Node class for leaf node 'versions/index.json' files'''

    def serialize_item(self, node, *args, **kwargs):
        # log.debug('serialize node: %s', node)
        # timestamp = datetime.datetime.now().isoformat()
        collection_version_list_item = \
            models.CollectionVersionListItem(version=node.name,
                                             href=node.url_pth,
                                             created_at=node.mtime,
                                             modified_at=node.mtime)
        return attr.asdict(collection_version_list_item)

    def index_of(self):
        # Get all of the 'versions/0.0.1' style subdirs
        return sorted([x for x in super().index_of() if isinstance(x, PathNode) and hasattr(x, 'version')])


class IndexBytesNode(IndexNode):
    '''Node class for file content that needs byte for byte node files

    Ie, something that may be signed/chksumed like MANIFEST.json'''
    def __init__(self, name, parent=None, children=None, b_filecontents=None, **kwargs):
        super().__init__(name, parent=parent, children=children, **kwargs)
        self.b_filecontents = b_filecontents

    def save(self, data=None):
        log.debug('SAVE %20s %s', self._node_type, self.fs_pth)
        b_filecontents = self.b_filecontents or b''
        with open(self.fs_pth, 'wb') as index_fo:
            index_fo.write(b_filecontents)


class IndexArtifactNode(IndexNode):
    '''Node class for artifact archive leaf node files.

    This copies the artifact file from it's original location into the warehouse tree.'''

    def save(self, data=None):
        # log.debug('SAVE %s', self)
        log.debug('SAVE %20s %s', self._node_type, self.fs_pth)
        res = shutil.copy(self.collection_filename, self.fs_pth)

        log.debug('copy of %s -> %s returned %s',
                  self.collection_filename,
                  self.fs_pth, res)


class FsSymlinkNode(PathNode):
    '''Create a symlink from self.fs_pth to _target_node.fs_pth'''
    _exclude_attrs = PathNode._exclude_attrs + ['_target_is_directory']

    def save(self, data=None):
        pass

    def reserve(self, data=None):
        log.debug('Target node: %s', self._target_node)
        log.debug('SYMLINK Target node_fs_pth: %s', self._target_node.fs_pth)
        log.debug('SYMLINK RESERVE %20s %s (symlink %s -> %s)',
                  self._node_type, self.fs_pth,
                  self.fs_pth, self._target_node.fs_pth)

        relative_to_dir_fd = os.open(self.parent.fs_pth, os.R_OK)
        relpath = os.path.relpath(self._target_node.fs_pth, self.parent.fs_pth)

        log.debug('relpath: %s', relpath)

        try:
            os.symlink(relpath, self.fs_pth, dir_fd=relative_to_dir_fd)
        except FileExistsError:
            pass
        finally:
            os.close(relative_to_dir_fd)

        return


class HighestVersionFsSymlinkNode(FsSymlinkNode):
    _exclude_attrs = FsSymlinkNode._exclude_attrs + ['_versions_subdir_node']

    @property
    def label(self):
        if self._target_is_directory:
            return f"{self.name}/ -> {self.target().name}/"
        return f"{self.name} -> {self.target().name}"

    def target(self):
        return highest_version_node(self.parent)

    def reserve(self, data=None):
        # _target_node = highest_version_node(self._versions_subdir_node)
        self._target_node = highest_version_node(self.parent)
        # self._target_node_fs_pth = _target_node.fs_pth
        super().reserve(data=data)


class IndexJinjaNode(IndexNode):
    '''Node class for leaf nodes created from jinja templates'''

    def __init__(self, name, parent=None, children=None, **kwargs):
        self.template_name = kwargs.pop('template_name', 'default.html.j2')
        super().__init__(name, parent=parent, children=children, **kwargs)

    def body(self, data=None):
        jinja_env = self.get_field('_jinja_env')

        template = jinja_env.get_template(self.template_name)
        log.debug('template: %s', template)

        return template.render(data={'name': self.name,
                                     'siblings': self.index_of(),
                                     'node': self,
                                     'template_name': self.template_name,
                                     })

    def index_of(self):
        return sorted([x for x in self.siblings if x is not self])


class IndexHtmlNode(IndexJinjaNode):
    '''Node class for html leaf nodes created from jinja templates'''
    pass


class IndexSha256sumNode(IndexNode):
    '''Node class for writing SHA256SUMS files'''

    def __init__(self, name, parent=None, children=None,
                 _recursive=False, **kwargs):
        super().__init__(name, parent=parent, children=children, **kwargs)
        self._recursive = _recursive

    def body(self, data=None):
        lines = []
        for sibling in self.index_of():
            if os.path.isdir(sibling.fs_pth):
                continue

            # At some point, could attempt to make this multiprocessing'ed if it is cpu bound
            sha256sum = utils.sha256sum_from_path(sibling.fs_pth)
            rel_path = os.path.basename(sibling.fs_pth)

            # show relative path of descendants for recursive
            if self._recursive:
                rel_path = os.path.relpath(sibling.fs_pth, self.parent.fs_pth)

            line = f'{sha256sum}  {rel_path}'
            lines.append(line)

        res = '\n'.join(lines)
        return res

    def index_of(self):
        # Note: In constrast to IndexFileListNode, the shasum node should _NOT_ include itself in it's output,
        #       but it _should_ include other SHA256sums files.
        if self._recursive:
            return [x for x in self.parent.descendants if x is not self]
        else:
            return [x for x in self.siblings if not isinstance(x, IndexSha256sumNode) and x is not self]


class IndexFileListNode(IndexNode):
    '''Node class for writing a text list of files.

    Amongst other uses, for using with `git add --pathspec-from-file=file_list.txt`.'''

    def __init__(self, name, parent=None, children=None,
                 _recursive=False, **kwargs):
        super().__init__(name, parent=parent, children=children, **kwargs)
        self._recursive = _recursive

    def body(self, data=None):
        lines = []
        for sibling in self.index_of():
            # log.debug('sibling.fs_pth: %s', sibling.fs_pth)
            if os.path.isdir(sibling.fs_pth):
                continue
            rel_path = os.path.basename(sibling.fs_pth)
            # show relative path of descendants for recursive
            if self._recursive:
                rel_path = os.path.relpath(sibling.fs_pth, self.parent.fs_pth)

            line = f'{rel_path}'

            lines.append(line)
        res = '\n'.join(lines)
        # log.debug('res:\n%s', res)
        return res

    def index_of(self):
        # Note: In constrast to IndexSha256sumNode, the file list node _should_ include itself in it's output
        if self._recursive:
            return [x for x in self.parent.descendants if not isinstance(x, IndexArtifactNode)]
        else:
            return [x for x in self.siblings if not isinstance(x, IndexArtifactNode)]


def compare_nodes(a, b):
    '''Adhoc compare for nodes of different types so sorted() DWIM

    Approximate rules:
        # Dirs before Files
        PathNodes < IndexNodes

        # Make 'default' ver dir before versions
        PathNodes(name='default') < PathNode

        # For PathNodes with a version, use reverse semver order
        # so newer versions are first

        # Index.* is sorted earlier than other IndexNodes.

        # Otherwise, lexical sort on node.name'''
    if not isinstance(b, BaseNode):
        raise NotImplementedError("ffffff")

    # Show dirs before files
    if isinstance(a, IndexNode) and isinstance(b, PathNode):
        return False
    if isinstance(a, PathNode) and isinstance(b, IndexNode):
        return True

    if isinstance(b, (PathNode, HighestVersionFsSymlinkNode)) and isinstance(a, (PathNode, HighestVersionFsSymlinkNode)):
        # log.info('is %s < %s', a, b)
        # Bubble 'default/' to top
        if a.name == 'default':
            return True
        if b.name == 'default':
            return False

    # sort version dirs by semvert
    if isinstance(b, PathNode) and isinstance(a, PathNode) and \
            hasattr(b, 'version') and hasattr(a, 'version'):
        # log.info('comparing a.version < b.version: %s < %s == %s',
        #          a.version, b.version,
        #          semantic_version.Version(a.version) < semantic_version.Version(b.version))

        # Note that we want higher versions shown earlier, so this is flipped
        return semantic_version.Version(a.version) > semantic_version.Version(b.version)

    # index files before other files
    if isinstance(a, IndexNode) and isinstance(b, IndexNode):
        if a.name in ('index.html', 'index.json'):
            return True
        if b.name in ('index.html', 'index.json'):
            return False

    # lexical sort by name
    return a.name < b.name


NODE_TYPE_MAP = {
    'PathNode': PathNode,
    'CollectionIndexJsonNode': CollectionIndexJsonNode,
    'FsSymlinkNode': FsSymlinkNode,
    'HighestVersionFsSymlinkNode': HighestVersionFsSymlinkNode,
    'IndexNode': IndexNode,
    'IndexJinjaNode': IndexJinjaNode,
    'IndexJsonNode': IndexJsonNode,
    'IndexHtmlNode': IndexHtmlNode,
    'IndexFileListNode': IndexFileListNode,
    'IndexBytesNode': IndexBytesNode,
    'IndexArtifactNode': IndexArtifactNode,
    'IndexSha256sumNode': IndexSha256sumNode,
    'ListIndexJsonNode': ListIndexJsonNode,
    'VersionsIndexJsonNode': VersionsIndexJsonNode,
    'Unknown': BaseNode,
}


# try to import the result
def node_class_factory(parent, **attrs):
    # if parent and parent.name == 'collections':
    #    log.debug('parent: %s', parent)
    #    log.debug('**attrs: %s', dict(attrs))
    # log.debug('attrs.get(_node_type): %s', attrs.get('_node_type'))
    if attrs.get('_node_type') == 'IndexArtifactNode':
        log.debug('parent: %s', parent)
        log.debug('**attrs: %s', dict(attrs))

    # log.debug('_node_type: %s', attrs.get('_node_type', 'Unknown'))
    # node_class = NODE_TYPE_MAP[attrs.get('_node_type', 'Unknown')]
    node_class = NODE_TYPE_MAP[attrs.get('_node_type', 'Unknown')]
    return node_class(parent=parent, **attrs)
