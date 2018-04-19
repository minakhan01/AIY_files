#!/bin/bash

MACHINE_ARCH=$(uname -m)
WHEELS_DIR=/opt/aiy/python-wheels

/usr/bin/python3 - << "EOF"
import google.assistant.library
try:
  google.assistant.library.Assistant(None,'a')
except AttributeError:
  pass
exit(249)
EOF

# If no library found, install the wheel for this machine
if [[ "$?" != "249" ]]; then
    sudo pip3 install --ignore-installed --no-deps \
      ${WHEELS_DIR}/google_assistant_library-0.1.0-py2.py3-none-linux_${MACHINE_ARCH}.whl
else
  PYTHON_SITE_PATH=$(python3 -c 'import site; print(site.getsitepackages()[0]);')
  INSTALLED_ARCH=$(find ${PYTHON_SITE_PATH} | grep google_assistant_library | grep WHEEL | xargs cat | grep ${MACHINE_ARCH})
  if [[ -z ${INSTALLED_ARCH} ]]; then
    sudo pip3 uninstall google-assistant-library
    sudo pip3 install --ignore-installed --no-deps \
      ${WHEELS_DIR}/google_assistant_library-0.1.0-py2.py3-none-linux_${MACHINE_ARCH}.whl
  fi
fi
