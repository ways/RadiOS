#!/usr/bin/env python

# Main part of RadiOP
#
# Requires python-mpd
#
# Pseudo code:
# * stop any music playing
#
# * feel input
#  * check if we're playing that
#  * if no: stop, play that
#
# Our input looks like this:
#
# channel | volume
# 1       | 100
# 2       | 90
# 3       | 80
# 4       | 70
# 5       | 60
# 6       | 50
# 7       | 40
# 8       | 30

from mpd import MPDClient
from time import sleep

client = MPDClient() 
ioMapVolume = None
ioMapChannels = None
verbose = 3
test = True


def ConnectMPD (c):
  c.timeout = 10
  c.idletimeout = None
  c.connect("localhost", 6600)
  if verbose:
    print(c.mpd_version) 


def StopMPD (c):
  if verbose:
    print "Stopping mpd."
  c.setvol(0)
  c.clear()


def PopulateTables (vol, chan):   # Set up mapping from IO to function
  # gpio | function
  # 8    | volume 100
  # 9    | volume 90
  # 7    | volume 80
  # 0    | volume 70
  # 2    | volume 60
  # 3    | volume 50
  # 12   | volume 40
  # 13	 | volume 30
  # 14   | mute / off

  # 15   | channel 1
  # 16   | channel 2
  # 1    | channel 3
  # 4    | channel 4
  # 5    | channel 5
  # 6    | channel 6
  # 10   | channel 7
  # 11   | channel 8

  vol = dict(
    8: "100",
    9: "90"
    )

  chan = dict(
    15: "http://vprbbc.streamguys.net:8000/vprbbc24.mp3",
    16: "NrkP1"
  )

  if verbose:
    print str( vol )
    print str( chan )


def Play (ioVolume, ioChannel):   # Start playing based on IO table
  PlayMPD (vol, chan)
  if verbose:
    print str( t )


def Compare (vol, chan):   # Check if we're playing what we're supposed to
  now = None   # What we're playing now

  if verbose:
    print "No need to change"
    return True


# Main

ConnectMPD (client)
StopMPD (client)

PopulateTables (ioMapVolume, ioMapChannels)

while True:
  if not Compare ( ScanIO (ioMapVolume, ioMapChannels)):
    Play(ioMapVolume, ioMapChannels)

  sleep 2
