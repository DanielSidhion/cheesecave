from enum import Enum
import time
from etcdstate import EtcdBackedState


class CheeseCaveControllerMode(Enum):
    GENERAL_INFO = 0
    HUMIDITY_SET = 1
    SETTINGS = 2
    WATER_SET = 3


class CheeseCaveState(EtcdBackedState):
    def __init__(self, shutdown_hook=None):
        super().__init__('/cheesecave/state')

        self.temperature = 0
        self.humidity = 0
        self.mode = CheeseCaveControllerMode.GENERAL_INFO
        self._shutdown_hook = shutdown_hook

    def default_state(self):
        return {
            'desired_humidity': 50,
            'has_water': True,
            'heater_on': False,
            'humidifier_state': False,
            'time_humidifier_turned_on': None,
            'total_humidifier_run_time': 0,
            'humidifier_capacity_time_seconds': 4 * 60 * 60,  # 4 hours
        }

    @property
    def desired_humidity(self):
        return self.state['desired_humidity']

    @desired_humidity.setter
    def desired_humidity(self, value):
        value = max(0, min(100, value))
        self.state['desired_humidity'] = value

    @property
    def humidifier_state(self):
        return self.state['humidifier_state']

    @humidifier_state.setter
    def humidifier_state(self, value):
        if value:
            self.state['time_humidifier_turned_on'] = time.time()
        else:
            self.state['total_humidifier_run_time'] += time.time() - \
                self.state['time_humidifier_turned_on']
            self.state['time_humidifier_turned_on'] = None

        self.state['humidifier_state'] = value

    @property
    def water_level(self):
        used_water_percentage = self.state['total_humidifier_run_time'] / \
            self.state['humidifier_capacity_time_seconds']

        if used_water_percentage < 0.05:
            return 1

        return 1 - used_water_percentage

    def top_button_pressed(self):
        if self.mode == CheeseCaveControllerMode.GENERAL_INFO:
            self.mode = CheeseCaveControllerMode.HUMIDITY_SET
        elif self.mode == CheeseCaveControllerMode.HUMIDITY_SET:
            self.desired_humidity = self.desired_humidity + 1
        elif self.mode == CheeseCaveControllerMode.SETTINGS:
            if self._shutdown_hook is not None:
                self._shutdown_hook()
        elif self.mode == CheeseCaveControllerMode.WATER_SET:
            self.state['has_water'] = False

    def bottom_button_pressed(self):
        if self.mode == CheeseCaveControllerMode.GENERAL_INFO:
            self.mode = CheeseCaveControllerMode.SETTINGS
        elif self.mode == CheeseCaveControllerMode.HUMIDITY_SET:
            self.desired_humidity = self.desired_humidity - 1
        elif self.mode == CheeseCaveControllerMode.SETTINGS:
            self.mode = CheeseCaveControllerMode.WATER_SET
        elif self.mode == CheeseCaveControllerMode.WATER_SET:
            self.state['has_water'] = True
            self.state['total_humidifier_run_time'] = 0
