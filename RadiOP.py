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
# Requires apt-get install python-mpd python-rpi.gpio
# Requires pip install python-mpd2 ( http://pythonhosted.org/python-mpd2/topics/commands.html )
# Can use espeak mpd
#
# Pseudo code:
# * load user configs
# * feel input
#  * no input -> stop music
#  * check if we're playing what's selected
#   * check if volume's right
#    * if no -> set volume
#   * if no -> play selected
#   * if no network -> warn user
#   * if no channels set -> warn user
#
# Our physical input looks something like this:
#
# channel | volume
# 1       | 50
# 2       | 40
# 3       | 30
# 4       | 20
# 5       | 10
# 6       | 5

import time, syslog, ConfigParser, io, sys, os, mpd, urllib2
import RPi.GPIO as GPIO

mpdhost = 'localhost'
client = mpd.MPDClient () # Connection to mpd

ioList = None        # Map GPIO to function
channelNames = None  # User channel titles
channelUrls = None   # User channel urls
nowPlaying = False   # Status variables
nowVolume = 0
nowTimestamp = 0
prevPlaying = False
prevVolume = 0
prevTimestamp = 0
ioChannel = None     # Current channels selected
ioVolume = None      # Current volumes selected
speakTime = False
configFile = "/boot/config/config.txt"

                     # User configurable
useVoice = True      # Announce channels
volVoice = 3
verbose = True       # Development variables


def ParseConfig ():
  section = 'Channels'
  channelnames = ['noop']
  channelurls = ['noop']

  try:
    config = ConfigParser.RawConfigParser (allow_no_value=True)
    config.read (configFile)

    for i in range (1, 9):
      channelnames.append (config.get (section, 'channel' \
        + str (i) + '_name'))
      channelurls.append (config.get (section, 'channel' + \
        str (i) + '_url'))
      if verbose:
        print "Added "+ str(i) + " - " \
          + str(config.get (section, 'channel' + str (i) + '_name'))

  except ConfigParser.NoOptionError, e:
    WriteLog ("Error in config file " + configFile + ". Error: " \
      + str (e), True)

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
  try:
    c.connect (mpdhost, 6600)
    #c.crossfade (5)
  except mpd.ConnectionError():
    WriteLog ("Error connecting to MPD", True)
    return False
  
  #WriteLog ("Connected to MPD version " + c.mpd_version)
  return True


def DisconnectMPD (c):
  try:
    c.close ()
  except mpd.ConnectionError():
    pass


def StopMPD (c):
#  step = -10
#  volume = nowVolume
#  for v in range (nowVolume, 0, step):
#    SetVolumeMPD (c, v)
#    time.sleep (.1)

  WriteLog ("Stopping MPD")
  try:
    c.clear ()
    return True
  except mpd.ConnectionError():
    WriteLog ("MPD error")
    return False


def MuteMPD (c):
  WriteLog ("Muting MPD.")
  SetVolumeMPD (c, volVoice)


def SetVolumeMPD (c, vol):
  WriteLog ("Setting volume to " + str (vol) + ".")
  nowVolume = vol

  try:
    c.setvol (int (vol))
    #os.system ('amixer cget numid=5 ')
    #os.system ('amixer cset numid=5 --quiet -- ' + str(vol) + '%')
  except mpd.ConnectionError():
    WriteLog('MPD error setting volume.')
    return False
  return True


def PlayMPD (c, volume, url):
  start = 0
  step = 5

  try:
    WriteLog ("Playing " + url + " at volume " + str (volume) + ".")
    c.add (url)
    SetVolumeMPD (c, 0)
    c.play ()

    for v in range (start, volume + step, step):
      SetVolumeMPD (c, v)
      time.sleep (.05)

    time.sleep (5)
    mpdstatus = c.status()
  except mpd.CommandError, e:
    WriteLog ("PlayMPD: Error commanding mpd: " + str(e))
    return False
  except mpd.ConnectionError, e:
    WriteLog ("PlayMPD: Error connecting to MPD:" + str (e), True)
    return False
  
  if 'play' != mpdstatus['state']:
    Speak ('Unable to play channel ' + str (nowPlaying) + '?', c) 
    return False

  return True


def PlayStream (ioVolume, ioChannel, client):
  global nowPlaying, nowVolume, nowTimestamp

  nowPlaying = int (ioChannel[0])
  nowVolume = int (ioVolume[0])

  #StopMPD (client)

  if len (channelNames) <= nowPlaying:   # We don't have that many channels
    Speak ("Channel " + str(nowPlaying) + " is not configured.", client)
    return False
    
  WriteLog ("Will play channel " + str (nowPlaying) + \
    " (named " + channelNames[nowPlaying] + \
    ") at volume " + str (nowVolume) + "." )

  if useVoice:
    Speak ("Playing " + channelNames[nowPlaying], client, 2)
  nowTimestamp = time.time ()
  return PlayMPD (client, nowVolume, channelUrls[nowPlaying])


def Speak (msg, client, volume=5):
  WriteLog ('Saying . o O (' + msg + ')')
  SetVolumeMPD (client, volume)
  os.system ('espeak -a ' + str (volume) + ' -s 130 --stdout "' + msg + '" | aplay --quiet')

