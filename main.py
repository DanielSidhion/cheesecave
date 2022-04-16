import os
from time import sleep
from threading import Timer
import digitalio
import busio
import board
import RPi.GPIO as GPIO
import adafruit_sht31d
from adafruit_epd.ssd1680 import Adafruit_SSD1680
from display import DisplayController
from state import CheeseCaveControllerMode, CheeseCaveState
from configs import CheeseCaveConfigs
import logging


logger = logging.getLogger(__name__)


class CheeseCaveController:
    def __init__(self):
        self.i2c = busio.I2C(board.SCL, board.SDA)
        self.spi = busio.SPI(board.SCK, MOSI=board.MOSI, MISO=board.MISO)
        self.ecs = digitalio.DigitalInOut(board.CE0)
        self.dc = digitalio.DigitalInOut(board.D22)
        self.rst = digitalio.DigitalInOut(board.D27)
        self.busy = digitalio.DigitalInOut(board.D17)

        logger.info('Controller is loading configs and state.')
        self.configs = CheeseCaveConfigs()
        # The state is the one that receives button events when someone presses a button. One of the actions is shutting down the board, so we need to give it a shutdown callback.
        self.state = CheeseCaveState(self.shutdown)
        logger.info('Configs and state loaded.')

        self.display = Adafruit_SSD1680(
            122,
            250,
            self.spi,
            cs_pin=self.ecs,
            dc_pin=self.dc,
            sramcs_pin=None,
            rst_pin=self.rst,
            busy_pin=self.busy,
        )
        self.display.rotation = 1
        self.display_controller = DisplayController(self.display, self.state)

        logger.info('Display controller started.')

        self.setup_sensors()
        self.setup_humidifier()

        # Up and down buttons are configured directly with RPi.GPIO so we can have threaded callbacks whenever a button press is detected. This avoids all the busy loop that we'd have to do if we used adafruit's code instead.
        GPIO.setmode(GPIO.BCM)
        GPIO.setup(5, GPIO.IN, pull_up_down=GPIO.PUD_UP)
        GPIO.add_event_detect(5, GPIO.RISING, callback=self.button_pressed, bouncetime=50)
        GPIO.setup(6, GPIO.IN, pull_up_down=GPIO.PUD_UP)
        GPIO.add_event_detect(6, GPIO.RISING, callback=self.button_pressed, bouncetime=50)

        self._return_menu_timer = None
        self._display_update_timer = None

        self._measurement_rolling_window_size = int(self.configs.display_update_delay_seconds / \
            self.configs.measurement_delay_seconds)
        self._measurements = []

    def averaged_measures(self):
        summed_measurements = list(map(sum, zip(*self._measurements)))
        temperature = summed_measurements[0] / len(self._measurements)
        humidity = summed_measurements[1] / len(self._measurements)

        return (temperature, humidity)

    def start(self):
        self.heater_cycle()
        self.measure()
        self.make_humidifier_decision()
        self.update_display()

    def shutdown(self):
        pass

    def setup_sensors(self):
        if self.configs.sensors == 0:
            logger.warning("Controller is configured to control 0 sensors! Temperature and humidity data won't be available.")
            self._sensors = []
        else:
            logger.info(f'Controller started with {self.configs.sensors} sensors.')
            self._sensors = [adafruit_sht31d.SHT31D(self.i2c)]

            if self.configs.sensors == 2:
                self._sensors.append(adafruit_sht31d.SHT31D(self.i2c, address=0x45))

        for sensor in self._sensors:
            sensor.repeatability = adafruit_sht31d.REP_HIGH

    def setup_humidifier(self):
        if not self.configs.humidifier_connected:
            logger.warning(
                "Controller is configured without a humidifer connected! The controller won't be able to control humidity.")
            self.humidifier_control = None
        else:
            logger.info('Humidifier control configured.')
            self.humidifier_control = digitalio.DigitalInOut(board.D24)
            self.humidifier_control.switch_to_output()

    def button_pressed(self, channel):
        if self._return_menu_timer is not None:
            self._return_menu_timer.cancel()
            self._return_menu_timer = None

        if channel == 6:
            self.state.top_button_pressed()
        elif channel == 5:
            self.state.bottom_button_pressed()

        self._return_menu_timer = Timer(
            self.configs.menu_return_delay_seconds, self.return_to_general_menu)
        self._return_menu_timer.start()
        self.update_display(delay=True)

    def return_to_general_menu(self):
        self.state.mode = CheeseCaveControllerMode.GENERAL_INFO
        self.update_display()
        self._return_menu_timer = None

    def heater_cycle(self):
        new_timer = None

        if self.state.heater_on:
            for sensor in self._sensors:
                sensor.heater = False
            self.state.heater_on = False
            new_timer = Timer(
                self.configs.heater_delay_seconds, self.heater_cycle)
        else:
            for sensor in self._sensors:
                sensor.heater = True
            self.state.heater_on = True
            new_timer = Timer(self.configs.heater_on_seconds, self.heater_cycle)

        new_timer.start()

    def update_display(self, delay=False):
        if self._display_update_timer is not None:
            self._display_update_timer.cancel()

        if not delay:
            self.display_controller.update_display()

        next_update_in = self.configs.display_update_delay_seconds
        if delay:
            next_update_in = self.configs.display_update_input_delay_seconds

        self._display_update_timer = Timer(next_update_in, self.update_display)
        self._display_update_timer.start()

    def measure(self):
        temperature = []
        humidity = []

        for sensor in self._sensors:
            temperature.append(sensor.temperature)
            humidity.append(sensor.relative_humidity)

        # Denominator has a max() to handle case when any of the lists is empty.
        temperature = sum(temperature) / max(1, len(temperature))
        humidity = sum(humidity) / max(1, len(humidity))

        self._measurements.append((temperature, humidity))

        exceeded_measurements = len(self._measurements) - self._measurement_rolling_window_size
        if exceeded_measurements > 0:
            # Getting rid of the oldest measurements that exceed the capacity.
            self._measurements = self._measurements[exceeded_measurements:]

        avg_measures = self.averaged_measures()
        self.state.temperature = avg_measures[0]
        self.state.humidity = avg_measures[1]

        new_timer = Timer(self.configs.measurement_delay_seconds, self.measure)
        new_timer.start()

    def turn_off_humidifier(self):
        if self.humidifier_control is None or not self.state.humidifier_state:
            return

        logger.debug('Turning humidifier off.')

        self.humidifier_control.value = True
        sleep(0.05)
        self.humidifier_control.value = False
        self.state.humidifier_state = False

    def turn_on_humidifier(self):
        if self.humidifier_control is None or (self.state.humidifier_state or not self.state.has_water):
            return

        logger.debug('Turning humidifier on.')

        self.humidifier_control.value = True
        sleep(0.05)
        self.humidifier_control.value = False
        sleep(0.1)
        self.humidifier_control.value = True
        sleep(0.05)
        self.humidifier_control.value = False
        self.state.humidifier_state = True

    def make_humidifier_decision(self):
        if self.state.humidity >= self.state.desired_humidity:
            self.turn_off_humidifier()
        else:
            self.turn_on_humidifier()

        new_timer = Timer(
            self.configs.humidifier_decision_delay_seconds, self.make_humidifier_decision)
        new_timer.start()

if __name__ == "__main__":
    logging.basicConfig(
        format='%(asctime)s [%(levelname)s] %(module)s: %(message)s', level=logging.DEBUG)
    logger.info('Initializing controller.')
    controller = CheeseCaveController()
    logger.info('Controller initialized. Starting.')
    controller.start()
    logger.info('Controller started. Will now enter an infinite sleep loop.')
    while True:
        sleep(3600)
