import json
import time
import re
import datetime
import paho.mqtt.client as mqtt
from pymodbus.client import ModbusTcpClient
from pymodbus.exceptions import ModbusException, ModbusIOException, ConnectionException

CONFIG_FILE = "config.json"
POLL_INTERVAL = 60  # seconds

def slugify(value: str) -> str:
    """Convert a string to a safe MQTT-friendly slug."""
    value = value.lower()
    value = re.sub(r"[^a-z0-9_-]+", "_", value)
    return value.strip("_")

def read_config(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

def read_modbus_value(client, address, dtype, register_type="holding"):
    try:
        if dtype in ["bool"]:
            rr = client.read_coils(address)
            return rr.bits[0] if rr.isError() is False else None

        if register_type == "input":
            read_func = client.read_input_registers
        else:
            read_func = client.read_holding_registers

        if dtype in ["uint16", "int16"]:
            rr = read_func(address)
            if rr.isError(): return None
            val = rr.registers[0]
            if dtype == "int16" and val > 32767:
                val -= 65536
            return val

        if dtype in ["uint32", "int32"]:
            rr = [0, 0]
            rr[0] = read_func(address)
            rr[1] = read_func(address+1)
            if rr[0].isError(): return None
            val = (rr[0].registers[0] << 16) | rr[1].registers[0]
            if dtype == "int32" and val > 2147483647:
                val -= 4294967296
            return val
    except (ModbusIOException, ConnectionException, ModbusException) as e:
        print(f"Modbus communication error: {e}")

def publish_homeassistant_discovery(mqttc, base_topic, device_name, datapoint):
    sensor_id = f"{device_name}_{datapoint['name']}"
    topic = f"homeassistant/sensor/{slugify(sensor_id)}/config"
    payload = {
        "name": f"{device_name} {datapoint['name']}",
        "state_topic": f"{base_topic}/{slugify(device_name)}/{slugify(datapoint['name'])}/state",
        "unit_of_measurement": datapoint["unit"],
        "unique_id": sensor_id,
        "device": {
            "identifiers": f"{slugify(device_name)}",
            "name": device_name,
            "manufacturer": "Paradigma",
            "model": "SystaComfortII"
        }
    }
    mqttc.publish(topic, json.dumps(payload), retain=True)

def main():
    cfg = read_config(CONFIG_FILE)
    client = ModbusTcpClient(cfg["modbus"]["host"], port=cfg["modbus"]["port"])
    mqttc = mqtt.Client()
    mqttc.connect(cfg["mqtt"]["host"], cfg["mqtt"]["port"], 60)
    mqttc.loop_start()

    while True:
        for device in cfg["devices"]:
            coil_addr = device.get("presence_coil")
            #print(coil_addr)
            if coil_addr is not None:
                coil = read_modbus_value(client, coil_addr, "bool")
                if not coil:
                    continue  # skip if not present

            
            for dp in device["datapoints"]:
                publish_homeassistant_discovery(mqttc, cfg["mqtt"]["base_topic"], device["name"], dp)
                raw_value = read_modbus_value(client, dp["address"], dp["type"], register_type=dp["register_type"])
                if raw_value is None:
                    continue
                scaled = round(raw_value * dp.get("scaling", 1), 1)
                topic = f"{cfg['mqtt']['base_topic']}/{slugify(device['name'])}/{slugify(dp['name'])}/state"
                mqttc.publish(topic, scaled)
        print(datetime.datetime.now())
        time.sleep(POLL_INTERVAL)

if __name__ == "__main__":
    main()
