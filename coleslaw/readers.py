import datetime
import glob
import logging
import multiprocessing
import os
import os.path
import pathlib
import tarfile
import tempfile

from anytree import (
    Resolver,
    ResolverError,
)
import anytree.search

import attr

import jinja2

from galaxy_importer.config import Config

from . import loader
from . import models
from .nodes import (
    CollectionIndexJsonNode,
    HighestVersionFsSymlinkNode,
    IndexNode,
    IndexArtifactNode,
    IndexBytesNode,
    IndexFileListNode,
    IndexHtmlNode,
    IndexJinjaNode,
    IndexJsonNode,
    IndexSha256sumNode,
    ListIndexJsonNode,
    PathNode,
    VersionsIndexJsonNode,
)

from . import snapshot
from . import utils


log = logging.getLogger(__name__)
mplog = multiprocessing.get_logger()


class TreeReader:
    def __init__(self):
        self.jinja_env = self.setup_jinja_env()

    def setup_jinja_env(self):
        templates_loader = jinja2.ChoiceLoader([
            jinja2.PackageLoader('coleslaw', 'templates')])
        return jinja2.Environment(loader=templates_loader)

    def populate(self, district_dir, url_prefix):
        # "/"
        base_node = PathNode("",
                             fs_prefix=district_dir,
                             url_prefix=url_prefix,
                             _jinja_env=self.jinja_env)

        ListIndexJsonNode("index.json",
                          parent=base_node,
                          _item_type='PathNode')

        IndexHtmlNode("index.html",
                      parent=base_node,
                      template_name="warehouses_index.html.j2",
                      )

        IndexJinjaNode("ansible.cfg",
                       parent=base_node,
                       template_name="ansible.cfg.j2",
                       )

        # "/content"
        content_node = PathNode('content',
                                parent=base_node,
                                )

        # /content/index.json
        ListIndexJsonNode("index.json",
                          parent=content_node,
                          _item_type='PathNode')

        # /content/index.html
        IndexHtmlNode("index.html",
                      parent=content_node)

        # A list of all the files in the warehouse district dir
        # /FILES.txt
        IndexFileListNode("FILES.txt",
                          parent=base_node,
                          _recursive=True)

        # A list of all the files, except the binary artifacts.
        # For use with `git add --pathspec-from-file`
        # /FILES_NO_ARTIFACTS.txt
        IndexFileListNode("FILES_NO_ARTIFACTS.txt",
                          parent=base_node,
                          # _excluded_types=('IndexArtifactNode',),
                          _recursive=True)

        # A list of the sha256sums for everything we wrote to the output dir
        # /SHA256SUMS
        IndexSha256sumNode("SHA256SUMS",
                           parent=base_node,
                           _recursive=True)

        return base_node


