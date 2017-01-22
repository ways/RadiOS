#!/bin/bash

# Install RadiOS on already installed volumio.

# RadiOS dir
dir=/home/volumio/RadiOS/

cd ${dir} || { echo "Error, check dir"; exit 1; }

# Install crontab
sudo crontab < "${dir}crontab.root"

# Install packages
sudo apt update
sudo apt-get install python-pip python-dev vim-nox screen
sudo pip install python-mpd2 RPi.GPIO

# Set up access to gpio for user (see also root crontab)
sudo adduser volumio gpio

# Add favorits to /data/favourites/my-web-radio
cp my-web-radio /data/favourites/my-web-radio

