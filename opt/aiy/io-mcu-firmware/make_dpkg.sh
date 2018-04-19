#!/bin/bash

# set -x
set -e

SCRIPT_DIR=$(dirname $(readlink -f $0))
WORK_DIR=$(mktemp -d)

VERSION=0.2
AIY_IO_MCU_FIRMWARE_PREFIX=aiy-io-mcu-firmware
AIY_IO_MCU_FIRMWARE_PATH=${AIY_IO_MCU_FIRMWARE_PREFIX}-${VERSION}
AIY_IO_MCU_DEB_PATH=${AIY_IO_MCU_FIRMWARE_PREFIX}_${VERSION}

mkdir -p ${WORK_DIR}/${AIY_IO_MCU_FIRMWARE_PATH}/opt/aiy
git worktree add --detach ${WORK_DIR}/${AIY_IO_MCU_FIRMWARE_PATH}/debian origin/debian
git worktree add --detach ${WORK_DIR}/${AIY_IO_MCU_FIRMWARE_PATH}/io-mcu-firmware origin/master
pushd ${WORK_DIR}/${AIY_IO_MCU_FIRMWARE_PATH}
tar cf ${WORK_DIR}/${AIY_IO_MCU_DEB_PATH}.orig.tar.xz io-mcu-firmware
find .

debuild --no-lintian -us -uc

ls ${WORK_DIR}/${AIY_IO_MCU_FIRMWARE_PATH}*
cp ${WORK_DIR}/${AIY_IO_MCU_DEB_PATH}-0_all.deb ${SCRIPT_DIR}
rm -rf ${WORK_DIR}
popd
git worktree prune
