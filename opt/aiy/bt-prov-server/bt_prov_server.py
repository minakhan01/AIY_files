#!/usr/bin/python3
"""AIY provisioning Bluetooth server.

Enables BT in discoverable mode, waits for rfcomm connections, acts on and
responds to protobuf encoded provisioning related messages.
"""
import argparse
import bluetooth
import dbus
import hashlib
import logging
import logging.handlers
import os
import pathlib
import random
import shutil
import signal
import string
import struct
import subprocess
import sys
import threading
import time

import messages_pb2
from sta_wpas_client import StaWpasClient
from aiy_trigger import AiyTrigger

DEVICE_NAME_FILE = "/home/pi/.config/aiy/device_name"
BT_SERVICE_UUID = "b3e6fae8-af98-11e7-bd52-db14af10432c"
PROTOCOL_VERSION = 1

KITS_NAMES = {0: "Kit", 1: "Voice", 2: "Vision", 3: "Voice"}

_closables = []


def _SignalHandler(signum, frame):  # pylint: disable=unused-argument
  print("\nCaught signal %d\n" % signum)
  for closable in _closables:
    closable.Close()


def _ExceptionHandler(exc_type, exc_value, exc_traceback):
  sys.__excepthook__(exc_type, exc_value, exc_traceback)
  os.kill(os.getpid(), signal.SIGINT)


