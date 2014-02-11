#!/usr/bin/env python

# Main part of RadiOP
#
# Requires python-mpd
#
# Pseudo code:
# * stop any music playing
#
# * feel input
#  * muted for > 30 sec -> stop
#  * no input -> mute
#  * check if we're playing what's selected
#   * if no -> play selected
#  * check if volume's right
#   * if no -> set volume
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
import time, syslog
import RPi.GPIO as GPIO

client = MPDClient () 
ioList = None        # Map GPIO to function

channelNames = None  # User channel titles
channelUrls = None   # User channel urls

nowPlaying = False   # Status variables
nowVolume = False
nowTimestamp = 1
prevPlaying = False
prevVolume = False
prevTimestamp = 0

ioChannel = None
ioVolume = None
ioUpdated = None

verbose = 3          # Development variables
test = True


def WriteLog (msg, error = False):
  severity = syslog.LOG_INFO
  if error:
    severity = syslog.LOG_ERR
  
  syslog.syslog (severity, msg)

def ConnectMPD (c):
  c.timeout = 10
  c.idletimeout = None
  c.connect ("localhost", 6600)

  WriteLog ("Connected to MPD version " + c.mpd_version)


def StopMPD (c):
  WriteLog("Stopping MPD")
  c.clear ()


def MuteMPD (c):
  WriteLog ("Muting MPD.")
  c.setvol (0)


def PlayMPD (c, volume, url):
  WriteLog ("Playing " + url + " at volume " + str (volume) + ".")
  c.add (url)
  c.play ()
  c.setvol (volume)

def PlayStream (ioVolume, ioChannel):
  global nowPlaying, nowVolume, nowTimestamp, prevPlaying, prevVolume, prevTimestamp

  prevPlaying = nowPlaying
  prevVolume = nowVolume
  prevTimestamp = nowTimestamp

  nowPlaying = int (ioChannel[0])
  nowVolume = int (ioVolume[0])
  nowTimestamp = time.time ()

  WriteLog ("Will play volume " + str (nowVolume) + " channel " + str (nowPlaying) + " with name " + \
      channelNames[nowPlaying] + " at time " + str (nowTimestamp))

  PlayMPD (client, int(ioVolume[0]), channelUrls[ int (ioChannel[0]) ])

def VolumeMPD (c, vol):
  if verbose:
    print "Setting volume to " + str (vol) + "."
  c.setvol (int (vol))


def PopulateTables ():   # Set up mapping from IO to function
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

  ioList = [
    70, #0
    3,  #1
    60, #2
    50, #3
    4,  #4
    5,
    6,
    80, #7
    100,
    90,
    7,  #10
    8,
    40,
    30,
    0,
    1,
    2   #16
  ]

#  if verbose:
#    print str( ioList )

  return ioList

def Compare ():   # Check if we're playing what we're supposed to
  return ( nowPlaying == int (ioChannel[0]) and nowVolume == int (ioVolume[0]) )


def ScanIO (ioList):
  ioVol = list ()
  ioChan = list ()

  for pin, func in enumerate (ioList):
    if pin < 10:                         # Prepare channels for input
      GPIO.setup (pin, GPIO.IN)
    else:
      GPIO.setup (pin, GPIO.OUT)         # Prepare volumes for output

  for pin, func in enumerate (ioList):   # Look for HIGHs
    if pin < 10 and GPIO.input(pin):
      ioVol.append (func)
      break

  # Now we turn it around
  for pin, func in enumerate (ioList):   
    if pin < 10:                         # Prepare channels for output
      GPIO.setup (pin, GPIO.OUT)
    else:        
      GPIO.setup (pin, GPIO.IN)          # Prepare volumes for input

  for pin, func in enumerate (ioList): # Look for HIGHs
    if pin > 10 and GPIO.input(pin):
      ioChan.append (func)
      break

  if 0 == len (ioVol):
    ioVol.append (0)

  if 0 == len (ioChan):
    ioChan.append (0)

  return (ioVol, ioChan)

def UserChannels ():
  channelnames = list ()
  channelurls = list ()

  channelnames.append ('Groove Salad')
  channelurls.append ('http://ice.somafm.com/groovesalad')
  channelnames.append ('Secret Agent')
  channelurls.append ('http://sfstream1.somafm.com:9010')
  channelnames.append ('Mission Control')
  channelurls.append ('http://sfstream1.somafm.com:2020')
  channelnames.append ('NRK P3')
  channelurls.append ('http://lyd.nrk.no/nrk_radio_p3_mp3_h')
  channelnames.append ('NRK Alltid Nyheter')
  channelurls.append ('http://lyd.nrk.no/nrk_radio_alltid_nyheter_mp3_h')
  channelnames.append ('NRK MP3')
  channelurls.append ('http://lyd.nrk.no/nrk_radio_mp3_mp3_h')

  return channelnames, channelurls

# Main

channelNames, channelUrls = UserChannels ()
ConnectMPD (client)
#StopMPD (client)

ioList = PopulateTables ()

GPIO.setmode (GPIO.BCM)
GPIO.setwarnings (False)

while True:
  ioVolume, ioChannel = ScanIO (ioList)
  if not Compare ():
    PlayStream (ioVolume, ioChannel)

  time.sleep (5)
