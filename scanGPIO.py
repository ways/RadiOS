#!/usr/bin/env python

# Main part of RadiOP
# Requires python-mpd
#
# Pseudo code:
# * load user configs
# * feel input
#  * muted for > x sec -> stop
#  * no input -> mute
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
# 7       | 40

from mpd import MPDClient
import time, syslog
import RPi.GPIO as GPIO

client = MPDClient () # Connection to mpd
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

verbose = True       # Development variables

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
  return True

def StopMPD (c):
  WriteLog("Stopping MPD")
  c.clear ()


def MuteMPD (c):
  WriteLog ("Muting MPD.")
  VolumeMPD (c, 0)


def VolumeMPD (c, vol):
  WriteLog ("Setting volume to " + str (vol) + ".")
  c.setvol (int (vol))


def PlayMPD (c, volume, url):
  try:
#    StopMPD (c)
    WriteLog ("Playing " + url + " at volume " + str (volume) + ".")
    c.add (url)
    c.play ()
    c.crop ()
    VolumeMPD (c, volume)
  except mpd.ConnectionError():
    WriteLog ("Error playing with MPD", True)
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
  PlayMPD (client, nowVolume, channelUrls[nowPlaying])


def PopulateTables ():   # Set up mapping from IO to function
  # bcn  | function
  # -
  # 8    | volume 100
  # 9    | volume 90
  # 7    | volume 80
  # -
  # 0    | volume 70
  # 2    | volume 60
  # 3    | volume 50
  # -
  # 12   | volume 40
  # 13	 | volume 30
  # 14   | mute / off
  # -

  # -
  # -
  # -
  # 15   | channel 1
  # 16   | channel 2
  # 1    | channel 3
  # -
  # 4    | channel 4
  # 5    | channel 5
  # -
  # 6    | channel 6
  # 10   | channel 7
  # 11   | channel 8

#  ioList = [
#    -1, #0
#    70, #0
#    3,  #1
#    60, #2
#    50, #3
#    4,  #4
#    5,
#    6,
#    80, #7
#    100,
#    90,
#    7,  #10
#    8,
#    40,
#    30,
#    0,
#    1,
#    2   #16
#  ]


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
    80,  #4
    -1,  #5
    -1,  #6
    9,   #7
    8,   #8
    30,  #9
    40, #10
    1,  #11
    -1, #12
    -1, #13
    2,  #14
    3,  #15
    -1, #16
    70, #17
    4,  #18
    -1, #19
    -1, #20
    -1,
    50, #22
    5,  #23
    6,  #24
    7,  #25
    -1,
    60  #27
  ]

  if verbose:
    print ioList

  return ioList


def Compare ():      # True if we do not need to start something
  global nowPlaying, nowVolume

#  if -1 == int (ioChannel[0]) \
#    and (time.time () -15 < nowTimestamp) \
#    and 0 < nowVolume:                 # Mute if cable is unplugged
#    WriteLog ("Muting MPD due to channel " + str (ioChannel[0]) + \
#      " and nowTime " + str (nowTimestamp) + " and nowvol " + str (nowVolume))
#    nowVolume = 0
#    MuteMPD (client)
#    return True

  if -1 == int (ioChannel[0]) \
    and nowPlaying:                    # Stop if unplugged for more that a few seconds
    WriteLog ("Stopping MPD due to nowPlaying: " + str (nowPlaying) )
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
      if verbose:
        print "Found high pin", pin, "func", func, "while looking for channels"

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
      if verbose:
        print "Found high pin", pin, "func", func, "while looking for volumes"

  if 0 == len (ioVol):
    ioVol.append (0)
    print "No volume set"

  GPIO.cleanup()
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
  print "Exiting..."

finally:  
    GPIO.cleanup()
