#!/usr/bin/python3

import time
import sys

import Adafruit_GPIO.SPI as SPI
import Adafruit_SSD1306

from PIL import Image
from PIL import ImageDraw
from PIL import ImageFont

import subprocess

import fcntl
import errno

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

# Raspberry Pi pin configuration:
RST = None     # on the PiOLED this pin isnt used
# Note the following are only used with SPI:
DC = 23
SPI_PORT = 0
SPI_DEVICE = 0

# 128x64 display with hardware I2C:
disp = Adafruit_SSD1306.SSD1306_128_64(rst=RST)

disp.begin()

# Clear display.
disp.clear()
disp.display()

# Create blank image for drawing.
width = disp.width
height = disp.height
image = Image.new('1', (width, height))

# Get drawing object to draw on image.
draw = ImageDraw.Draw(image)

# Draw a black filled box to clear the image.
draw.rectangle((0,0,width,height), outline=0, fill=0)

padding = -2
top = padding
bottom = height-padding
x = 0

#font = ImageFont.load_default()
height = 12
font = ImageFont.truetype('/usr/share/fonts/truetype/lato/Lato-Semibold.ttf', height)

for y in range(0, len(sys.argv)-1):
    draw.text((x, top+y*height), sys.argv[y+1], font=font, fill=255)

disp.image(image)
disp.display()

releaseLock(lock_fd)    
