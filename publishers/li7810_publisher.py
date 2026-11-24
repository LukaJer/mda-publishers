import json
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
        self._client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
        self._client.on_connect = self.on_connect
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
                return
            except Exception as e:
                self._logger.log(
                    f"Failed to connect to LI7810 at '{self._host}:{self._port}': {e}. Retrying in 5 seconds..."
                )
                self._try_post_log(f"ERROR: {e}")
                if self._stopping.wait(5.0):
                    return

    def measurement_routine(self) -> None:
        self._stopping.wait(1)

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
            self._logger.log(f"Failed to connect to instrument: {reason_code}")
        else:
            client.subscribe("licor/niobrara/output/concentration", qos=1)

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
            timestamp = datetime.fromtimestamp(
                payload['Concentration']['SECONDS'] + payload['Concentration']['NANOSECONDS'] / 1e9
            ) - self._gas_inlet_delay

            ch4 = GasMeasurement(
                datetime=timestamp,
                type='CH4-LI',
                concentration=payload['Concentration']['CH4'] / 1000,
                unit='ppm'
            )

            co2 = GasMeasurement(
                datetime=timestamp,
                type='CO2-LI',
                concentration=payload['Concentration']['CO2'],
                unit='ppm'
            )

            h2o = GasMeasurement(
                datetime=timestamp,
                type='H2O-LI',
                concentration=payload['Concentration']['H2O'],
                unit='ppm'
            )
            self._try_post_measurement_to_server(ch4)
            self._try_post_measurement_to_server(co2)
            self._try_post_measurement_to_server(h2o)
        except (UnicodeDecodeError, json.JSONDecodeError, KeyError, TypeError, ValueError) as e:
            self._logger.log(f"Received malformed message from LI7810: {e}")


if __name__ == "__main__":
    gas_logger = Logger('Gas')

    p = LI7810Publisher("tg10-01736.local", 1883, 10.2, gas_logger)
    p.start()
    time.sleep(5)
    p.stop()