def PopulateTables ():   # Set up mapping from IO to function
# BCN/GPIO number | function
# Function: volumes are positive, channels negative. 0 is noop.
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
      0,  #0
      0,  #1
      0,  #2 100, This pin gives false positives
      0,  #3 90, This pin gives false positives
    100,  #4
      0,  #5
      0,  #6
      0,  #7 95
     -7,  #8
     20,  #9
     -5,  #10
     -1,  #11
      0,  #12
      0,  #13
     -2,  #14
     -3,  #15
      0,  #16
     90,  #17
     -4,  #18
      0,  #19
      0,  #20
      0,
     60,  #22
     -5,  #23
     -6,  #24
     -1,  #25
      0,
     80   #27
  ]

  if verbose:
    print ioList

  return ioList


def Compare (client):      # True if we do not need to start something
  global nowPlaying, speakTime, nowTimestamp

  print time.time ()
  print nowTimestamp
  print nowVolume
  print ioVolume[0]

  # Stop if unplugged for more that a few seconds
  if 0 == int (ioChannel[0]) and nowPlaying:
    if 20 > ( float (time.time ()) - float (nowTimestamp) ):
      WriteLog ("Stopping MPD due to nowPlaying " + \
        str (nowPlaying) + " or ioChannel " + str (ioChannel[0]) )
      nowPlaying = False
      nowTimestamp = 0
      StopMPD (client)
    else:
      WriteLog ("Muting due to unplugged cable.")
      MuteMPD (client)

    return True

  # Volume ok?
  elif nowPlaying and nowVolume != ioVolume[0]:
    WriteLog("Restoring volume")
    SetVolumeMPD (client, int (ioVolume[0]))

  # Channel ok?
  #elif 0 == int (ioChannel[0]): #No channel set, nothing playing.
  #  if verbose:
  #    WriteLog("No channel set: ", str (ioChannel[0]))
  #  return True

  elif -40 == int (ioChannel[0]): #Hourly speakTime
    if not speakTime:
      WriteLog ("Activating speakTime")
      Speak ("Time is now " + time.strftime("%H:%M"), client, 80)

      speakTime = True
    return True

  else: # Else check if we're playing correct, and return status
    return ( nowPlaying == int (ioChannel[0]) \
             and nowVolume == int (ioVolume[0]) )


def ScanIO (ioList):
  ioVol = list ()
  ioChan = list ()

  # Set up for channel
  for pin, func in enumerate (ioList):
    if 0 == func: #noop pins
      continue

    if 0 > func:                         # Prepare channels for input
      GPIO.setup (pin, GPIO.IN, pull_up_down=GPIO.PUD_DOWN)
    else:                                # Prepare volumes for output
      GPIO.setup (pin, GPIO.OUT, initial=GPIO.HIGH)

  # Look for channel
  for pin, func in enumerate (ioList):   # Look for HIGHs
    if 0 == func: # noop pins
      continue

    if 0 > func and GPIO.input(pin):
      ioChan.append ( abs (func) )
      if verbose:
        print "Found high pin", pin, "func", func, "while looking for channels"

  if 0 == len (ioChan):
    ioChan.append (0)
    if verbose:
      print "No channel set."

  GPIO.cleanup()

  # Now we turn it around
  # Set up for volume
  for pin, func in enumerate (ioList):   
    if 0 == func: # noop pins
      continue

    if 0 < func:                        # Prepare volumes for input
      #print "setting pin", pin, "func", func, "as in"
      GPIO.setup (pin, GPIO.IN, pull_up_down=GPIO.PUD_DOWN)
    else:                                # Prepare channels for output
      #print "setting pin", pin, "func", func, "as out"
      GPIO.setup (pin, GPIO.OUT, initial=GPIO.HIGH)

  # Look for volume
  for pin, func in enumerate (ioList): # Look for HIGHs
    if 0 == func: #noop pins
      continue

    if 0 < func and GPIO.input(pin):
      ioVol.append (func)
      if verbose:
        print "Found high pin", pin, "func", func, "while looking for volumes"

  if 0 == len (ioVol):
    ioVol.append (0)
    if verbose:
      print "No volume set"

  GPIO.cleanup()

  # Check for same-row connections.
  # TODO: Currently disabled.
  #if 0 == ioVol[0] and -1 == ioChan[0]:
  #  pinout = 4
  #  pinin = 7

  #  GPIO.setup (pinin, GPIO.IN, pull_up_down=GPIO.PUD_DOWN)
  #  GPIO.setup (pinout, GPIO.OUT, initial=GPIO.HIGH)

  #  if GPIO.input(pinin):
  #    ioChan[0] = -40

  #  GPIO.cleanup()

  return (ioVol, ioChan)


def internet_on():
  try:
    response = urllib2.urlopen ('http://nrk.no/', timeout=2)
    return True
  except urllib2.URLError as err: pass
  return False


# Main
channelNames, channelUrls = ParseConfig ()
ioList = PopulateTables ()
ConnectMPD (client)
GPIO.setmode (GPIO.BCM) #Use GPIO numbers

try:
  if not internet_on ():
    Speak ("Uh oh. No network.", client)
  else:
    Speak ("Hello.", client, volVoice)

  while True:
    ioVolume, ioChannel = ScanIO (ioList)
    if not Compare (client):
      PlayStream (ioVolume, ioChannel, client)

    time.sleep (1)

except KeyboardInterrupt:
  print "Shutting down cleanly ... (Ctrl + C)"

finally:
  DisconnectMPD (client)
  GPIO.cleanup()
