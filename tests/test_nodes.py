import json
import logging
import os.path

import anytree

import pytest

from coleslaw import nodes

log = logging.getLogger(__name__)


def debug(node):
    log.debug("node: %s", node)
    log.debug("node.path %s", node.path)
    log.debug("repr(node) %r", node)
    log.debug('fs_pth: %s', node.fs_pth)
    log.debug("url_pth: %s", node.url_pth)
    # log.debug("_url_pth: %s", node._url_pth)
    log.debug('node.root: %s', node.root)
    log.debug('renderTree:\n%s', anytree.RenderTree(node.root))
    for n in node.path:
        log.debug('n.fs_pth: %s n.url_pth: %s', n.fs_pth, n.url_pth)


def test_path_node_empty():
    path_node = nodes.PathNode("")
    debug(path_node)

    assert isinstance(path_node, nodes.PathNode)
    assert isinstance(path_node, anytree.NodeMixin)

    fs_pth = path_node.fs_pth
    assert fs_pth == "."

    url_pth = path_node.url_pth
    assert url_pth == ""


@pytest.fixture
def small_tree():
    a = nodes.PathNode(name="", fs_prefix="/dev/null/foo", url_prefix="foo")
    b = nodes.PathNode("bee", parent=a)
    c = nodes.PathNode("cee", parent=b)
    nodes.PathNode("be1", parent=b)
    return c, ("bee", "cee")


@pytest.mark.parametrize("name,output_dir,node_args,exp_fs_pth,exp_url_pth", [
    ("content", "/dev/null/foo", {}, "content", "content/"),
    ("blip", "/dev/null/foo", {}, "blip", "blip/"),
#    ("two_roots", "/another_root", {"fs_path": "/another_root"}, "another_root", "two_roots"),
])
def test_path_node(name, output_dir, node_args, exp_fs_pth, exp_url_pth, small_tree):
    path_node = nodes.PathNode(name, parent=small_tree[0], **node_args)
    debug(path_node)

    log.debug("fs: %s url: %s", exp_fs_pth, exp_url_pth)
    assert isinstance(path_node, nodes.PathNode)
    assert isinstance(path_node, anytree.NodeMixin)

    fs_pth = path_node.fs_pth
    assert fs_pth == os.path.join(output_dir, *small_tree[1], exp_fs_pth)

    url_pth = path_node.url_pth
    assert url_pth == "%s/bee/cee/%s" % ("foo", exp_url_pth)


@pytest.mark.parametrize("name,output_dir,node_args,exp_fs_pth,exp_url_pth", [
    ("index.html", "/dev/null/foo", {}, "index.html", "index.html"),
    ("SHA256SUMS", "/dev/null/foo", {}, "SHA256SUMS", "SHA256SUMS"),
])
def test_index_node(name, output_dir, node_args, exp_fs_pth, exp_url_pth, small_tree):
    index_node = nodes.IndexNode(name, parent=small_tree[0], **node_args)
    debug(index_node)

    log.debug("exp_fs: %s exp_url: %s", exp_fs_pth, exp_url_pth)
    assert isinstance(index_node, nodes.IndexNode)
    assert isinstance(index_node, anytree.NodeMixin)

    fs_pth = index_node.fs_pth
    assert fs_pth == os.path.join(output_dir, *small_tree[1], exp_fs_pth)

    url_pth = index_node.url_pth
    assert url_pth == "%s/bee/cee/%s" % ("foo", exp_url_pth)


node_classes = [node_class for node_class in nodes.NODE_TYPE_MAP.values()]


@pytest.mark.parametrize("Node_Class",
                         node_classes)
def test_node_init(Node_Class):
    name = "test_%s" % Node_Class.__name__
    node = Node_Class(name=name)
    assert isinstance(node, Node_Class)
    assert node._node_type == Node_Class.__name__


@pytest.mark.parametrize("Node_Class",
                         node_classes)
def test_node_as_dict(Node_Class):
    name = "test_%s" % Node_Class.__name__
    node = Node_Class(name=name)
    assert isinstance(node, Node_Class)

    data = node.asdict()
    log.debug('data: %s', data)
    assert isinstance(data, dict)

    assert data['_node_type'] == Node_Class.__name__

    for excluded in Node_Class._exclude_attrs:
        assert excluded not in data


@pytest.mark.parametrize("Node_Class",
                         node_classes)
def test_node_can_be_json_serialized(Node_Class):
    name = "test_%s" % Node_Class.__name__
    node = Node_Class(name=name)
    assert isinstance(node, Node_Class)

    data = node.asdict()
    log.debug('data: %s', data)
    json_data = json.dumps(data, indent=4)
    log.debug('json_data:\n%s', json_data)


@pytest.mark.parametrize("Node_Class",
                         node_classes)
def test_node_arbitrary_field(Node_Class):
    name = "test_%s" % Node_Class.__name__
    some_value = [1, 1.11, "one", [], {'a': 'A'}]
    node = Node_Class(name=name, some_field=some_value)
    assert isinstance(node, Node_Class)

    assert node.some_field == some_value
