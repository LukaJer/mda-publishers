import json
import math
import queue
import time
from datetime import datetime, timedelta

import paho.mqtt.client as mqtt

from messages.gas_measurement_message import GasMeasurement
from publishers.base_publisher import BasePublisher
from publishers.logger import Logger


class LI7810Publisher(BasePublisher):
    def __init__(self,
                 host: str,
                 port: int,
                 gas_inlet_delay: float,
                 logger: Logger,
                 url: str = 'http://127.0.0.1:5000/measurement/gas'):
        super().__init__('LI7810', url, logger)
        self._host = host
        self._port = port
        self._gas_inlet_delay = timedelta(seconds=gas_inlet_delay)
        self._topic = "licor/niobrara/output/concentration"
        self._loop_started = False
        self._queue: queue.Queue = queue.Queue(maxsize=200)
        self._connected_once = False
        self._has_error = False
        self._error_message = ""
        self._client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
        self._client.on_connect = self.on_connect
        self._client.on_disconnect = self.on_disconnect
        self._client.on_subscribe = self.on_subscribe
        self._client.on_message = self.on_message
        self._client.on_unsubscribe = self.on_unsubscribe

    def start_up(self) -> None:
        self._try_post_log("Unconnected")
        while not self._stopping.is_set():
            try:
                self._client.connect(self._host, self._port)
                self._client.loop_start()
                self._loop_started = True
                self._has_error = False
                self._error_message = ""
                return
            except Exception as e:
                self._has_error = True
                self._error_message = f"ERROR: {e}"
                self._logger.log(
                    f"Failed to connect to LI7810 at '{self._host}:{self._port}': {e}. Retrying in 5 seconds..."
                )
                self._try_post_log(self._error_message)
                try:
                    self._client.disconnect()
                except Exception:
                    pass
                if self._stopping.wait(5.0):
                    return

    def measurement_routine(self) -> None:
        try:
            batch = self._queue.get(timeout=0.5)
        except queue.Empty:
            if not self._stopping.is_set():
                if self._has_error and self._error_message:
                    self._try_post_log(self._error_message)
                elif self._connected_once:
                    self._try_post_log("OK")
            return

        while True:
            if self._stopping.is_set():
                return
            self._try_post_measurements_batch(batch)
            self._has_error = False
            self._error_message = ""
            self._try_post_log("OK")
            try:
                batch = self._queue.get_nowait()
            except queue.Empty:
                break

    def shutdown(self) -> None:
        if self._loop_started:
            try:
                self._client.unsubscribe(self._topic)
            except Exception:
                pass
            try:
                self._client.disconnect()
            except Exception:
                pass
            try:
                self._client.loop_stop()
            except Exception:
                pass
            self._loop_started = False

    def on_connect(self, client, userdata, flags, reason_code, properties):
        if reason_code.is_failure:
            self._has_error = True
            self._error_message = f"ERROR: Failed to connect ({reason_code})"
            self._logger.log(f"Failed to connect to instrument: {reason_code}")
        else:
            self._connected_once = True
            self._has_error = False
            self._error_message = ""
            client.subscribe(self._topic, qos=1)

    def on_disconnect(self, client, userdata, disconnect_flags, reason_code, properties):
        if not self._stopping.is_set() and reason_code.is_failure:
            self._has_error = True
            self._error_message = f"ERROR: Disconnected ({reason_code})"
            self._logger.log(f"Disconnected from LI7810: {reason_code}")

    def on_subscribe(self, client, userdata, mid, reason_code_list, properties):
        if reason_code_list[0].is_failure:
            self._logger.log(f"Broker rejected you subscription: {reason_code_list[0]}")
        else:
            self._logger.log(f"Broker granted the following QoS: {reason_code_list[0].value}")

    def on_unsubscribe(self, client, userdata, mid, reason_code_list, properties):
        if len(reason_code_list) == 0 or not reason_code_list[0].is_failure:
            self._logger.log("Unsubscribe succeeded.")
        else:
            self._logger.log(f"Broker replied with failure: {reason_code_list[0]}")

    def on_message(self, client, userdata, msg: mqtt.MQTTMessage):
        try:
            payload = json.loads(msg.payload.decode("utf-8"))
            conc = payload['Concentration']
            seconds = float(conc['SECONDS'])
            nanoseconds = float(conc['NANOSECONDS'])
            ch4_conc = float(conc['CH4']) / 1000.0
            co2_conc = float(conc['CO2'])
            h2o_conc = float(conc['H2O'])

            if not all(math.isfinite(v) for v in (seconds, nanoseconds, ch4_conc, co2_conc, h2o_conc)):
                self._logger.log("Received non-finite values from LI7810; skipping message.")
                return

            timestamp = datetime.fromtimestamp(seconds + nanoseconds / 1e9) - self._gas_inlet_delay

            ch4 = GasMeasurement(
                datetime=timestamp,
                type='CH4-LI',
                concentration=ch4_conc,
                unit='ppm'
            )

            co2 = GasMeasurement(
                datetime=timestamp,
                type='CO2-LI',
                concentration=co2_conc,
                unit='ppm'
            )

            h2o = GasMeasurement(
                datetime=timestamp,
                type='H2O-LI',
                concentration=h2o_conc,
                unit='ppm'
            )
            batch = [ch4, co2, h2o]
            try:
                self._queue.put_nowait(batch)
            except queue.Full:
                try:
                    self._queue.get_nowait()
                except queue.Empty:
                    pass
                try:
                    self._queue.put_nowait(batch)
                except queue.Full:
                    pass
        except (UnicodeDecodeError, json.JSONDecodeError, KeyError, TypeError, ValueError, OverflowError, OSError) as e:
            self._logger.log(f"Received malformed message from LI7810: {e}")


if __name__ == "__main__":
    gas_logger = Logger('Gas')

    p = LI7810Publisher("tg10-01736.local", 1883, 10.2, gas_logger)
    p.start()
    time.sleep(5)
    p.stop()