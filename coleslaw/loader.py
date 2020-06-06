import logging
import os

from galaxy_importer.collection import CollectionLoader
from galaxy_importer import exceptions as exc
from galaxy_importer import schema

log = logging.getLogger(__name__)


class CollectionAndManifestLoader(CollectionLoader):
    def __init__(self, path, filename, cfg=None, logger=None):
        super().__init__(path, filename, cfg=cfg, logger=logger)

        # keep ref to the MANIFEST.json contents as bytes
        self.b_manifest = None

        self.file_manifest_filename = None
        self.b_file_manifest = None
        # self.galaxy_yml = None

    def _load_collection_manifest(self):
        manifest_file = os.path.join(self.path, 'MANIFEST.json')
        if not os.path.exists(manifest_file):
            raise exc.ManifestNotFound(f'No manifest file ("{manifest_file}") found in collection from {self.filename}')

        # read as bytes to ensure exact match for shasum/sigs
        with open(manifest_file, 'rb') as f:
            self.b_manifest = f.read()

        with open(manifest_file, 'r') as f:
            manifest = f.read()
            try:
                data = schema.CollectionArtifactManifest.parse(manifest)
            except ValueError as e:
                error_msg = f'Error loading artifact manifest "{manifest_file}" from {self.filename}: {str(e)}'
                raise exc.ManifestValidationError(error_msg)
            self.metadata = data.collection_info

            # side effect, bit file_manifest_filename is used elsewhere
            self.file_manifest_filename = data.file_manifest_file['name']

            file_manifest = os.path.join(self.path, self.file_manifest_filename)
            if not os.path.exists(file_manifest):
                raise exc.ManifestNotFound(f'No file_manifest_file ({file_manifest} found in collection from {self.filename}')
            with open(file_manifest, 'rb') as fmf:
                self.b_file_manifest = fmf.read()
