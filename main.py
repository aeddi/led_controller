import rp2, json, network, requests, machine, logging, time
from machine import Pin, Timer
from utime import sleep_ms
from rotating_log import RotatingFileHandler, Formatter

# ================================
# Constants
# ================================

# Config
CONFIG_FILENAME = 'config.json'
REQUEST_RETRIES = 3
RETRY_INTERVAL_MS = 500

# File logging
FILELOG_MAX_BYTES = 500 * 1024 # 500 KB
FILELOG_BACKUP_COUNT = 2
FILELOG_FILENAME = 'led_controller.log'

# Hardware I/O
LED = Pin('LED', Pin.OUT)
INPUT_3V = Pin(15, Pin.IN)


# ================================
# Logger setup
# ================================

# Logger init
logger = logging.getLogger('led_controller')
logger.setLevel(logging.DEBUG)
log_format = Formatter('%(asctime)s %(levelname)s %(message)s')

# Rotating file handler that logs only INFO level
file_handler = RotatingFileHandler(
    FILELOG_FILENAME,
    maxBytes=FILELOG_MAX_BYTES,
    backupCount=FILELOG_BACKUP_COUNT,
)
file_handler.setLevel(logging.INFO)
file_handler.setFormatter(log_format)
logger.addHandler(file_handler)

# Console handler that logs DEBUG level
console_handler = logging.StreamHandler()
console_handler.setLevel(logging.DEBUG)
console_handler.setFormatter(log_format)
logger.addHandler(console_handler)


# ================================
# Load configuration
# ================================

def load_config():
    try:
        with open(CONFIG_FILENAME, 'r') as file:
            return json.load(file)
    except FileNotFoundError:
        fatal_error(f"Configuration file '{CONFIG_FILENAME}' not found.")
    except json.JSONDecodeError:
        fatal_error(f"Error decoding JSON from '{CONFIG_FILENAME}'.")

config = load_config() or {} # Avoid NoneType errors


# ================================
# Misc. functions
# ================================

# Connect RPi Pico to Wi-Fi
def connect_wifi(ssid, password):
    wlan = network.WLAN()
    wlan.active(True)
    if not wlan.isconnected():
        logger.info('Connecting to network...')
        wlan.connect(ssid, password)
        while not wlan.isconnected():
            machine.idle()
        logger.info('Network connected: %s', wlan.ipconfig('addr4'))
    else:
        logger.debug('Already connected to network: %s', wlan.ipconfig('addr4'))

# Pico board LED blinking functions.
blinker = Timer()

def start_blinking(interval=500, blink_time=500):
    def blink(t):
        LED.on()
        sleep_ms(blink_time)
        LED.off()

    blinker.init(period=interval, callback=blink)

def stop_blinking():
    blinker.deinit()

def working_blinking():
    start_blinking(3000, 100)  # Blink the LED every 3 seconds for 100 ms

def error_blinking():
    start_blinking(200, 100)  # Blink the LED rapidly to indicate an error

# Function to handle fatal errors
def fatal_error(message):
    logger.error(message)
    error_blinking()

    # Listen for a 3s press on the bootsel button to reset
    while True:
      # If the bootsel button is pressed
      if rp2.bootsel_button():
        stop_blinking()
        LED.on() # Turn on the LED to indicate the button is pressed

        # Measure the duration the button is pressed
        start = time.ticks_ms()
        while rp2.bootsel_button(): pass # Wait until the button is released
        delta = time.ticks_diff(time.ticks_ms(), start)

        # If the button was pressed for more than 3 seconds, reset the device
        if delta > 3000:
          logger.info("Button pressed for 3s, rebooting the device...")
          LED.off()
          machine.reset()
        else: # If the button was pressed for less than 3 seconds, start blinking again
          error_blinking()

# Send a request to Govee API to toggle the LED strip
def toggle_led_strip(state):
    data = config['govee']['data']
    data['cmd']['value'] = state

    for _ in range(REQUEST_RETRIES):
        try:
            connect_wifi(
                config['wifi']['ssid'],
                config['wifi']['password']
            )
            resp = requests.put(
                config['govee']['url'],
                data=json.dumps(data),
                headers=config['govee']['headers'],
            )
            logger.debug("Govee response: %s %s", resp.status_code, resp.content)
            return

        except Exception as e:
            logger.error("Error toggling LED strip: %s", e)
            sleep_ms(RETRY_INTERVAL_MS)  # Wait before retrying

    fatal_error("Failed to toggle LED strip after %d retries." % REQUEST_RETRIES)


# ================================
# Main loop
# ================================

# Initialize the current state with an invalid value
# this will ensure the first state change is always detected
current_state = -1
working_blinking()

while True:
    previous_state = current_state
    current_state = INPUT_3V.value()

    if current_state != previous_state:
        logger.info("Input state changed to %s", current_state)
        toggle_led_strip("on" if current_state else "off")

    sleep_ms(100)  # Polling interval to reduce CPU usage
