#!/usr/bin/env python

# Copyright 2014-2015 Lars Falk-Petersen
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
# Requires apt-get install python-rpi.gpio
# Requires pip install python-mpd2 ( http://pythonhosted.org/python-mpd2/topics/commands.html )
# Can use espeak
# For development git-core rsync emacs23-nox
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

import time, syslog, ConfigParser, io, sys, os, mpd, urllib2, socket
import RPi.GPIO as GPIO

GPIO.setwarnings(False)
GPIO.setmode(GPIO.BCM)

configFile = "/boot/config/radios.ini"
mpdhost = 'localhost'
inethost = 'nrk.no' # For testing internet
client = mpd.MPDClient () # Connection to mpd

ioList = None        # Map GPIO to function
channelNames = None  # User channel titles
channelUrls = None   # User channel urls
nowPlaying = False   # Status variables
nowVolume = 0
nowTimestamp = 0
prevPlaying = False
prevVolume = 0
muted = False
ioChannel = None     # Current channels selected
ioVolume = None      # Current volumes selected

                     # User configurable
useVoice  = True     # Announce channels
verbose   = True     # Development variables
speakTime = False


def FindSSID (client):
  config=''
  #grep ssid /etc/wpa.conf |cut -d'"' -f2
  with open ('/etc/wpa.conf', 'r') as myfile:
    config=myfile.read()

  return config.split('"')[1]


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
  if verbose:
    print severity, msg
  syslog.syslog (severity, msg)


def ConnectMPD (c):
  try:
    c.connect (mpdhost, 6600)
    #c.crossfade (5) #not implemented in mopidy
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
  global muted, prevVolume

  WriteLog ("Muting MPD.")
  prevVolume = nowVolume
  muted = True
  #c.pause (1)
  SetVolumeMPD (c, 0)


def SetVolumeMPD (c, vol):
  WriteLog ("Setting volume to " + str (vol) + ".")
  nowVolume = vol

  try:
    c.setvol (vol)
    #os.system ('amixer cget numid=5 ')
    #os.system ('amixer cset numid=5 --quiet -- ' + str(vol) + '%')
  except mpd.ConnectionError():
    WriteLog('MPD error setting volume.')
    return False
  return True


def PlayMPD (c, volume, url):
#  start = 1
#  step = 1
#  if 10 < volume:
#    step = 10

  try:
    WriteLog ("Playing " + url + " at volume " + str (volume) + ".")
    c.clear ()
    c.add (url)
    SetVolumeMPD (c, 0)
    c.play ()

#    for v in range (start, volume + step, step):
#      SetVolumeMPD (c, v)
#      time.sleep (.05)
    SetVolumeMPD (c, volume)

#    time.sleep (5)
    mpdstatus = c.status()
  except mpd.CommandError, e:
    WriteLog ("PlayMPD: Error commanding mpd: " + str(e))
    return False
  except mpd.ConnectionError, e:
    WriteLog ("PlayMPD: Error connecting to MPD:" + str (e), True)
    return False
  
#  if 'play' != mpdstatus['state']:
#    Speak ('Unable to play channel ' + str (nowPlaying) + '?', c) 
#    return False

  return True


def PlayStream (ioVolume, ioChannel, client):
  global nowPlaying, nowVolume, nowTimestamp

  nowPlaying = int (ioChannel[0])
  nowVolume = int (ioVolume[0])

  StopMPD (client)

  if 0 == nowPlaying:
    return False
  elif len (channelNames) <= nowPlaying:  # We don't have that many channels
    Speak ("Kanal " + str(nowPlaying) + " er ikke konfigurert.", client)
    return False
    
  WriteLog ("Will play channel " + str (nowPlaying) + \
    " (named " + channelNames[nowPlaying] + \
    ") at volume " + str (nowVolume) + "." )

  if useVoice:
    Speak ("Spiller " + channelNames[nowPlaying], client)
  nowTimestamp = time.time ()
  return PlayMPD (client, nowVolume, channelUrls[nowPlaying])


