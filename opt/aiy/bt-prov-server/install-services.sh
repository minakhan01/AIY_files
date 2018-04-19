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

sudo sed -i: \
 's|^ExecStart=.*bluetoothd$|ExecStart=/usr/lib/bluetooth/bluetoothd -C -E|g' \
/lib/systemd/system/bluetooth.service

scripts_dir="$(dirname "${BASH_SOURCE[0]}")"
cd "${scripts_dir}"

sudo cp bt_prov_server.service /lib/systemd/system
systemctl enable bt_prov_server.service