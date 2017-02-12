#!/bin/bash

# Install RadiOS on already installed volumio.

# RadiOS dir
dir=/home/volumio/RadiOS/

cd ${dir} || { echo "Error, check dir"; exit 1; }

# Install packages
sudo apt update
sudo apt-get install -f python-pip python-dev vim-nox screen espeak
sudo pip install python-mpd2 RPi.GPIO wireless

# Set up access to gpio for user (see also root crontab)
sudo adduser volumio gpio

# Add favorits to /data/favourites/my-web-radio
cp my-web-radio /data/favourites/my-web-radio

# Enable on startup
sudo cp systemd/radios.service /etc/systemd/system/
sudo systemctl enable radios.service

# Disable wireless powersaving
echo "wireless-power off" >> /etc/network/interfaces

echo "Done. Please reboot.

Suggested settings in volumio:

* Set output device to your usb soundcard.
* audio buffer: small, i.e. 2 MB
* check My Web Radios and replace with your favorites
"
