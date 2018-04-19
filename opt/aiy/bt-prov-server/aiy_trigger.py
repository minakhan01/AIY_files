# TODO: Make this library available system wide.
import sys
sys.path.append("/home/pi/AIY-projects-python/src")

from gpiozero import Button
from gpiozero import LED
from aiy.vision.pins import BUTTON_GPIO_PIN
from aiy.vision.pins import LED_1

BLINK_ON_TIME_S = 0.5
BLINK_OFF_TIME_S = 0.5
BUTTON_HOLD_TIME_S = 5


class AiyTrigger(object):
  """Trigger interface for AIY kits."""

  def __init__(self, triggered):
    self._triggered = triggered
    self._active = False

    self._led = LED(LED_1)
    self._button = Button(BUTTON_GPIO_PIN, hold_time=BUTTON_HOLD_TIME_S)
    self._button.when_held = triggered

  def Close(self):
    self._led.off()

  def SetActive(self, active):
    if active:
      self._led.blink(on_time=BLINK_ON_TIME_S, off_time=BLINK_OFF_TIME_S)
    else:
      self._led.off()
