#!/bin/bash

# set -x
set -e

SCRIPT_DIR=$(dirname $(readlink -f $0))
WORK_DIR=$(mktemp -d)

VERSION=0.1
AIY_VOICE_SERVICE_PREFIX=aiy-voice-services
AIY_VOICE_SERVICE_PATH=${AIY_VOICE_SERVICE_PREFIX}-${VERSION}
AIY_VOICE_SERVICE_DEB_PATH=${AIY_VOICE_SERVICE_PREFIX}_${VERSION}

mkdir -p ${WORK_DIR}/${AIY_VOICE_SERVICE_PATH}/opt/aiy
git worktree add --detach ${WORK_DIR}/${AIY_VOICE_SERVICE_PATH}/debian origin/debian
git worktree add --detach ${WORK_DIR}/${AIY_VOICE_SERVICE_PATH}/voice-services origin/master
pushd ${WORK_DIR}/${AIY_VOICE_SERVICE_PATH}
tar cf ${WORK_DIR}/${AIY_VOICE_SERVICE_DEB_PATH}.orig.tar.xz voice-services
find .

debuild --no-lintian -us -uc

ls ${WORK_DIR}/${AIY_VOICE_SERVICE_PATH}*
cp ${WORK_DIR}/${AIY_VOICE_SERVICE_DEB_PATH}-0_all.deb ${SCRIPT_DIR}
rm -rf ${WORK_DIR}
popd
git worktree prune