def Speak (msg, client, volume=4):
  WriteLog ('Saying . o O (' + msg + ')')
  SetVolumeMPD (client, volume)
  os.system ('/usr/bin/espeak -v no -g 10 -p 1 -a ' + str (volume) + ' -s 170 --stdout "' \
    + msg + '" | /usr/bin/aplay -D plughw:1,0 --quiet')

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
      0,  #0 Doesn't exist
      0,  #1 Doesn't exist on Raspi rev2 and later
      0,  #2 This pin gives false positives
      0,  #3 This pin gives false positives
     40,  #4
      0,  #5
      0,  #6
      0,  #7 95
     -1,  #8
    666,  #9
     10,  #10
     30,  #11
      0,  #12
      0,  #13
     -7,  #14
     -6,  #15
      0,  #16
      1,  #17
     -5,  #18
      0,  #19
      0,  #20
      0,
      5,  #22
     -4,  #23
     -3,  #24
     -2,  #25
      0,  #26 This pin seems to not work?
      2   #27
  ]

  if verbose:
    print ioList

  return ioList


def Compare (client):      # True if we do not need to start something
  global nowPlaying, speakTime, nowTimestamp

  client.ping ()

  # If unplugged, but playing
  if 0 == ioChannel[0] and nowPlaying:
    WriteLog ("Stopping MPD due to nowPlaying " + \
      str (nowPlaying) + " or ioChannel " + str (ioChannel[0]) )
    nowPlaying = False
    StopMPD (client)
    return True

  #elif -40 == int (ioChannel[0]): #Hourly speakTime
  #  if not speakTime:
  #    WriteLog ("Activating speakTime")
  #    Speak ("Time is now " + time.strftime("%H:%M"), client, 80)

  #    speakTime = True
  #  return True

  elif 666 == int (ioVolume[0]): 
    WriteLog ("Placeholder")
    StopMPD (client)

    #Speak ("I'm at I P " + GetIP (), client, 5)
    
    #Speak ("Good bye.", client, 5)
    #Speak ("Good bye.", client, 4)
    #Speak ("Good bye.", client, 3)
    #os.system("sudo halt")
    #Speak ("Ouch. No no no.", client, 2)
    #time.sleep (10)
    return True

  else: # Else check if we're playing correct, and return status
    return ( nowPlaying == int (ioChannel[0]) \
             and nowVolume == int (ioVolume[0]) )


def ScanIO (ioList):
#  if verbose:
#    print "scanio"

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

  # Channel sanity checks
  if 0 == len (ioChan):
    ioChan.append (0)
#    if verbose:
#      print "No channel set."

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

  # Volume sanity checks
  if 0 == len (ioVol):
    ioVol.append (0)
    if verbose:
      print "No volume set"

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


def TestConnection ():
  try:
    response = urllib2.urlopen ('http://' + inethost, timeout=2)
    return True
  except urllib2.URLError as err: pass
  return False


def GetIP ():
  ip = 'unknown'
  s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
  s.connect ( (inethost,80) )
  ip = s.getsockname()[0]
  s.close()
  return ip


# Main
channelNames, channelUrls = ParseConfig ()
ioList = PopulateTables ()
ConnectMPD (client)
GPIO.setmode (GPIO.BCM) #Use GPIO numbers

try:
  ssid=FindSSID (client)

  if not TestConnection ():
    Speak ("Kan ikke koble til nettverket " + ssid + ".", client)
  else:
    StopMPD (client)
    Speak ("Koblet til nettverket " + ssid + ".", client)

  while True:
    ioVolume, ioChannel = ScanIO (ioList)
    if not Compare (client):
      PlayStream (ioVolume, ioChannel, client)

    time.sleep (0.2)

except KeyboardInterrupt:
  print "Shutting down cleanly ... (Ctrl + C)"

finally:
  #DisconnectMPD (client)
  GPIO.cleanup()