class BtProvServer(object):
  """Provisioning Bluetooth server."""

  def __init__(self, enable_trigger=True):
    self._lock = threading.Lock()
    self._cond = threading.Condition(self._lock)
    self._logger = logging.getLogger("logger")
    self._wpas_client = StaWpasClient()
    self._server_socket = None
    self._client_socket = None
    self._adapter = dbus.Interface(dbus.SystemBus().get_object(
        "org.bluez", "/org/bluez/hci0"), "org.freedesktop.DBus.Properties")
    self._adapter.Set("org.bluez.Adapter1", "Powered", dbus.Boolean(1))

    self._ReadKitId()
    self._ReadIdentifier()
    self._name_thread = self._NameThread(self, DEVICE_NAME_FILE)
    self._UpdateDeviceName(self._name_thread.ReadName())
    self._name_thread.start()

    self._closed = False
    self._triggered = False
    if enable_trigger and self._kit_id != 0:
      # AIY kit detected, use its trigger mechanism.
      self._trigger = AiyTrigger(self._Triggered)
    else:
      # No external trigger.
      self._trigger = None

  def __del__(self):
    self.Close()

  def HasTrigger(self):
    return self._trigger is not None

  def Close(self):
    """Closes the server and all assiciated resources."""
    with self._lock:
      if self._closed:
        return
      self._closed = True
      self._cond.notifyAll()

    self._name_thread.Close()
    self._wpas_client.Close()
    if self._client_socket is not None:
      self._client_socket.close()
    if self._server_socket is not None:
      self._server_socket.close()
    self._SetDiscoverable(False)
    if (self._trigger):
      self._trigger.Close()

  def Run(self, timeout):
    """Runs the server until Close() is called or timeout expires."""

    # TODO: Add a file exists check to completely disable the server.

    self._WaitForTrigger()
    if self._closed:
      return not self._closed

    # Wait a minute for any already configured network to connect, and
    # if it does don't run the server. If triggered externally always run.
    if not self._triggered and timeout > 0 and self._wpas_client.WaitForNetwork(
        60):
      self._logger.info("Network connected, not running server")
      return not self._closed

    if self.HasTrigger():
      self._trigger.SetActive(True)

    subprocess.call("/usr/bin/sdptool add SP", shell=True)

    self._server_socket = bluetooth.BluetoothSocket(bluetooth.RFCOMM)
    self._server_socket.bind(("", bluetooth.PORT_ANY))
    self._server_socket.listen(1)

    bluetooth.advertise_service(
        self._server_socket,
        "BtProvServer",
        service_id=BT_SERVICE_UUID,
        service_classes=[BT_SERVICE_UUID, bluetooth.SERIAL_PORT_CLASS],
        profiles=[bluetooth.SERIAL_PORT_PROFILE])

    start = time.monotonic()

    while timeout == 0 or time.monotonic() - start < timeout:
      try:
        if timeout > 0:
          left = timeout - (time.monotonic() - start)
          self._server_socket.settimeout(left)
          self._logger.info("Waiting %d seconds for connections", round(left))
        else:
          self._logger.info("Waiting for connections")
        self._SetDiscoverable(True)
        self._client_socket, client_info = self._server_socket.accept()
        self._logger.info("Connection from %s on channel %d", client_info[0],
                          client_info[1])
      except bluetooth.BluetoothError as error:
        self._logger.info("Stop waiting for connections (%s)", error)
        break

      try:
        self._SetDiscoverable(False)
        self._HandleConnection()
      except (IOError, bluetooth.BluetoothError):
        pass
      finally:
        self._client_socket.close()
        self._client_socket = None
        self._logger.info("Connection from %s on channel %d ended",
                          client_info[0], client_info[1])
        if timeout > 0:
          if self._wpas_client.WaitForNetwork(1):
            self._logger.info("Network connected, stopping server")
            break
          else:
            self._logger.info("Connected client didn't connect network")
    self._logger.info("Server done")
    if self.HasTrigger():
      self._trigger.SetActive(False)
    self._triggered = False
    return not self._closed

  def _WaitForTrigger(self):
    with self._lock:
      if not self.HasTrigger():
        return
      while not self._triggered and not self._closed:
        self._logger.info("Waiting for trigger")
        self._cond.wait()
        if self._closed:
          return
        self._logger.info("Triggered externally")

  def _Triggered(self):
    with self._lock:
      self._triggered = True
      self._cond.notifyAll()

  def _ReadKitId(self):
    try:
      with open("/proc/device-tree/hat/product_id", "r") as file:
        id_str = file.read().replace("\x00", "")  # Strip trailing null.
        self._kit_id = int(id_str, 16)
        # This is a load bearing log statement because it validates that
        # we have a name on file for this kit id.
        self._logger.info("Detected kit id %d (%s)", self._kit_id,
                          KITS_NAMES[self._kit_id])
    except Exception as error:
      # Default to a non descriptive id.
      self._logger.error("Reading kit id failed: %s", error)
      self._kit_id = 0

  def _ReadIdentifier(self):
    # Derive from the MCU UUID.
    try:
      with open("/proc/device-tree/hat/uuid", "r") as file:
        uuid_str = file.read().replace("\x00", "")  # Strip trailing null.
        md5 = hashlib.md5()
        md5.update(uuid_str.encode("utf8"))
        digest = md5.digest()
        self._identifier = [str(digest[x] % 10) for x in range(4)]
        self._logger.info("Identifier %s --> %s)", uuid_str, "".join(
            self._identifier))
    except Exception as error:
      # Use random digits instead.
      self._identifier = random.sample((string.digits), 4)
      self._logger.error("Reading identifier failed: %s", error)

  def _DefaultName(self):
    return "%s-" % KITS_NAMES[self._kit_id] + "".join(self._identifier)

  def _UpdateDeviceName(self, device_name):
    if not device_name:
      device_name = self._DefaultName()
      self._name_thread.WriteName(device_name)
    self._SetDeviceName(device_name)

  def _SetDeviceName(self, device_name):
    bt_name = "AIY-%d-%s" % (self._kit_id, device_name)
    with self._lock:
      self._device_name = device_name
    self._logger.info("Setting device name: '%s' ('%s')", device_name, bt_name)
    self._adapter.Set("org.bluez.Adapter1", "Alias", dbus.String(bt_name))

  def _SetDiscoverable(self, discoverable):
    adapter = self._adapter
    if discoverable:
      adapter.Set("org.bluez.Adapter1", "DiscoverableTimeout", dbus.UInt32(0))
      adapter.Set("org.bluez.Adapter1", "Discoverable", dbus.Boolean(1))
      self._HciConfigCommand("leadv 3")
      self._logger.info("Discoverable enabled")
    else:
      adapter.Set("org.bluez.Adapter1", "Discoverable", dbus.Boolean(0))
      self._HciConfigCommand("noleadv")
      self._logger.info("Discoverable disabled")

  def _HciConfigCommand(self, command):
    subprocess.call("/bin/hciconfig hci0 %s" % command, shell=True)

  def _HandleConnection(self):
    while True:
      received = self._ReceiveRequest()
      request = received.WhichOneof("request")
      self._logger.info("Received request '%s'", request)
      if request == "get_state":
        self._HandleGetState()
      elif request == "set_device_name":
        self._HandleSetDeviceName(received.set_device_name)
      elif request == "identify":
        self._HandleIdentify(received.identify)
      elif request == "scan_networks":
        self._HandleScanNetworks(received.scan_networks)
      elif request == "connect_network":
        self._HandleConnectNetwork(received.connect_network)
      else:
        self._logger.info("Received unknown request '%s'", request)
        break

  def _HandleGetState(self):
    response = messages_pb2.Response()
    response.get_state.status = messages_pb2.SUCCESS
    response.get_state.protocol_version = PROTOCOL_VERSION
    response.get_state.kit_id = KIT_ID
    with self._lock:
      response.get_state.device_name = self._device_name
    self._SetWifiInfo(response.get_state.wifi_info)
    self._SendMessage(response)

  def _HandleSetDeviceName(self, request):
    response = messages_pb2.Response()
    self._logger.info("Request to set device name to '%s'", request.device_name)
    self._UpdateDeviceName(request.device_name)
    with self._lock:
      response.set_device_name.device_name = self._device_name
    if request.device_name == response.set_device_name.device_name:
      response.set_device_name.status = messages_pb2.SUCCESS
    else:
      response.set_device_name.status = messages_pb2.FAILURE
    self._SendMessage(response)

  def _HandleIdentify(self, request):
    self._logger.info("Identify: %s", request.data)
    response = messages_pb2.Response()
    response.identify.status = messages_pb2.SUCCESS
    response.identify.data = "Test response to identify"
    self._SendMessage(response)

  def _HandleScanNetworks(self, request):
    if request.timeout > 0:
      entries = self._wpas_client.Scan(request.timeout)
    else:
      entries = self._wpas_client.Scan()

    response = messages_pb2.Response()
    response.scan_networks.status = messages_pb2.SUCCESS
    for entry in entries:
      scan_result = response.scan_networks.results.add()
      scan_result.ssid = entry["ssid"]
      scan_result.secure = entry["secure"]
      scan_result.rssi = entry["rssi"]
    self._SendMessage(response)

  def _HandleConnectNetwork(self, request):
    if request.timeout > 0:
      success = self._wpas_client.ConnectNetwork(request.ssid, request.psk,
                                                 request.timeout)
    else:
      success = self._wpas_client.ConnectNetwork(request.ssid, request.psk)

    response = messages_pb2.Response()
    response.connect_network.status = messages_pb2.SUCCESS if success else messages_pb2.FAILURE
    self._SetWifiInfo(response.connect_network.wifi_info)
    self._SendMessage(response)

  def _SendMessage(self, message):
    if self._client_socket is None:
      return
    buf = message.SerializeToString()
    self._client_socket.send(struct.pack("!I", len(buf)))
    self._client_socket.send(buf)

  def _ReceiveBytes(self, num_bytes):
    received = bytearray(b"")
    while num_bytes > len(received):
      buf = self._client_socket.recv(num_bytes - len(received))
      received.extend(buf)
    return bytes(received)

  def _ReceiveRequest(self):
    buf = self._ReceiveBytes(4)
    num_bytes = struct.unpack("!I", buf)[0]
    buf = self._ReceiveBytes(num_bytes)
    request = messages_pb2.Request()
    request.ParseFromString(buf)
    return request

  def _SetWifiInfo(self, info):
    (wpa_state, info.ssid, info.ip, info.rssi) = self._wpas_client.GetState()
    if wpa_state == "INTERFACE_DISABLED":
      info.state = messages_pb2.WifiInfo.DISABLED
    elif wpa_state == "COMPLETED":
      info.state = messages_pb2.WifiInfo.CONNECTED
    else:
      info.state = messages_pb2.WifiInfo.DISCONNECTED

  class _NameThread(threading.Thread):
    """Thread monitoring device name changes."""

    def __init__(self, owner, file_name):
      threading.Thread.__init__(self)
      self._lock = threading.Lock()
      self.daemon = True
      self._closed = False
      self._owner = owner
      self._file_name = file_name
      self._device_name = self.ReadName()

    def Close(self):
      self.closed = True

    def run(self):
      while not self._closed:
        try:
          name = self.ReadName()
          with self._lock:
            changed = self._device_name != name
            self._device_name = name
          if changed:
            self._owner._UpdateDeviceName(name)
        except OSError:
          pass
        finally:
          time.sleep(1)

    def ReadName(self):
      try:
        with self._lock, open(self._file_name, "r") as name_file:
          return name_file.read().strip()
      except OSError:
        return None

    def WriteName(self, name):
      try:
        path = pathlib.Path(self._file_name)
        path.parent.mkdir(parents=True, exist_ok=True)
        with self._lock, open(str(path), "w") as name_file:
          name_file.write("%s\n" % name)
          self._device_name = name
        shutil.chown(str(path), user="pi", group="pi")
        shutil.chown(str(path.parent), user="pi", group="pi")
      except OSError:
        self._owner._logger.info("Write to %s failed", self._file_name)


