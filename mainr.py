import aioble
import bluetooth
import uasyncio as asyncio
from machine import Pin, PWM

# RENAME THIS FILE TO main.py WHEN SAVING TO THE PI PICO (Boat)

# ===============================
# RECEIVER CONFIG
# ===============================

_REMOTE_NAME = "09_C4"                          # Must match transmitter _DEVICE_NAME
_GENERIC_SERVICE_UUID = bluetooth.UUID(0x1848)
_JOYSTICK_CHARACTERISTIC_UUID = bluetooth.UUID(0x2A6E)

connected = False
led = Pin("LED", Pin.OUT)                      # Built-in Pico LED
led_green = Pin(2, Pin.OUT)                   # External green LED (match wiring)

# ===============================
# MOTOR PINS (L298N)
# ===============================

# Make sure pin numbers match your wiring
E1 = PWM(Pin(0))      # Left motor PWM
M1 = Pin(1, Pin.OUT)  # Left motor direction

E2 = PWM(Pin(3))      # Right motor PWM
M2 = Pin(4, Pin.OUT)  # Right motor direction

# Set PWM frequency
E1.freq(500)
E2.freq(500)

# ===============================
# DEADZONE & MAX SPEED
# ===============================

DEADZONE_LOW = -2
DEADZONE_HIGH = 2
MAX_SPEED = 100

# ===============================
# MOTOR CONTROL
# ===============================

def set_motor(E, M, speed):
    """
    Sets one motor speed and direction.
    speed should be in range -100 to 100.
    """

    # Stop motor if inside deadzone
    if DEADZONE_LOW <= speed <= DEADZONE_HIGH:
        E.duty_u16(0)
        return

    # Clamp speed
    speed = max(-MAX_SPEED, min(MAX_SPEED, speed))

    # Smooth response curve
    pwm_val = int(((abs(speed) / 100) ** 2) * 65535)

    # Set direction and PWM
    if speed > 0:
        M.value(0)          # Forward
        E.duty_u16(pwm_val)
    else:
        M.value(1)          # Reverse
        E.duty_u16(pwm_val)

def stop_motors():
    """
    Stops both motors.
    """
    E1.duty_u16(0)
    E2.duty_u16(0)

# ===============================
# OPTIONAL BUTTON HANDLER
# ===============================

def handle_buttons(button_1, button_2):
    """
    Buttons are parsed correctly and available here.
    No action is assigned yet.
    Add future button behaviour in this function.
    """
    pass

# ===============================
# ADC SCALING
# ===============================

def scale_adc(val):
    """
    Converts ADC value 0-65535 into motor command -100 to 100.
    Center is approximately 32768.
    """
    speed = int((val / 65535) * 200 - 100)

    if DEADZONE_LOW <= speed <= DEADZONE_HIGH:
        return 0

    return speed

# ===============================
# HANDLE JOYSTICK DATA
# ===============================

def handle_command(cmd: bytes):
    """
    Expects transmitter message in this exact format:

    LX:<left_x>,LY:<left_y>,RX:<right_x>,RY:<right_y>,B1:<left_button>,B2:<right_button>
    """

    try:
        msg = cmd.decode().strip()
        parts = msg.split(",")

        left_x = int(parts[0].split(":")[1])
        left_y = int(parts[1].split(":")[1])
        right_x = int(parts[2].split(":")[1])
        right_y = int(parts[3].split(":")[1])
        button_1 = int(parts[4].split(":")[1])
        button_2 = int(parts[5].split(":")[1])

    except Exception as e:
        print("Parse error:", e)
        print("Received:", cmd)
        stop_motors()
        return

    # Use joystick vertical axes for tank steering
    left_speed = scale_adc(left_y)
    right_speed = scale_adc(right_y)

    # Drive motors
    set_motor(E1, M1, left_speed)
    set_motor(E2, M2, right_speed)

    # Parse buttons for future use
    handle_buttons(button_1, button_2)

    # Debug print
    # print(f"LX={left_x}, LY={left_y}, RX={right_x}, RY={right_y}, B1={button_1}, B2={button_2}")
    # print(f"Left motor={left_speed}, Right motor={right_speed}")

# ===============================
# BLUETOOTH CONNECT
# ===============================

# DO NOT modify this section unless absolutely required.

async def find_remote():
    async with aioble.scan(5000, interval_us=30000, window_us=30000, active=True) as scanner:
        async for result in scanner:
            if result.name() == _REMOTE_NAME:
                return result.device
    return None

async def connect_task():
    global connected

    while True:
        device = await find_remote()
        print("Connecting...")

        if not device:
            await asyncio.sleep(2)
            continue

        try:
            connection = await device.connect()
            print("Connected")
        except asyncio.TimeoutError:
            continue

        async with connection:
            connected = True
            led.on()

            service = await connection.service(_GENERIC_SERVICE_UUID)
            characteristic = await service.characteristic(_JOYSTICK_CHARACTERISTIC_UUID)
            await characteristic.subscribe(notify=True)

            while True:
                try:
                    cmd = await characteristic.notified()
                    handle_command(cmd)
                except Exception as e:
                    print("Error:", e)
                    connected = False
                    led.off()
                    stop_motors()
                    break

        connected = False
        led.off()
        stop_motors()
        await asyncio.sleep(2)

# ===============================
# LED BLINKER
# ===============================

async def blink_task():
    """
    Fast blink = searching
    Slow blink = connected
    """
    toggle = True

    while True:
        led.value(toggle)
        led_green.value(toggle)
        toggle = not toggle
        await asyncio.sleep_ms(250 if not connected else 1000)

# ===============================
# MAIN LOOP
# ===============================

async def main():
    await asyncio.gather(connect_task(), blink_task())

asyncio.run(main())
