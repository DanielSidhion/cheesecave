import os
import time

from display import DisplayController
from state import CheeseCaveControllerMode, CheeseCaveState

state = CheeseCaveState()
state.temperature = 33
state.humidity = 55.5
state.desired_humidity = 60
state._total_humidifier_run_time = 0#4 * 60 * 60
state.has_water = True
state.mode = CheeseCaveControllerMode.GENERAL_INFO

disp_controller = DisplayController(None, state)
disp_controller.show_debug_image()