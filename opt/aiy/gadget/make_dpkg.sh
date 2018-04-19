#!/bin/bash

# set -x
set -e

SCRIPT_DIR=$(dirname $(readlink -f $0))
WORK_DIR=$(mktemp -d)


mkdir -p ${WORK_DIR}/aiy-gadget-0.1/opt/aiy/
git worktree add --detach ${WORK_DIR}/aiy-gadget-0.1/debian origin/debian
git worktree add --detach ${WORK_DIR}/aiy-gadget-0.1/gadget origin/master
pushd ${WORK_DIR}/aiy-gadget-0.1
tar cf ${WORK_DIR}/aiy-gadget_0.1.orig.tar.xz gadget
find .

debuild --no-lintian -us -uc

cp ${WORK_DIR}/aiy-gadget_0.1-0_all.deb ${SCRIPT_DIR}
rm -rf ${WORK_DIR}
popd
git worktree prune
