import sys
import os
import time
import threading
import getpass


sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import logging

logging.basicConfig(level=logging.INFO)
_LOGGER = logging.getLogger(__name__)

import argparse
from custom_components.dreame_mower.dreame.device import DreameMowerDevice
from custom_components.dreame_mower.dreame.const import DreameMowerAction
from custom_components.dreame_mower.dreame.const import DreameMowerProperty

def main():
    parser = argparse.ArgumentParser(description="Dreame Mower CLI")
    parser.add_argument("--username", default=None, help="Cloud username (email)")
    parser.add_argument("--password", default=None, help="Cloud password")
    parser.add_argument(
        "--country", default=None, help="Cloud country code (e.g. 'cn', 'eu')"
    )
    parser.add_argument("--device_id", default=None, help="Device ID. If you don't know it, run 'list_devices.py' first.")
    parser.add_argument("--action", choices=["get", "set", "action", "listen", "getall"], help="Action to perform")
    parser.add_argument("--property", help="Property name (enum name or string)")
    parser.add_argument("--value", help="Value to set (for 'set' action)")
    args = parser.parse_args()

    # Prompt for username, password, country if not provided
    if args.username is None:
        args.username = input("Enter username (email): ")
    if args.password is None:
        args.password = getpass.getpass("Enter password: ")
    if args.device_id is None:
        args.device_id = input("Enter device ID: ")
    if args.country is None:
        print("No country provided, using default: eu")
        args.country = "eu"

    # Default to get BATTERY_LEVEL if no action/property provided
    action = args.action if args.action else "get"
    property_name = args.property if args.property else "BATTERY_LEVEL"

    device = DreameMowerDevice(
        name="",
        host="",
        token="",
        mac="",
        username=args.username,
        password=args.password,
        country=args.country,
        device_id=args.device_id,
    )

    # For device listing, we need access to the underlying protocol/cloud object
    # This assumes DreameMowerDevice exposes ._protocol or ._cloud

    def callback(value=None):
        _LOGGER.info("Device callback: %s", value)
    device.listen(callback)

    def on_error(ex=None):
        _LOGGER.error(f"Device error: {ex}")
    device.listen_error(on_error)

    # Add listeners for specific properties: ERROR, TASK_STATUS, CLEANING_PAUSED
    def on_error_changed(value):
        _LOGGER.info(f"ERROR changed: {value}")
    device.listen(on_error_changed, DreameMowerProperty.ERROR)

    def on_task_status_changed(value):
        _LOGGER.info(f"TASK_STATUS changed: {value}")
    device.listen(on_task_status_changed, DreameMowerProperty.TASK_STATUS)

    def on_status_changed(value):
        _LOGGER.info(f"STATUS changed: {value}")
    device.listen(on_status_changed, DreameMowerProperty.STATUS)

    def on_state_changed(value):
        _LOGGER.info(f"STATE changed: {value}")
    device.listen(on_state_changed, DreameMowerProperty.STATE)

    def on_cleaning_paused_changed(value):
        _LOGGER.info(f"CLEANING_PAUSED changed: {value}")
    device.listen(on_cleaning_paused_changed, DreameMowerProperty.CLEANING_PAUSED)

    def on_battery_level_changed(value):
        _LOGGER.info(f"BATTERY_LEVEL changed: {value}")
    device.listen(on_battery_level_changed, DreameMowerProperty.BATTERY_LEVEL)

    thread = threading.Thread(target=device.update)
    thread.start()

    # Wait for ready or error, print device state every second
    timeout = 30
    start = time.time()
    while not device.available and time.time() - start < timeout:
        _LOGGER.info("Connecting to device...")
        time.sleep(1)

    if not device.available:
        _LOGGER.error("Device connection failed or timed out.")
        turndown(device, thread, 1)
    else:
        _LOGGER.info("Device connected successfully.")

    if action == "listen":
        _LOGGER.info("Listening mode enabled. Press Ctrl+C to exit.")
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            _LOGGER.info("Interrupted by user. Exiting listening mode.")
            turndown(device, thread, 0)
    elif action == "get":
        if DreameMowerProperty and hasattr(DreameMowerProperty, property_name):
            prop = getattr(DreameMowerProperty, property_name)
        else:
            prop = property_name
        value = device.get_property(prop)
        _LOGGER.info(f"{property_name}: {value}")
    elif action == "set":
        if args.value is None:
            _LOGGER.error("--value required for set action")
            turndown(device, thread, 1)
        if DreameMowerProperty and hasattr(DreameMowerProperty, property_name):
            prop = getattr(DreameMowerProperty, property_name)
        else:
            prop = property_name
        try:
            device.set_property_value(prop, args.value)
            _LOGGER.info(f"Set {property_name} to {args.value}")
        except Exception as e:
            _LOGGER.error(f"Error: {e}")
            turndown(device, thread, 1)
    elif action == "action":
        if DreameMowerAction and hasattr(DreameMowerAction, property_name):
            action = getattr(DreameMowerAction, property_name)
        else:
            action = property_name
        try:
            device.call_action(action)
            _LOGGER.info(f"Performed action: {action}")
        except Exception as e:
            _LOGGER.error(f"Error: {e}")
            turndown(device, thread, 1)
    elif action == "getall":
        # Get all properties from DreameMowerProperty
        props = [
            attr for attr in dir(DreameMowerProperty)
            if not attr.startswith("__")
            and isinstance(getattr(DreameMowerProperty, attr), (str, int))
        ]
        results = {}
        for prop_name in props:
            prop = getattr(DreameMowerProperty, prop_name)
            try:
                value = device.get_property(prop)
            except Exception as e:
                value = f"Error: {e}"
            if value is not None:
                results[prop_name] = value
        for k, v in results.items():
            print(f"{k}: {v}")

    turndown(device, thread, 0)

def turndown(device, thread, exit_code=0):
    """Clean up: disconnect device and join thread, then exit."""
    try:
        device.disconnect()
    except Exception as e:
        _LOGGER.warning(f"Error during disconnect: {e}")
    if thread.is_alive():
        thread.join(timeout=2)
    sys.exit(exit_code)

if __name__ == "__main__":
    main()
    