class WarehouseTreeReader(TreeReader):
    def __init__(self, warehouse_info, config_info):
        self.warehouse_info = warehouse_info
        self.config_info = config_info
        super().__init__()

    def setup_jinja_env(self):
        templates_loader = jinja2.ChoiceLoader([
            jinja2.FileSystemLoader(self.warehouse_info.templates_dir),
            jinja2.PackageLoader('coleslaw', 'templates'),
        ])
        return jinja2.Environment(loader=templates_loader)

    def populate(self, parent_node):
        if self.warehouse_info.incremental:
            wh_node = self.load_snapshot()
            if wh_node:
                wh_node.parent = parent_node
                log.debug('snapshot tree:\n%s', utils.render_tree(wh_node))

                return wh_node

        # "/content/{warehouse}/"
        wh_node = PathNode(self.warehouse_info.warehouse_name,
                           parent=parent_node,
                           _jinja_env=self.jinja_env,
                           warehouse_name=self.warehouse_info.warehouse_name,
                           # galaxy_server_name=self.warehouse_info.warehouse_name,
                           )

        # full server url depends on the wh_node url_pth which we dont know at init
        wh_node.galaxy_server_url = f"{self.warehouse_info.server.url}{wh_node.url_pth}"

        api_root = models.APIRoot(available_versions={'v3': 'v3/'})

        # "/content/{warehouse}/index.json
        IndexJsonNode("index.json",
                      parent=wh_node,
                      **attr.asdict(api_root))

        # /content/{warehouse}/index.html
        IndexHtmlNode("index.html",
                      parent=wh_node,
                      server=self.warehouse_info.server.url,
                      # warehouse_name=self.warehouse_info.warehouse_name,
                      template_name="warehouse_index.html.j2",
                      )

        # # /content/{warehouse}/warehouse_info.json
        IndexJsonNode("warehouse_info.json",
                      parent=wh_node,
                      galaxy_server_name=self.warehouse_info.warehouse_name,
                      galaxy_server_url=f"{self.warehouse_info.server.url}{wh_node.url_pth}",
                      )

        IndexJinjaNode("ansible.cfg",
                       parent=wh_node,
                       template_name="ansible.cfg.j2",
                       )

        #  /content/{warehouse}/changes/
        changes_node = PathNode("changes",
                                parent=wh_node,
                                changes=[],
                                )

        #  /content/{warehouse}/changes/index.html
        IndexHtmlNode("index.html",
                      parent=changes_node,
                      )

        #  /content/{warehouse}/changes/index.json
        IndexJsonNode("index.json",
                      parent=changes_node,
                      )

        # "/content/{warehouse}/v3/"
        api_version_node = PathNode("v3",
                                    parent=wh_node,
                                    )

        # "/content/{warehouse}/v3/index.json
        IndexJsonNode("index.json",
                      parent=api_version_node,
                      # This could include the sizes, pkg count, mtimes, etc
                      content_apis={'artifacts': 'artifacts/',
                                    'collections': 'collections/'},
                      whatever_other_info_we_need={"can_go": "here"},
                      )

        # /content/{warehouse}/v3/index.html
        IndexHtmlNode("index.html",
                      parent=api_version_node)

        # "/content/{warehouse}/v3/collections/"
        collections_node = PathNode("collections",
                                    parent=api_version_node,
                                    )
        log.debug('collections_node.path: %s', collections_node.path)

        # /content/{warehouse}/v3/collections/index.json
        ListIndexJsonNode("index.json",
                          _item_type='PathNode',
                          parent=collections_node)

        # /content/{warehouse}/v3/collections/index.html
        IndexHtmlNode("index.html",
                      parent=collections_node)

        # "/content/{warehouse}/v3/artifacts/"
        artifacts_node = PathNode("artifacts",
                                  parent=api_version_node,
                                  )

        # "/content/{warehouse}/v3/artifacts/index.json
        IndexJsonNode("index.json",
                      parent=artifacts_node,
                      artifact_types={'collections': 'collections/'},
                      )

        # /content/{warehouse}/v3/artifacts/index.html
        IndexHtmlNode("index.html",
                      parent=artifacts_node)

        # "/content/{warehouse}/v3/artifacts/collections/"
        artifacts_collection_type_node = PathNode("collections",
                                                  parent=artifacts_node,
                                                  )

        # "/content/{warehouse}/v3/artifacts/collections/index.json
        IndexJsonNode("index.json",
                      parent=artifacts_collection_type_node)

        # /content/{warehouse}/v3/artifacts/collections/index.html
        IndexHtmlNode("index.html",
                      parent=artifacts_collection_type_node)

        # "/content/{warehouse}/v3/artifacts/collections/{warehouse}/"
        artifacts_collection_warehouse_node = \
            PathNode(self.warehouse_info.warehouse_name,
                     parent=artifacts_collection_type_node,
                     )

        # "/content/{warehouse}/v3/artifacts/collections/{warehouse}/index.json
        IndexJsonNode("index.json",
                      parent=artifacts_collection_warehouse_node)

        # /content/{warehouse}/v3/artifacts/collections/{warehouse}/index.html
        IndexHtmlNode("index.html",
                      parent=artifacts_collection_warehouse_node,
                      template_name="artifacts.html.j2")

        # A list of all the files in the warehouse
        # content/my_warehouse/FILES.txt
        IndexFileListNode("FILES.txt",
                          parent=wh_node,
                          _recursive=True)

        # This .gitignore is to avoid import artifact tar.gz files into
        # git if you use the 'FILES.txt' list.
        # For use with `git add --pathspec-from-file`
        # content/my_warehouse/.gitignore
        IndexNode(".gitignore",
                  parent=wh_node,
                  data="content/*/v3/artifacts/collections/*/*.tar.gz")

        # /content/my_warehouse/SHA256SUMS
        IndexSha256sumNode("SHA256SUMS",
                           parent=wh_node,
                           _recursive=True)

        # /content/my_warehouse/v3/artifacts/collections/my_warehouse/SHA256SUMS
        IndexSha256sumNode("SHA256SUMS",
                           parent=artifacts_collection_warehouse_node)

        return wh_node

    def populate_collections(self, wh_node, collection_filenames):
        log.debug('pre expand collection_filesnames: %s', collection_filenames)

        expanded_collection_filenames = list(expand_path_patterns(collection_filenames))
        log.debug('expanded_collection_filenames: %s', expanded_collection_filenames)

        added_names_set, deleted_names_set = calculate_warehouse_delta(expanded_collection_filenames, self.warehouse_info, wh_node)
        # added_collection_filenames = sorted(list([item for item in collection_filenames if item.name in added_names_set]))
        added_collection_filenames = sorted(list([item for item in expanded_collection_filenames if item.name in added_names_set]))
        log.debug('added_collection_filenames: %s', sorted(added_collection_filenames))
        log.debug('added_names_set: %s', sorted(list(added_names_set)))
        log.debug('deleted_names_set: %s', sorted(list(deleted_names_set)))

        collections_loader = load_collections_from_filenames(added_collection_filenames, self.warehouse_info, wh_node)

        log.debug('updating collections for warehouse: %s', self.warehouse_info.warehouse_name)
        # log.debug('render_tree:\n%s', utils.render_tree(base_node))
        # wh_node = actions.update_collections(wh_node, collections_reader, self.warehouse_info)

        r = Resolver('name')

        changes_path = "changes"
        changes_node = r.get(wh_node, changes_path)
        changes_node.changes = getattr(changes_node, 'changes', [])
        if added_names_set or deleted_names_set:
            changes_node.changes.append({'added': sorted(list(added_names_set)),
                                         'removed': sorted(list(deleted_names_set)),
                                         'date': datetime.datetime.now().isoformat()})

        collection_artifacts_reader = CollectionArtifactTreeReader(self.warehouse_info,
                                                                   self.config_info,
                                                                   self.jinja_env)

        wh_node = collection_artifacts_reader.populate(wh_node, collections_loader)

        log.debug('wh_node.pth: %s', wh_node.pth)

        return wh_node

    def load_snapshot(self):
        try:
            snapshot_path = os.path.join(self.config_info.app['snapshot_dir'],
                                         self.warehouse_info.warehouse_name,
                                         'SNAPSHOT.json')

            log.debug('Loading snapshot %s', snapshot_path)
            with open(snapshot_path, 'r') as snapshot_fd:
                wh_node = snapshot.snapshot_load(snapshot_fd)
                wh_node._jinja_env = self.jinja_env
                log.debug('loaded wh_node: %s from %s', wh_node.pth, snapshot_path)
            return wh_node
        except FileNotFoundError:
            log.warning('No snapshot file found at %s', snapshot_path)

        return None


