#!/bin/bash -e

OUTPUT_DIR=~/src/example_galaxycreate/example/
rm -rf "${OUTPUT_DIR:?}/*"

rm ~/.galaxycreate/snapshots/golden/SNAPSHOT.json

time coleslaw --config galaxycreate.yml 2>&1 | tee coleslaw.out

tree "${OUTPUT_DIR}" > tree.out
tree -C "${OUTPUT_DIR}" > treecolor.out
# galaxycreate --warehouse golden --output-dir /tmp/faux/whatever/ ~/src/galaxy-test/collection-releases/alikins-collection_ntp-0.1.193.tar.gz  ~/src/galaxy-test/collection-releases/alikins-collection_inspect-0.0.218.tar.gz ~/src/galaxy-test/collection-releases/alikins-collection_ntp-0.1.191.tar.gz

rm -rf /tmp/tmp-collections-root/*

time ANSIBLE_CONFIG=ansible-golden.cfg ANSIBLE_COLLECTIONS_PATHS=/tmp/tmp-collections-root ansible-galaxy  collection install  alikins.collection_inspect

date
sudo tail -n 5 /var/log/nginx/access.log
