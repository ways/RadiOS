#!/usr/bin/env python

# Copyright 2014 Lars Falk-Petersen
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program. If not, see <http://www.gnu.org/licenses/>.


# Main part of RadiOP
# Requires apt-get install mpd python-mpd espeak
#
# Pseudo code:
# * load user configs
# * feel input
#  * no input -> stop
#  * check if we're playing what's selected
#   * if no -> play selected
#  * check if volume's right
#   * if no -> set volume
#
# Our physical input looks like this:
#
# channel | volume
# 1       | 100
# 2       | 90
# 3       | 80
# 4       | 70
# 5       | 60
# 6       | 50

import time, syslog, mpd, ConfigParser, io, sys, os
import RPi.GPIO as GPIO

client = mpd.MPDClient () # Connection to mpd
ioList = None        # Map GPIO to function
channelNames = None  # User channel titles
channelUrls = None   # User channel urls
nowPlaying = False   # Status variables
nowVolume = 0
nowTimestamp = 1
prevPlaying = False
prevVolume = 0
prevTimestamp = 0
ioChannel = None     # Current channels selected
ioVolume = None      # Current volumes selected
useVoice = True     # Announce channels
configFile = "/boot/config/config.txt"
verbose = True       # Development variables


def ParseConfig ():
  section = 'Channels'
  channelnames = list ()
  channelurls = list ()

  try:
    config = ConfigParser.RawConfigParser (allow_no_value=True)
    config.read (configFile)

    for i in range (1, 9):
      channelnames.append (config.get (section, 'channel' + str (i) + '_name'))
      channelurls.append (config.get (section, 'channel' + str (i) + '_url'))

  except ConfigParser.NoOptionError, e:
    WriteLog ("Error in config file " + configFile + ". Error: " + str (e), True)

  except ConfigParser.Error:
    print "Error reading config file " + configFile
    WriteLog ("Error reading config file " + configFile, True)
    sys.exit (1)

  if verbose:
    print channelnames
    print channelurls
  else:
    WriteLog ( "Read channels from config: " + str (channelnames))

  return channelnames, channelurls

def WriteLog (msg, error = False):
  severity = syslog.LOG_INFO
  if error:
    severity = syslog.LOG_ERR
  syslog.syslog (severity, msg)


def ConnectMPD (c):
  c.timeout = 10
  c.idletimeout = None
  try:
    c.connect ("localhost", 6600)
  except mpd.ConnectionError():
    WriteLog ("Error connecting to MPD", True)
    return False

  WriteLog ("Connected to MPD version " + c.mpd_version)
  Speak ("I am ready")
  return True

def StopMPD (c):
  WriteLog("Stopping MPD")
  c.clear ()


def MuteMPD (c):
  WriteLog ("Muting MPD.")
  SetVolumeMPD (c, 0)


def SetVolumeMPD (c, vol):
  WriteLog ("Setting volume to " + str (vol) + ".")
  c.setvol (int (vol))


def PlayMPD (c, volume, url):
  start = 20
  step = 5

  try:
    WriteLog ("Playing " + url + " at volume " + str (volume) + ".")
    c.add (url)
    SetVolumeMPD (c, 0)
    c.play ()

    for v in range (start, volume + step, step):
      SetVolumeMPD (c, v)
      time.sleep (.1)

  except mpd.CommandError, e:
    WriteLog ("PlayMPD: Error commanding mpd: " + str(e))
    return False
  except mpd.ConnectionError, e:
    WriteLog ("PlayMPD: Error connecting to MPD:" + str (e), True)
    return False

  return True


def PlayStream (ioVolume, ioChannel):
  global nowPlaying, nowVolume, nowTimestamp, prevPlaying, prevVolume, prevTimestamp

  prevPlaying = nowPlaying
  prevVolume = nowVolume
  prevTimestamp = nowTimestamp

  nowPlaying = int (ioChannel[0])
  nowVolume = int (ioVolume[0])
  nowTimestamp = time.time ()

  WriteLog ("Will play channel " + str (nowPlaying) + \
    " (named " + channelNames[nowPlaying] + \
    ") at volume " + str (nowVolume) + "."
    )

  StopMPD (client)
  Speak ("Playing " + channelNames[nowPlaying])
  PlayMPD (client, nowVolume, channelUrls[nowPlaying])


