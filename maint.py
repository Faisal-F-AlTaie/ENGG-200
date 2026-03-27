import aioble
import bluetooth
import uasyncio as asyncio
from micropython import const
from machine import ADC, Pin

# RENAME THIS FILE TO main.py WHEN SAVING TO THE PI PICO (Controller)

# =====================================================
# TRANSMITTER CONFIGURATION
# =====================================================

# Unique name for your controller (must match the receiver)
_DEVICE_NAME = "09_C4"

# BLE service identifiers (provided by course starter code)
_GENERIC_SERVICE_UUID = bluetooth.UUID(0x1848)
_JOYSTICK_CHARACTERISTIC_UUID = bluetooth.UUID(0x2A6E)

# Bluetooth advertising interval
_ADV_INTERVAL_MS = 250_000

# Device appearance for BLE
_BLE_APPEARANCE_GENERIC_REMOTE_CONTROL = const(384)

# =====================================================
# HARDWARE SETUP
# =====================================================

# Analog joystick axes
# Make sure these pin numbers match your wiring

adc_left_y = ADC(27)     # Left joystick vertical axis
adc_left_x = ADC(26)     # Left joystick horizontal axis
adc_right_y = ADC(28)    # Right joystick vertical axis
adc_right_x = ADC(29)    # Right joystick horizontal axis

# Joystick push buttons
# Using pull-up resistors so:
# pressed = 1
# not pressed = 0

button_left = Pin(14, Pin.IN, Pin.PULL_UP)
button_right = Pin(15, Pin.IN, Pin.PULL_UP)

# Built-in Pico LED (used to indicate connection status)
led = Pin("LED", Pin.OUT)

# =====================================================
# CONNECTION STATE VARIABLES
# =====================================================

connected = False     # True when BLE is connected
connection = None     # Stores the active BLE connection

# =====================================================
# BLE SERVICE SETUP
# =====================================================

# Create BLE service
remote_service = aioble.Service(_GENERIC_SERVICE_UUID)

# Create characteristic that sends joystick data
joystick_char = aioble.Characteristic(
    remote_service,
    _JOYSTICK_CHARACTERISTIC_UUID,
    read=True,
    notify=True
)

# Register the BLE service
aioble.register_services(remote_service)

# =====================================================
# BLE TASKS
# =====================================================

# NOTE:
# Do not modify advertise_task() or blink_task()
# unless absolutely necessary.

async def advertise_task():
    """
    Handles Bluetooth advertising and connections.
    The controller continuously advertises itself
    until the receiver connects.
    """

    global connected, connection

    while True:
        connected = False

        async with await aioble.advertise(
            _ADV_INTERVAL_MS,
            name=_DEVICE_NAME,
            appearance=_BLE_APPEARANCE_GENERIC_REMOTE_CONTROL,
            services=[_GENERIC_SERVICE_UUID]
        ) as connection:

            connected = True
            await connection.disconnected()


async def joystick_task():
    """
    Reads joystick values and button states,
    then sends them to the receiver via BLE.
    """

    global connected, connection

    # Store previous values to avoid sending identical data repeatedly
    last_lx = last_ly = -1
    last_rx = last_ry = -1
    last_b1 = last_b2 = -1

    while True:

        # Only read inputs if the controller is connected
        if connected:

            # =================================
            # Read joystick analog values
            # =================================

            left_y = adc_left_y.read_u16()
            left_x = adc_left_x.read_u16()

            right_y = adc_right_y.read_u16()
            right_x = adc_right_x.read_u16()

            # =================================
            # Read button states
            # =================================

            # Pull-up logic:
            # pressed = 1
            # not pressed = 0

            left_button = 0 if button_left.value() else 1
            right_button = 0 if button_right.value() else 1

            # =================================
            # Send data only if something changed
            # =================================

            if (
                left_x != last_lx or
                left_y != last_ly or
                right_x != last_rx or
                right_y != last_ry or
                left_button != last_b1 or
                right_button != last_b2
            ):

                # Create message string
                msg = (
                    f"LX:{left_x},"
                    f"LY:{left_y},"
                    f"RX:{right_x},"
                    f"RY:{right_y},"
                    f"B1:{left_button},"
                    f"B2:{right_button}"
                )

                # Send message to receiver
                joystick_char.notify(connection, msg.encode())

                # Update stored values
                last_lx = left_x
                last_ly = left_y
                last_rx = right_x
                last_ry = right_y
                last_b1 = left_button
                last_b2 = right_button

                # Print message to serial for debugging
                print("Sent →", msg)

        # Small delay to control update rate
        await asyncio.sleep_ms(50)


async def blink_task():
    """
    Blinks the Pico LED to indicate connection status.

    Slow blink = connected
    Fast blink = searching for receiver
    """

    toggle = True

    while True:

        led.value(toggle)
        toggle = not toggle

        await asyncio.sleep_ms(1000 if connected else 250)


# =====================================================
# MAIN PROGRAM
# =====================================================

async def main():

    # Run BLE advertising, joystick reading, and LED blinking simultaneously
    await asyncio.gather(
        advertise_task(),
        joystick_task(),
        blink_task()
    )

# Start the program
asyncio.run(main())