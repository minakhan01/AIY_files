#!/bin/bash

UUID=0ddfb752-31be-4291-92da-73360695695e
FOUND_UUID=XXXXXXXX-XXXX-XXXX-XXXX-XXXXXXXXXXXX
REBOOT=false

if [ -f /proc/device-tree/hat/uuid ]; then
    FOUND_UUID=$(cat /proc/device-tree/hat/uuid | xargs -0)
else
    # No HAT found. However, this doesn't mean one isn't there: older Voice HATs
    # have unprogrammed EEPROMs which means they can't be recognized, so don't
    # adjust the config in this case.
    exit 0
fi

if [[ "$UUID" == "$FOUND_UUID" ]]; then
    if grep -q "^# dtoverlay=googlevoicehat-soundcard" /boot/config.txt; then
        sed -i -e "s/^# dtoverlay=googlevoicehat-soundcard/dtoverlay=googlevoicehat-soundcard/" /boot/config.txt
        REBOOT=true
    elif ! grep -q "^dtoverlay=googlevoicehat-soundcard" /boot/config.txt; then
        echo "dtoverlay=googlevoicehat-soundcard" >> /boot/config.txt
        REBOOT=true
    fi
else
    if grep -q "^dtoverlay=googlevoicehat-soundcard" /boot/config.txt; then
        sed -i -e "s/^dtoverlay=googlevoicehat-soundcard/# \0/" /boot/config.txt
        REBOOT=true
    fi
fi

if [[ $REBOOT == true ]]; then
    reboot
fi
