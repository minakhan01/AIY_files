#!/bin/bash
# Copyright 2017 Google Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

set -o errexit

scripts_dir="$(dirname "${BASH_SOURCE[0]}")"
cd "${scripts_dir}"

APT_NONINTERACTIVE='-y -o Dpkg::Options::=--force-confdef -o Dpkg::Options::=--force-confold'
export DEBCONF_FRONTEND=noninteractive
sudo apt-get install $APT_NONINTERACTIVE --no-install-recommends \
  libbluetooth-dev python3-pip python3-dbus
sudo pip3 install pybluez