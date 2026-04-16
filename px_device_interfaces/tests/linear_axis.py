

from px_device_interfaces.GPIO_Lib import GPIO_Lib, PinMode
from px_device_interfaces.transports.usb import USBTransportConfig
import time
import threading



DIR_PIN         = 0
STEP_PIN        = 1
EN_PIN          = 2
M0_PIN          = 3
M1_PIN          = 4
SLP_PIN         = 5
END_STOP_PIN    = 6
FAULT_PIN       = 7


gpio_usb_config = USBTransportConfig(auto_connect=True, debug=False)
gpio_lib = GPIO_Lib(transport_config=gpio_usb_config)
i2c = GPIO_Lib.I2C(gpio_lib=gpio_lib, i2c_bus=0)
oled = GPIO_Lib.Display.DisplaySSD1306(
    gpio_lib=gpio_lib,
    i2c=i2c,
    address=0x3C,
    width=128,
    height=64,
)

gpio_lib.start()
time.sleep(0.5)  # Wait for transport to be ready
oled.setup()
oled.clear()
oled.set_cursor(0, 0)
oled.write_text("GPIO_Lib OK")
gpio_lib.await_send_empty()
time.sleep(0.1)

# (updater thread will be started after stepper configuration)

# OLED updater thread: poll stepper status and refresh display periodically
_stop_oled_updater = threading.Event()

def _oled_position_updater(stepper, oled, gpio_lib, stop_event, interval=0.1):
    while not stop_event.is_set():
        try:
            status = stepper.get_status(timeout=0.5)
        except Exception:
            time.sleep(interval)
            continue
        
        pos_str = f"{status.get('position', 0.0):.2f} mm"
        state = status.get("state", "")

        try:
            oled.set_cursor(0, 0)
            oled.write_text(f"Pos: {pos_str}        ")
            oled.set_cursor(0, 10)
            oled.write_text(f"State: {state}        ")
            gpio_lib.await_send_empty()
        except Exception:
            # Ignore display errors and continue
            pass
        time.sleep(interval)

# (updater thread will be started after stepper configuration)


stepper = GPIO_Lib.Stepper.StepperSTSPIN220(
    gpio_lib=gpio_lib,
    step_pin=STEP_PIN,
    dir_pin=DIR_PIN,
    enable_pin=EN_PIN,
    m0_pin=M0_PIN,
    m1_pin=M1_PIN,
    sleep_pin=SLP_PIN,
    fault_pin=FAULT_PIN,
    steps_per_revolution=200,
    max_speed=1000,
    acceleration=500,
)
stepper.setup()
stepper.set_microstepping_mode(GPIO_Lib.Stepper.MICROSTEPS.X1_32)
stepper.initialize()
stepper.configure_motion_mm(
    steps_per_mm=50.0,
    max_speed_mm_s=200.0,
    max_accel_mm_s2=500.0,
)

oled.clear()
gpio_lib.await_send_empty()
time.sleep(0.1)

# Start the OLED updater thread now that the stepper is configured
_updater_thread = threading.Thread(
    target=_oled_position_updater,
    args=(stepper, oled, gpio_lib, _stop_oled_updater),
    daemon=True,
)
_updater_thread.start()


# Move positiv untill end stop is triggered
gpio_lib.pinMode(END_STOP_PIN, PinMode.INPUT, "END_STOP")
gpio_lib.await_send_empty()
time.sleep(0.1)

# Home fast until we hit the end stop, then
stepper.configure_homing(
    speed_mm_s=50.0,
    accel_mm_s2=200.0,
    end_stop_left=END_STOP_PIN
)
stepper.home()
stepper.wait_until_stopped()
# move a bit away from the end stop
stepper.set_direction(invert=True)
stepper.set_current_position_mm(100.0)
stepper.move_to_position_mm(95.0, speed=50.0, acceleration=200.0)
stepper.wait_until_stopped()
stepper.set_direction(invert=False)

# home slowly to find the end stop position
stepper.configure_homing(
    speed_mm_s=10.0,
    accel_mm_s2=40.0,
    end_stop_left=END_STOP_PIN
)

gpio_lib.await_send_empty()
stepper.home()
stepper.wait_until_stopped()


calibration_position_mm = 0.0
stepper.set_direction(invert=True)
stepper.set_current_position_mm(100.0)
stepper.move_to_position_mm(calibration_position_mm, speed=55.0, acceleration=200.0)
stepper.wait_until_stopped()

POS_ONE_MM = 50.0 - 25.0
POS_TWO_MM = 50.0 + 25.0

for speed in range(50, 130, 10):
    print(f"Moving to {POS_ONE_MM} mm at {speed} mm/s …")
    stepper.move_to_position_mm(POS_ONE_MM, speed=speed, acceleration=200.0)
    stepper.wait_until_stopped()
    print(f"Moving to {POS_TWO_MM} mm at {speed} mm/s …")
    stepper.move_to_position_mm(POS_TWO_MM, speed=speed, acceleration=400.0)
    stepper.wait_until_stopped()

stepper.move_to_position_mm(90, speed=10.0, acceleration=200.0)
stepper.wait_until_stopped()


# Stop OLED updater thread cleanly
time.sleep(.5)  # Let it run for a bit after motion is done
_stop_oled_updater.set()
try:
    _updater_thread.join(timeout=1.0)
except Exception:
    pass
gpio_lib.stop()
