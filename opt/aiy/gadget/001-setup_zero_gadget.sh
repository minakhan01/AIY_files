#!/bin/bash


SCRIPT=$(readlink -f $0)
SCRIPTPATH=`dirname $SCRIPT`

echo "Install getty-gadget"
cp -f /lib/systemd/system/serial-getty@.service /usr/lib/systemd/system/getty-gadget@.service
sed -i \
  -e 's/ExecStart=-\/sbin\/agetty/\0 -w/g' \
  /usr/lib/systemd/system/getty-gadget@.service

if grep -q 'dtoverlay=dwc2' /boot/config.txt; then
  echo 'DWC is already enabled, skip.'
else
  echo 'Enable DWC'
  echo 'dtoverlay=dwc2' >> /boot/config.txt
fi

echo "Configure static IP Address"
cat $SCRIPTPATH/googadget-dhcpcd.conf >> /etc/dhcpcd.conf

echo "Enable console to ACM interface"
systemctl enable getty-gadget@ttyGS0.service