def Speak (msg):
  if useVoice:
    WriteLog ('Saying . o O (' + msg + ')')
    os.system("espeak --stdout '" + msg + "' -a 300 -s 130 | aplay")


def PopulateTables ():   # Set up mapping from IO to function
# BCN/GPIO number | function
# 2  | volume 100
# 3  | volume 90
# 4  | volume 80
# 17 | volume 70
# 27 | volume 60
# 22 | volume 50
# 10 | volume 40
# 9  | volume 30

# 11 | channel 1
# 14 | channel 2
# 15 | channel 3
# 18 | channel 4
# 23 | channel 5
# 24 | channel 6
# 25 | channel 7
# 08 | channel 8
# 07 | channel 9

  ioList = [
    -1,  #0
    -1,  #1
    -1, #2 100, This pin gives false positives
    -1,  #3 90, This pin gives false positives
    100,  #4
    -1,  #5
    -1,  #6
    40,  #7
    8,   #8
    50,  #9
    70, #10
    1,  #11
    -1, #12
    -1, #13
    2,  #14
    3,  #15
    -1, #16
    90, #17
    4,  #18
    -1, #19
    -1, #20
    -1,
    60, #22
    5,  #23
    6,  #24
    7,  #25
    -1,
    80  #27
  ]

  if verbose:
    print ioList

  return ioList


def Compare ():      # True if we do not need to start something
  global nowPlaying

  if -1 == int (ioChannel[0]) \
    and nowPlaying:                    # Stop if unplugged for more that a few seconds
    WriteLog ("Stopping MPD due to nowPlaying " + \
      str (nowPlaying) + " or ioChannel " + str (ioChannel[0]) )

    nowPlaying = False
    StopMPD (client)
    return True

  elif -1 == int (ioChannel[0]): #No channel set, nothing playing.
    return True

  # Else check if we're playing correct, and return status
  return ( nowPlaying == int (ioChannel[0]) and nowVolume == int (ioVolume[0]) )


def ScanIO (ioList):
  ioVol = list ()
  ioChan = list ()

  for pin, func in enumerate (ioList):
    if -1 == func: #noop
      continue

    if func < 10:                         # Prepare channels for input
      GPIO.setup (pin, GPIO.IN, pull_up_down=GPIO.PUD_DOWN)
    else:                                # Prepare volumes for output
      GPIO.setup (pin, GPIO.OUT, initial=GPIO.HIGH)

  for pin, func in enumerate (ioList):   # Look for HIGHs
    if -1 == func: # noop 
      continue

    if func < 10 and GPIO.input(pin):
      ioChan.append (func)
      #if verbose:
      #  print "Found high pin", pin, "func", func, "while looking for channels"

  if 0 == len (ioChan):
    ioChan.append (-1)
    if verbose:
      print "No channel set"

  GPIO.cleanup()

  # Now we turn it around
  for pin, func in enumerate (ioList):   
    if -1 == func: # noop
      continue

    if func > 10:                        # Prepare volumes for input
      #print "setting pin", pin, "func", func, "as in"
      GPIO.setup (pin, GPIO.IN, pull_up_down=GPIO.PUD_DOWN)
    else:                                # Prepare channels for output
      #print "setting pin", pin, "func", func, "as out"
      GPIO.setup (pin, GPIO.OUT, initial=GPIO.HIGH)

  for pin, func in enumerate (ioList): # Look for HIGHs
    if -1 == func: #noop 
      continue

    if func > 10 and GPIO.input(pin):
      ioVol.append (func)
      #if verbose:
      #  print "Found high pin", pin, "func", func, "while looking for volumes"

  if 0 == len (ioVol):
    ioVol.append (0)
    print "No volume set"

  GPIO.cleanup()
  return (ioVol, ioChan)


# Main
channelNames, channelUrls = ParseConfig ()
ConnectMPD (client)
ioList = PopulateTables ()

#GPIO.setmode (GPIO.BOARD)
GPIO.setmode (GPIO.BCM) #Use GPIO numbers
GPIO.setwarnings (False)

try:
  while True:
    ioVolume, ioChannel = ScanIO (ioList)
    if not Compare ():
      PlayStream (ioVolume, ioChannel)

    time.sleep (5)

except KeyboardInterrupt:
  print "Shutting down cleanly ... (Ctrl + C)"

finally:  
    GPIO.cleanup()
