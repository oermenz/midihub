#!/usr/bin/python3

from luma.core.interface.serial import i2c
from luma.core.render import canvas
from luma.oled.device import ssd1306

import sys
import time
import fcntl
import errno
import subprocess

serial = i2c(port=1, address=0x3C)
device = ssd1306(serial, rotate=0)

def acquireLock():
    while True:
      try:
        ''' acquire exclusive lock file access '''
        locked_file_descriptor = open('/tmp/lockfile.LOCK', 'w+')
        fcntl.lockf(locked_file_descriptor, fcntl.LOCK_EX)
        return locked_file_descriptor
      except IOError as e:
        if e.errno != errno.EAGAIN:
            raise
        else:
            time.sleep(2)

def releaseLock(locked_file_descriptor):
    ''' release exclusive lock file access '''
    locked_file_descriptor.close()

lock_fd = acquireLock()

padding = -2
top = padding
height = 12
bottom = height-padding
x = 0

for y in range(0, len(sys.argv)-1):
  with canvas(device) as draw:
    draw.rectangle(device.bounding_box, outline="white", fill="black")
    draw.text((x, top+y*height), sys.argv[y+1], fill="white")

time.sleep(1)

releaseLock(lock_fd)
