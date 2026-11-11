from pinky_lcd import LCD
from PIL import Image, ImageSequence
import time

lcd = LCD()

print("Start GIF")

img = Image.open("dance.gif")

for _ in range(10):
    for frame in ImageSequence.Iterator(img):
        lcd.img_show(frame)

print("End GIF")

lcd.close()