class CollectionArtifactTreeReader(TreeReader):
    def __init__(self, warehouse_info, config_info, jinja_env):
        self.warehouse_info = warehouse_info
        self.config_info = config_info
        self.jinja_env = jinja_env
        super().__init__()

    def populate(self, wh_node, collections_loader):
        '''Add/Update the collections nodes from the collections_loader iterable.'''

        r = Resolver('name')

        server_info = self.warehouse_info.server

        wh_name = self.warehouse_info.warehouse_name
        collections_path = "v3/collections"
        collections_node = r.get(wh_node, collections_path)

        artifacts_collection_warehouse_path = f"v3/artifacts/collections/{wh_name}"
        artifacts_collection_warehouse_node = r.get(wh_node, artifacts_collection_warehouse_path)

        log.debug("collections_node: %s", collections_node)
        log.debug("collections_node.pth: %s", collections_node.pth)

        # add a content/{dist_base_path}/v3/galaxy_repositories/
        # it's index.json would contain per-galaxy-repo contextual info
        # like the set of collections that are deprecated in that repo.
        # Or it's version/timstamp/serialnumber, size, info about url config for pulp and ansible-galaxy
        # etc
        updated_collections = []

        for result in collections_loader:
            # result, artifact_info, collection_filename = result_tup
            # log.debug('result: %r', result)
            # log.debug('artifact_info: %s', result.artifact_info)

            namespace = result.metadata.namespace
            name = result.metadata.name
            version = result.metadata.version

            log.debug('handling collection %s.%s.%s', namespace, name, version)

            # We only want one node for each warehouse/{namespace} and
            # {warehouse}/{namespace}/{name}
            # /content/{warehouse}/v3/collections/{namespace}/
            namespace_node = PathNode(namespace)
            namespace_node = collections_node.get_or_add_child(namespace_node)

            # /content/{warehouse}/v3/collections/{namespace}/index.html
            namespace_index_html_node = IndexHtmlNode("index.html")
            namespace_node.get_or_add_child(namespace_index_html_node)

            # /content/{warehouse}/v3/collections/{namespace}/index.json
            namespace_index_json_node = ListIndexJsonNode("index.json",
                                                          _item_type='PathNode')
            namespace_node.get_or_add_child(namespace_index_json_node)

            collection_label = f"{result.metadata.namespace}.{result.metadata.name}"

            # /content/{warehouse}/v3/collections/{namespace}/{name}/
            name_node = namespace_node.get_or_add_child(PathNode(name,
                                                                 collection_label=collection_label))

            try:
                r.get(name_node, "index.html")
            except ResolverError:
                IndexHtmlNode("index.html",
                              parent=name_node,
                              )

            # /v3/collections/{namespace}/{collection_name}/versions/
            try:
                versions_subdir_node = r.get(name_node, 'versions')
            except ResolverError:
                versions_subdir_node = PathNode("versions",
                                                parent=name_node,
                                                )


            # /v3/collections/{namespace}/{collection_name}/versions/index.html
            try:
                # node already created
                r.get(versions_subdir_node, 'index.html')
            except ResolverError:
                IndexHtmlNode("index.html",
                              parent=versions_subdir_node,
                              template_name="collection_versions.html.j2",
                              )

            # /v3/collections/{namespace}/index.json
            try:
                r.get(name_node, "index.json")
            except ResolverError:
                CollectionIndexJsonNode("index.json",
                                        parent=name_node,
                                        versions_url=versions_subdir_node.url_pth)

            # /v3/collections/{namespace}/{collection_name}/versions/index.json
            try:
                # node already created
                r.get(versions_subdir_node, 'index.json')
            except ResolverError:
                VersionsIndexJsonNode("index.json",
                                      parent=versions_subdir_node,
                                      )

            download_url = utils.urljoin(server_info.url,
                                         artifacts_collection_warehouse_node.url_pth,
                                         result.artifact_info.filename)

            log.debug('download_url: %s', download_url)
            log.debug('server_info.url: |%s|, warehouse_node.url_path: |%s|, art.filename: |%s|',
                      server_info.url, artifacts_collection_warehouse_node.url_pth, result.artifact_info.filename)

            # /v3/collections/{namespace}/{collection_name}/versions/{version}
            version_subdir_node = \
                PathNode(version,
                         parent=versions_subdir_node,
                         # nsnv='%s-%s' % (result.metadata.label, version),
                         collection_data=result,
                         metadata=attr.asdict(result.metadata),
                         namespace=result.metadata.namespace,
                         collection=result.metadata.name,
                         collection_label=f"{result.metadata.namespace}.{result.metadata.name}",
                         imported_artifact=True,
                         version=result.metadata.version,
                         artifact_info=result.artifact_info,
                         artifact=attr.asdict(result.artifact_info),
                         artifact_file_basename=result.artifact_info.filename,
                         mtime=result.artifact_info.mtime,
                         download_url=download_url)

            updated_collections.append(version_subdir_node)

            # Point {namespace}/{name} symlinkt to "default" version of the versions in versions_subdir_node
            try:
                r.get(versions_subdir_node, 'default')
            except ResolverError:
                default_version_symlink_node = \
                    HighestVersionFsSymlinkNode("default",
                                                parent=versions_subdir_node,
                                                # _versions_subdir_node=versions_subdir_node,
                                                # _target_node_fs_pth=versions_subdir_node.fs_pth,
                                                _target_is_directory=True)
                log.debug('default_version_symlink_node: %s', default_version_symlink_node)

            # /v3/collections/{namespace}/{collection_name}/versions/{version}/index.json
            IndexJsonNode("index.json",
                          parent=version_subdir_node,
                          download_url=download_url,
                          namespace={'name': result.metadata.namespace},
                          collection={'name': result.metadata.name},
                          version=result.metadata.version,
                          metadata=attr.asdict(result.metadata),
                          artifact=attr.asdict(result.artifact_info),
                          )

            # /v3/collections/{namespace}/{collection_name}/versions/{version}/README.html
            IndexHtmlNode("README.html",
                          parent=version_subdir_node,
                          template_name="README.html.j2",
                          body_html=result.docs_blob.collection_readme.html,
                          )

            # /v3/collections/{namespace}/{collection_name}/versions/{version}/index.html
            IndexHtmlNode("index.html",
                          parent=version_subdir_node,
                          template_name="collection_version.html.j2",
                          )

            # /v3/collections/{namespace}/{collection_name}/versions/<version>/docs_blob/
            try:
                version_subdir_docs_blob_subdir_node = r.get(version_subdir_node, 'docs_blob')
            except ResolverError:
                version_subdir_docs_blob_subdir_node = PathNode("docs_blob",
                                                                parent=version_subdir_node,
                                                                )

            # log.debug('result.docs_blob: %s', result.docs_blob)
            # /v3/collections/{namespace}/{collection_name}/versions/{version}/docs_blob/index.json
            IndexJsonNode("index.json",
                          parent=version_subdir_docs_blob_subdir_node,
                          **attr.asdict(result.docs_blob))

            # /v3/collections/{namespace}/{collection_name}/versions/{version}/docs_blob/index.html
            IndexHtmlNode("index.html",
                          parent=version_subdir_docs_blob_subdir_node,
                          template_name="collection_version_docs_blob.html.j2",
                          docs_blob=attr.asdict(result.docs_blob),
                          )

            # /v3/collections/{namespace}/{collection_name}/versions/{version}/MANIFEST.json
            IndexBytesNode("MANIFEST.json",
                           parent=version_subdir_node,
                           b_filecontents=result.b_manifest)

            # /v3/collections/{namespace}/{collection_name}/versions/{version}/FILES.json
            # (or whatever files_manifest_filename points to)
            IndexBytesNode(result.file_manifest_filename,
                           parent=version_subdir_node,
                           b_filecontents=result.b_file_manifest)

            # Add the artifact file entry into the cousin 'artifacts' branch for download
            # /v3/artifacts/collections/{warehouse_name}/{namespace}-{name}.{version}.tar.gz
            IndexArtifactNode(result.artifact_info.filename,
                              parent=artifacts_collection_warehouse_node,
                              collection_filename=result.artifact_info.full_path,
                              file_size=result.artifact_info.size,
                              mtime=result.artifact_info.mtime,
                              )

            # TODO: yield a progress?
        return wh_node


