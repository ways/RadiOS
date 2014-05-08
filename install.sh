#!/bin/bash

# Install RadiOS on already installed musicbox.

cat /root/RadiOS/settings.ini >> /boot/config/settings.ini

apt-get install python-rpi.gpio espeak
pip install python-mpd2