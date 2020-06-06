"""Console script for coleslaw."""
import logging
import sys

import click

from . import actions

log = logging.getLogger(__name__)


@click.command()
@click.option('-o', '--output-dir',
              'output_dir',
              help='Directory to write the collection warehouse metadata to',
              type=click.Path(file_okay=False, dir_okay=True, writable=True))
@click.option('-t', '--templates-dir',
              'templates_dir',
              help='Directory where jinja templates are stored',
              type=click.Path(file_okay=False, dir_okay=True, writable=True,
                              exists=True, resolve_path=True))
@click.option('-w', '--warehouse',
              'warehouse_name',
              default='default',
              help='Name of the content warehouse to use (ie, /api/automation-hub/content/{wherehouse}/v3/collections)',
              type=click.STRING)
@click.option('-s', '--server',
              'server',
              default='http://localhost/',
              help='Name and schema of web server (ie, http://collections.example.com/)',
              type=click.STRING)
@click.option('--url-prefix',
              'url_prefix',
              default='',
              help='The url prefix (ie, "warehouse" in http://c.example.com/warehouse/)',
              type=click.STRING)
@click.option('--config',
              'config_file_path',
              default='./coleslaw.yml',
              help='Specify a config file to use (default is ./coleslaw.yml)',
              type=click.Path(file_okay=True, dir_okay=False, writable=False,
                              exists=False, resolve_path=True))
@click.argument('collection_filenames', type=click.Path(exists=True), nargs=-1)
def main(args=None, output_dir=None, templates_dir=None,
         warehouse_name=None, server=None, url_prefix=None,
         config_file_path=None,
         collection_filenames=None):
    """Console script for coleslaw."""

    actions.setup_logging()

    log.debug('args: %s', args)
    log.debug('output_dir: %s', output_dir)
    log.debug('collection_filenames: %s', collection_filenames)
    log.debug('templates_dir: %s', templates_dir)
    log.debug('config_file_path: %s', config_file_path)

    config_info = actions.read_config(config_file_path)

    base_node = actions.build_tree(config_info, collection_filenames)

    actions.export_tree(base_node)

    return 0


if __name__ == "__main__":
    sys.exit(main())  # pragma: no cover
