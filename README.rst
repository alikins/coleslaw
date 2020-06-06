========
coleslaw
========


.. image:: https://img.shields.io/pypi/v/coleslaw.svg
        :target: https://pypi.python.org/pypi/coleslaw

.. image:: https://img.shields.io/travis/alikins/coleslaw.svg
        :target: https://travis-ci.com/alikins/coleslaw

.. image:: https://readthedocs.org/projects/coleslaw/badge/?version=latest
        :target: https://coleslaw.readthedocs.io/en/latest/?badge=latest
        :alt: Documentation Status




Create a static ansible-galaxy collection warehouse for a set of
ansible galaxy collection artifacts.

The generated static content is served from a web server and
can be used as galaxy server with ansible-galaxy 2.9 or higher.




* Free software: Apache Software License 2.0
* Documentation: https://coleslaw.readthedocs.io.

Use
---

Create a output dir. Somewhere shareable by a web server ideally.::

    $ mkdir /var/www/data/html/my_warehouses

Choose a name for a 'warehouse', something like 'awesomeco_prod' or 'awesomeco_test' etc.
This is more or less similar to naming a yum or dnf repo.

Figure out the name of the server that the warehouses will be hosted on (ie, figure out
what the first part of the url should be). Something like 'http://ansible.example.com/ansible_collections/'

Point coleslaw at a set of collection artifacts and the output dir and generate the content::

    $ coleslaw --server="http://ansible.example.com/ansible_collections/" --warehouse "awesomeco_test" --output-dir "/var/www/data/html/my_warehouses/" /data/ansible/collections/*.tar.gz


Then point ansible-galaxy config to 'http://ansible.example.com/ansible_collections/'::

    [galaxy]
    server_list = my_warehouses

    [galaxy_server.my_warehouses]
    url=http://ansible.example.com/ansible_collections/


Features
--------

* Share a set of ansible collections so they can be installed with ansible-galaxy

TODO
----

- Support incremental updates

  + Add loaders/models for loading the generated tree

  + ~~add tree node hooks for attach/detach~~

  + ~~Load existing warehouse, then find, load, and add new collection artifacts to tree
    - build list of additions to tree, then just generate them~~

  + ~~Read/write a tree SNAPSHOT file.~~
`
- Support loading of the ansible_collections directories that ansible uses to store
  collections. (And the format that 'ansible-galaxy' actually installs them as).

  * The main diff is the ANSIBLE_COLLECTIONS_PATH format has no way to install more
    that one version of a collection.

    + ie, the path ansible_collections/{namespace}/{name}/ doesn't include the collection
      version, so more than one version conflicts

- Extract the artifact archive and add it to generated static content, so the collection
  contents can be explored. Possible as raw files, maybe also as wrapped html.

    + possibly symlink trees or a content-aware cache or even just check it all into git?

- cli pre/post hooks

  + build a CHANGELOG (partially done)

  + commit to git

  + trigger syncs to cdn

- Fill in missing indexes in the existing galaxy v3 api format.

  + /content/index.json -> list of warehouses

  + /content/{warehouse}/v3/index.json -> list of content types (ie, artifacts and collection metadata)

  + /content/{warehouse}/v3/collections/{namespace}/index.json -> list of namespaces

  + /content/{warehouse}/v3/collections/{namespace}/index.json -> list of collections in the namespace

  + /content/{warehouse}/v3/collections/{namespace}/{name}/index.json -> basic info about the collection

  + /content/{warehouse}/v3/artifacts/index.json -> list of artifact types (ie, just 'collections' atm)

  + /content/{warehouse}/v3/artifacts/collections/index.json -> list of warehouses

  + /content/{warehouse}/v3/artifacts/collections/{warehouse} -> list of collection artifacts in this warehouse

  + ~~/content/{warehouse}/v3/artifacts/collections/{warehouse}/SHA256SUMS -> list of sha256sums for collection artifacts in this warehouse~~

  + ~~/content/{warehouse}/v3/artifacts/collections/{warehouse}/SHA256SUMS.json -> list of sha256sums for collection artifacts in this warehouse~~

  + /content/{warehouse}/v3/artifacts/collections/{warehouse}/{namespace}.{name}.{version}.json -> The artifact info (sha, size, filename) for each artifact

- ~~Add a config file for defining general options (like cli stuff) as well as pre-defining a
  list of warehouses to build. yaml? maybe include coleslaw.cfg.d/\*.yaml~~

- implement loading data as a task queue
  (currently uses a multiprocessing.Pool)

  + persisted to disk

  + with worker processes

  + loader_task_producer

  + loader_task_consumer

  + As tree is walked/visited, add generation and io
      to metadata_task_producer
  + metadata_task_consumer workers to pick up queued tasks
     and do them (serialize json, html, copy files, io)

- Add mechanism for detached gpg signatures (pygnupg?)
  + for artifacts

  + manifests, SHA256SUM, etc

- global cache

  + should be able to do a content-addressable style global cache that
   is shared across invocations. Potentially making updates or rebuilds
   faster.

 + Add a content-addressable style fs/url layout?

   * ala, .git/objects/*

   * /{warehouse}/store/

- Make sure the versions/ index page list siblings in correct version order

- "aliases" Add a content/shortnames/ tree with "link" entries in "namespace.name-version" format
  that link to /content/v3/collections/namespace/name/versions/version/

  + and shortnames/namespace.name -> /content/v3/collections/namespace/name/

  + and shortnames/namespace -> /content/v3/collections/namespace/

  + Or maybe just provide example http server configs that use url rewrite rules
    to do something similar

- Add /errors/404.html 403.json etc to generated content. So webservers can serve static
  html and json errors

- use Boltons for at least atomic dir/file helpers

- atomic updates

  + maybe add sibling _tmp_XXX_node_name sibling nodes to tree on update, then
    add a tree pass that creates all the _tmp_* path nodes, then another pass that
    repartents _tmp_XXX over the original node and on save, os.rename() _tmp_XXX dir over
    original dir

  + Maybe could use anytree NodeMixin ._pre_*() _post_*() hooks for atomic replace?

- Add a warehouse level html/js file that is a one page app with all the repo
  data loaded into the DOM

- Pass more structured data into templates and html/js so pages can be extended

Maybe

- /tags/{tag}/{collections}/ns-name (link to collection)
  /tags/{tag}/{collection_versions}/ns-name-version

- /authors/{author}/  ^ same as tags

- generate requirements.yml at various levels

  + at collection version level, could extract METADATA.json:requirements -> requirements.yml

  + at namespace level, could have requirements.yml that references all the collections in the namespace

  + at warehouse level, requirements.yml for everything

  + could have requirements.yml per tag or author

- eventually, indexes based on content types

  + /content_types/callbacks/ns-name-version  (ie, show all the collection/cv's with callbacks)

- on read/import of collection artifact, look for associated metadata file ( alikins.foo-1.2.3.tar.gz -> alikins.foo-1.2.3.tar.gz.yml)
  and if found, include the metadata from it into the generated collection info.

    + possibly useful for CI / build info?

- see if any existing collection browser html/js would be license compatible and if so
  possibly integrate it

- include some CI webhook scripts?

  + maybe figure out how to use as github action?

Credits
-------

* Adrian Likins <alikins@redhat.com>


This package was created with Cookiecutter_ and the `audreyr/cookiecutter-pypackage`_ project template.

.. _Cookiecutter: https://github.com/audreyr/cookiecutter
.. _`audreyr/cookiecutter-pypackage`: https://github.com/audreyr/cookiecutter-pypackage