def main():
  logger = logging.getLogger("logger")
  parser = argparse.ArgumentParser()
  parser.add_argument("--syslog", help="Log to syslog", action="store_true")
  parser.add_argument(
      "--debug", help="Enable debug logging", action="store_true")
  parser.add_argument(
      "--no_trigger", help="Disable triggers", action="store_true")
  parser.add_argument(
      "--timeout", "-t", type=int, dest="timeout", default="300")
  args = parser.parse_args()
  if args.syslog:
    handler = logging.handlers.SysLogHandler(address="/dev/log")
    format = "%s[%d]" % (sys.argv[0], os.getpid())
    formatter = logging.Formatter(format + ": %(message)s")
  else:
    handler = logging.StreamHandler(sys.stdout)
    formatter = logging.Formatter("%(asctime)s: %(message)s")

  handler.setFormatter(formatter)
  logger.addHandler(handler)
  logger.setLevel(logging.INFO)

  if args.debug:
    logger.setLevel(logging.DEBUG)
    logger.info("Debug logs enabled")

  sys.excepthook = _ExceptionHandler
  signal.signal(signal.SIGINT, _SignalHandler)
  signal.signal(signal.SIGTERM, _SignalHandler)

  enable_trigger = True
  if args.no_trigger:
    enable_trigger = False
  server = BtProvServer(enable_trigger)
  _closables.append(server)
  while server.Run(args.timeout):
    if not server.HasTrigger():
      break
  server.Close()


if __name__ == "__main__":
  main()
