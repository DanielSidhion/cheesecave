from etcdstate import EtcdBackedState


class CheeseCaveConfigs(EtcdBackedState):
    def __init__(self):
        super().__init__('/cheesecave/config')

    def default_state(self):
        return {
            # How many sensors are plugged in.
            'sensors': 0,
            # Whether the humidifier is plugged in.
            'humidifier_connected': False,

            # How long to wait without any button press before returning to the general info menu.
            'menu_return_delay_seconds': 20,
            # How long to wait before grabbing temperature and humidity data.
            'sensor_delay_seconds': 5,
            # How long to wait before updating the e-ink display.
            'display_update_delay_seconds': 60,
            # How long to wait before updating the e-ink display if a delay was requested due to user input.
            'display_update_input_delay_seconds': 3,
            # How long to keep heater running when it's supposed to run.
            'heater_on_seconds': 1,
            # How long to wait before turning on heater again.
            'heater_delay_seconds': 20,
            # How long to wait between measurements.
            'measurement_delay_seconds': 5,
            # How long to wait between deciding humidifier action.
            'humidifier_decision_delay_seconds': 60,
        }
