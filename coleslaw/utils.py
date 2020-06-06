import hashlib
import logging

from anytree import RenderTree

log = logging.getLogger(__name__)


def sha256sum_from_path(filename):
    block_size = 65536
    sha256 = hashlib.sha256()
    with open(filename, 'rb') as fo:
        for block in iter(lambda: fo.read(block_size), b''):
            sha256.update(block)
    return sha256.hexdigest()


# From https://stackoverflow.com/a/11326230
def urljoin(*args):
    """
    Joins given arguments into an url. Trailing but not leading slashes are
    stripped for each argument.
    """
    return '/'.join(str(a).rstrip('/') for a in args + ('',) if a)


def render_tree(root, fields_to_truncate=None, by_attr=None):
    fields_to_truncate = fields_to_truncate or ['collection_data',
                                                'metadata',
                                                'artifact',
                                                'artifact_info',
                                                'collection_readme',
                                                'contents',
                                                ]
    lines = []
    # by_attr = True

    def sorter(nodes):
        return sorted(nodes)

    render_tree = RenderTree(root, childiter=sorter)
    # render_tree = RenderTree(root)
    return str(render_tree.by_attr("label"))

    for pre, fill, node in render_tree.by_attr():
        # args = ["%r" % node.separator.join([""] + [str(subnode.name) for subnode in node.path])]
        # lines.append("%s%s" % (pre, node.namei))
        upper = node.name.upper()
        len_upper = len(upper)
        len_upper = 4        # lines.append("%s%s:%s" % (pre, upper, ''.join(args)))
        # lines.append("%s%s " % (pre, upper))
        lines.append("%s%s " % (pre, node.pth))
        # lines.append("%s%s  _node_type=%s" % (fill, ' '*len_upper, getattr(node, '_node_type', None)))
        # try:
        #     # lines.append("%s%s  fs_pth = %s" % (fill, ' '*len_upper, node.fs_pth))
        #     lines.append("%s%s  pth = %s" % (fill, ' '*len_upper, node.pth))
        # except AttributeError:
        #     pass
        data = node.asdict()
        for field in data:
            # value = getattr(node, field, None)
            value = data.get(field, None)
            if field.startswith('_NodeMixin__'):
                continue
            if field.startswith('b_') or isinstance(value, bytes):
                continue
            if field in fields_to_truncate:
                value = '<... value has been truncated ...>'
            lines.append("%s%s  %s = %s" % (fill, ' '*len_upper, field, value or ''))

        # lines.append("%s%s other_fields=%s" % (fill, ' '*len_upper, ','.join([x for x in node.__dict__])))
        # if getattr(node, 'b_file_manifest', None):
        #    lines.append("%s%s  url_pth=%s" % (fill, ' '*len_upper, node.b_file_manifest))
    return '\n'.join(lines)


class NodeEventLoggingMixin:
    def _kid_names(self, children):
        return [x.pth for x in children]

    def _pre_detach_children(self, children):
        """Method call before detaching `children`."""
        log.debug('_pre_detach_children(%s)', self._kid_names(children))

    def _post_detach_children(self, children):
        """Method call after detaching `children`."""
        log.debug('_post_detach_children(%s)', self._kid_names(children))

    def _pre_attach_children(self, children):
        """Method call before attaching `children`."""
        log.debug('_pre_attach_children(%s)', self._kid_names(children))

    def _post_attach_children(self, children):
        """Method call after attaching `children`."""
        log.debug('_post_attach_children(%s)', self._kid_names(children))

    def _pre_detach(self, parent):
        """Method call before detaching from `parent`."""
        log.debug('_pre_detach(%s)', parent.pth)

    def _post_detach(self, parent):
        """Method call after detaching from `parent`."""
        log.debug('_post_detach(%s)', parent.pth)

    def _pre_attach(self, parent):
        """Method call before attaching to `parent`."""
        log.debug('_pre_attach(%s)', parent.pth)

    def _post_attach(self, parent):
        """Method call after attaching to `parent`."""
        log.debug('_post_attach(%s)', parent.pth)
