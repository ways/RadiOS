#!/bin/bash

# Install RadiOS on already installed musicbox.
dir=/root/RadiOS/

cat "${dir}settings.ini" >> /boot/config/settings.ini
crontab < "${dir}crontab.root"

apt-get install python-rpi.gpio espeak
pip install python-mpd2
