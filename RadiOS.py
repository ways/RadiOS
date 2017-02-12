#!/usr/bin/env python

# Copyright 2014-2017 Lars Falk-Petersen <dev@falkp.no>
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
#
# See install.sh for requirements
#

import time, syslog, io, sys, os, urllib2, socket, mpd, json, RPi.GPIO as GPIO
from wireless import Wireless

# Init GPIO
GPIO.setwarnings(False)
GPIO.setmode(GPIO.BCM)

# Init wireless
wireless = Wireless()

favoritesFile = '/data/favourites/my-web-radio'
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
startTime = time.time()

                     # User configurable
useVoice  = False    # Announce channels
verbose   = False    # Development variables
speakTime = False


def FindSSID (client):
  current = wireless.current()

  if current:
    return current
  else:
    return 'kabel' # 'wired'


def ParseConfig ():
  section = 'Channels'
  channelnames = ['noop']
  channelurls = ['noop']
  config = None

  try:

    # Read config file
    with open(favoritesFile) as data_file:    
      config = json.load(data_file)

    if verbose:
      print "Read config file:"
      from pprint import pprint
      pprint(config)

    # Parse favorites into channels

    for channel in config:
      channelnames.append (channel['name'])
      channelurls.append (channel['uri'])

  except IOError:
    print "Error reading config file " + favoritesFile
    WriteLog ("Error reading config file " + favoritesFile, True)
    sys.exit (1)

  if verbose:
    print 'channelnames', channelnames
    print 'channelurls', channelurls
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
  except mpd.ConnectionError():
    WriteLog ("Error connecting to MPD", True)
    return False
  
  return True


def DisconnectMPD (c):
  try:
    c.close ()
  except mpd.ConnectionError():
    pass


def StopMPD (c):
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
  except mpd.ConnectionError():
    WriteLog('MPD error setting volume.')
    return False
  return True


def PlayMPD (c, volume, url):
  try:
    WriteLog ("Playing " + url + " at volume " + str (volume) + ".")
    c.clear ()
    c.add (url)
    SetVolumeMPD (c, 0)
    c.play ()

    SetVolumeMPD (c, volume)

    mpdstatus = c.status()
  except mpd.CommandError, e:
    WriteLog ("PlayMPD: Error commanding mpd: " + str(e))
    return False
  except mpd.ConnectionError, e:
    WriteLog ("PlayMPD: Error connecting to MPD:" + str (e), True)
    return False

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
    Speak (channelNames[nowPlaying], client, nowVolume)
  nowTimestamp = time.time ()
  return PlayMPD (client, nowVolume, channelUrls[nowPlaying])


def Speak (msg, client, volume=10):
  _volume = volume + 5
  WriteLog ('Saying . o O (' + msg + ')')
  SetVolumeMPD (client, _volume)
  StopMPD (client)
  os.system ('/usr/bin/espeak -v no -g 10 -p 1 -a ' + str (_volume) + ' -s 200 --stdout "' \
    + msg + '" | /usr/bin/aplay -D plughw:5,0 --quiet')

def PopulateTables ():   # Set up mapping from IO to function
# BCN/GPIO number | function
# Function: volumes are positive, channels negative. 0 is noop.

  ioList = [
      0,  #0 Doesn't exist?
      0,  #1 Doesn't exist on Raspi rev2 and later
      0,  #2 This pin gives false positives
      0,  #3 This pin gives false positives
     -1,  #4
      0,  #5
      0,  #6
      0,  #7
      3,  #8
     -6,  #9
     -5,  #10
     -7,  #11
      0,  #12
      0,  #13
     40,  #14
     30,  #15
      0,  #16
     -2,  #17
     20,  #18
      0,  #19
      0,  #20
      0,  #21
     -4,  #22
     15,  #23
      7,  #24
      5,  #25
      0,  #26 This pin seems to not work?
     -3   #27
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

  elif 666 == int (ioVolume[0]): 
    WriteLog ("Placeholder")
    StopMPD (client)

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


def checkFavorites(c): # Check if favorites file has changed. If so complain and exit.
  stamp = os.stat(favoritesFile).st_mtime
  if stamp > startTime:
    StopMPD (c)
    WriteLog ('Favorites changed. I was started at ' + startTime + ' and ' + favoritesFile + ' changed at ' + stamp)
    Speak ('Favorites changed, restarting.')
    sys.exit(0)

# Main

channelNames, channelUrls = ParseConfig ()
ioList = PopulateTables ()
ConnectMPD (client)
GPIO.setmode (GPIO.BCM) #Use GPIO numbers

try:
  ssid=FindSSID (client)

  if not TestConnection ():
    Speak ("Kan ikke koble til nettverket.", client)
  else:
    StopMPD (client)
    if useVoice:
      Speak ("Nettverk " + ssid + ".", client)

  while True:
    ioVolume, ioChannel = ScanIO (ioList)
    if not Compare (client):
      PlayStream (ioVolume, ioChannel, client)

    checkFavorites(client)

    time.sleep (0.2)

except KeyboardInterrupt:
  print "Shutting down cleanly ... (Ctrl + C)"
except socket.error:
  print "socket.error MPD stopped?"
  sys.exit(1)
except mpd.ConnectionError:
  print "mpd.ConnectionError: MPD stopped?"
  sys.exit(1)

finally:
  #DisconnectMPD (client)
  GPIO.cleanup()