def load_collection(collection_path, warehouse_info):
    log.debug('loading CollectionArtifact from %s', collection_path)

    with tempfile.TemporaryDirectory() as tmp_dir:
        with open(collection_path, 'rb') as b_collection_fo:
            sub_path = 'ansible_collections/placeholder_namespace/placeholder_name'
            extract_dir = os.path.join(tmp_dir, sub_path)
            with tarfile.open(fileobj=b_collection_fo, mode='r') as pkg_tar:
                def is_within_directory(directory, target):
                    
                    abs_directory = os.path.abspath(directory)
                    abs_target = os.path.abspath(target)
                
                    prefix = os.path.commonprefix([abs_directory, abs_target])
                    
                    return prefix == abs_directory
                
                def safe_extract(tar, path=".", members=None, *, numeric_owner=False):
                
                    for member in tar.getmembers():
                        member_path = os.path.join(path, member.name)
                        if not is_within_directory(path, member_path):
                            raise Exception("Attempted Path Traversal in Tar File")
                
                    tar.extractall(path, members, numeric_owner) 
                    
                
                safe_extract(pkg_tar, extract_dir)
            dummy_logger = logging.getLogger(__name__ + '._dummy')

            sha256 = utils.sha256sum_from_path(collection_path)
            file_size = os.path.getsize(collection_path)
            mtime = datetime.datetime.utcfromtimestamp(os.path.getmtime(collection_path)).isoformat()

            artifact_info = models.ArtifactInfo(filename=os.path.basename(collection_path),
                                                full_path=collection_path,
                                                sha256=sha256,
                                                mtime=mtime,
                                                size=file_size)

            cfg = Config(config_data=warehouse_info.galaxy_importer_config)
            collection_loader = loader.CollectionAndManifestLoader(extract_dir,
                                                                   str(collection_path),
                                                                   cfg=cfg,
                                                                   logger=dummy_logger)
            import_result = collection_loader.load()

            loader_result = models.LoaderResult(metadata=import_result.metadata,
                                                docs_blob=import_result.docs_blob,
                                                contents=import_result.docs_blob,
                                                artifact_info=artifact_info,
                                                b_file_manifest=collection_loader.b_file_manifest,
                                                b_manifest=collection_loader.b_manifest,
                                                file_manifest_filename=collection_loader.file_manifest_filename,
                                                )

            return loader_result


