import logging

import anytree

from . import snapshot
from . import utils

log = logging.getLogger(__name__)


class TreeExport():
    def __init__(self, root_node):
        self.root_node = root_node
        self.log = logging.getLogger(__name__ + '.' + self.__class__.__name__)

    # TODO: Replace with a tree walker or iterater
    def export(self):
        self.log.debug('render_tree:\n%s', utils.render_tree(self.root_node))

        log.debug('Reserving paths for %s', self.root_node)
        for node in anytree.PreOrderIter(self.root_node):
            node.reserve()

        log.debug('Saving nodes for %s', self.root_node)
        for node in anytree.PreOrderIter(self.root_node):
            node.save()

        return

    def snapshot(self, snapshot_path):
        log.debug('saving SNAPSHOT.json at %s', snapshot_path)
        with open(snapshot_path, 'w') as snapshot_fo:
            snapshot.snapshot_dump(self.root_node, snapshot_fo)

        return
