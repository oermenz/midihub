from luma.core.interface.serial import i2c
from luma.oled.device import ssd1306
from luma.core.render import canvas
from PIL import ImageFont

serial = i2c(port=1, address=0x3C)
device = ssd1306(serial)
try:
    font = ImageFont.load("/home/oermens/midihub/fonts/miniwi-8.bdf")
except Exception:
    font = ImageFont.load_default()

with canvas(device) as draw:
    draw.text((0, 0), "HELLO", font=font, fill=255)