def calculate_warehouse_delta(collection_filenames, warehouse_info, wh_node):
    r = Resolver("name")
    artifacts_collection_warehouse_path = f"v3/artifacts/collections/{warehouse_info.warehouse_name}"

    try:
        artifacts_collection_warehouse_node = r.get(wh_node, artifacts_collection_warehouse_path)
    except ResolverError as exc:
        log.exception(exc)
        raise

    import pprint
    pf = pprint.pformat
    log.debug('tree:\n%s', utils.render_tree(wh_node))
    log.debug('artifacts_collection_warehouse_node: %s', pf(artifacts_collection_warehouse_node))
    log.debug('artifacts_collection_warehouse_node.path: %s', artifacts_collection_warehouse_node.path)
    log.debug('artifacts_collection_warehouse_node.children: %s', pf(artifacts_collection_warehouse_node.children))

    artifact_nodes = anytree.search.findall_by_attr(artifacts_collection_warehouse_node, "IndexArtifactNode", name="_node_type")

    log.debug('artifact_nodes:\n%s', pprint.pformat([a for a in artifact_nodes]))

    all_artifact_nodes = anytree.search.findall_by_attr(wh_node,
                                                        "IndexArtifactNode", name="_node_type")
    log.debug('all_artifact_nodes:\n%s', pprint.pformat([a for a in all_artifact_nodes]))

    previous_existing_paths = [pathlib.Path(y.collection_filename) for y in artifact_nodes]
    previous_existing_basenames = [x.name for x in previous_existing_paths]
    log.debug('previous_existing_basenames: %s', previous_existing_basenames)

    existing_paths = [p for p in previous_existing_paths if p.exists()]
    existing_basenames = [p.name for p in existing_paths]
    log.debug('existing_basenames: %s', existing_basenames)

    collection_filenames = list(collection_filenames)
    requested_basenames = list([p.name for p in collection_filenames])

    existing_set = set(existing_basenames)
    previous_existing_set = set(previous_existing_basenames)
    requested_set = set(requested_basenames)

    new_set = requested_set - existing_set

    # deleted_set = previous_existing_set - existing_set
    deleted_set = existing_set - requested_set

    log.debug('previsou_existing_set:\n%s', pprint.pformat(sorted(list(previous_existing_set))))
    log.debug('existing_set:\n%s', pprint.pformat(sorted(list(existing_set))))
    log.debug('requested_set:\n%s', pprint.pformat(sorted(list(requested_set))))

    log.debug('existing - requested:\n%s', pprint.pformat(sorted(list(existing_set - requested_set))))
    log.debug('prev_existing - existing:\n%s', pprint.pformat(sorted(list(previous_existing_set - existing_set))))
    log.debug('requested_set - previous_existing_set:\n%s', pprint.pformat(sorted(list(requested_set - previous_existing_set))))
    log.debug('request_set - existing_set (new_set):\n%s', pprint.pformat(sorted(list(new_set))))

    # new_collection_filenames = list([item for item in collection_filenames if item.name in new_set])

    return new_set, deleted_set


def expand_path_patterns(path_patterns):
    for path_pattern in path_patterns:
        for path in glob.iglob(str(path_pattern)):
            yield pathlib.Path(path).resolve()


# helper for mp.Pool.imap_async since it only takes one arg
def collection_paths(filenames, wh_info):
    for filename in filenames:
        yield filename, wh_info


def load_collection_tuple(path_and_info):
    return load_collection(path_and_info[0], path_and_info[1])


def load_collections_from_filenames(collection_filenames, warehouse_info, wh_node):

    #    filtered_collection_filenames = filter_artifacts_already_in_tree(expand_path_patterns(collection_filenames), warehouse_info, wh_node)

    with multiprocessing.Pool() as pool:
        import_iterator = pool.imap_unordered(load_collection_tuple,
                                              collection_paths(collection_filenames, warehouse_info),
                                              chunksize=1)

        pool.close()

        for import_result in import_iterator:
            log.debug('yielding %s', import_result.artifact_info.filename)
            yield import_result

        pool.join()
