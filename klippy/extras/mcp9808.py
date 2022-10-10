# Support for MCP9808 temperature sensor

import logging
from . import bus
from struct import unpack_from

REPORT_TIME = 1.5
DEFAULT_ADDR = 0x18  # MCP9808 I2C Address

MCP9808_REG_AMBIENT_TEMP = 0x05
MCP9808_REG_MANUF_ID = 0x06
MCP9808_REG_DEVICE_ID = 0x07


class MCP9808:
    def __init__(self, config):
        self.printer = config.get_printer()
        self.name = config.get_name().split()[-1]
        self.reactor = self.printer.get_reactor()
        self.i2c = bus.MCU_I2C_from_config(
            config, default_addr=DEFAULT_ADDR, default_speed=100000
        )
        self.mcu = self.i2c.get_mcu()
        self.min_temp = 0
        self.max_temp = 0
        self.temp = 0.0
        self.sample_timer = None
        self.printer.add_object("mcp9808 " + self.name, self)
        self.printer.register_event_handler(
            "klippy:connect", self.handle_connect)

    def handle_connect(self):
        manufacture_id = unpack_from(">H", self.get_man_id())[0]
        device_id = unpack_from(">H", self.get_dev_id())[0]
        logging.info("MCP9808 manufacturer ID: %#x" % manufacture_id)
        logging.info("MCP9808 device ID: %#x" % device_id)
        self.sample_timer = self.reactor.register_timer(self.sample_sensor)
        self.reactor.update_timer(self.sample_timer, self.reactor.NOW)

    def setup_minmax(self, min_temp, max_temp):
        self.min_temp = min_temp
        self.max_temp = max_temp

    def setup_callback(self, cb):
        self._callback = cb

    def sample_sensor(self, eventtime):
        self.reactor.pause(self.reactor.monotonic() + .1)
        recv = unpack_from(">H", self.get_measurement())[0]
        temp = (recv & 0x0FFF) / 16.0
        if recv & 0x1000:
            temp -= 256.0
        self.temp = temp
        measured_time = self.reactor.monotonic()
        self._callback(self.mcu.estimated_print_time(measured_time), self.temp)
        return measured_time + REPORT_TIME

    def get_measurement(self):
        register = [MCP9808_REG_AMBIENT_TEMP]
        recv = self.i2c.i2c_read(register, 2)
        return bytearray(recv['response'])

    def get_man_id(self):
        register = [MCP9808_REG_MANUF_ID]
        recv = self.i2c.i2c_read(register, 2)
        return bytearray(recv['response'])

    def get_dev_id(self):
        register = [MCP9808_REG_DEVICE_ID]
        recv = self.i2c.i2c_read(register, 2)
        return bytearray(recv['response'])

    def get_report_time_delta(self):
        return REPORT_TIME

    def get_status(self, eventtime):
        data = {
            'temperature': round(self.temp, 2)
        }
        return data


def load_config(config):
    logging.info("MCP9808 init")
    pheaters = config.get_printer().load_object(config, "heaters")
    pheaters.add_sensor_factory("MCP9808", MCP9808)

