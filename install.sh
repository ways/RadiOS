#!/bin/bash

# Install RadiOS on already installed volumio.

#dir=/volumio/RadiOS/

#cat "${dir}settings.ini" >> /boot/config/settings.ini
#crontab < "${dir}crontab.root"

sudo apt update
sudo apt-get install python-pip python-dev vim-nox screen
sudo pip install python-mpd2 RPi.GPIO

# Add favorits to /data/favourites/my-web-radio
cp my-web-radio /data/favourites/my-web-radio

