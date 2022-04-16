import time
import etcd3
from threading import Timer
import json


STORE_DELAY_SECONDS_KEY = 'store_delay_seconds'
DEFAULT_STATE_STORE_DELAY_SECONDS = 300

def dict_store_delay_seconds(d):
    if STORE_DELAY_SECONDS_KEY in d:
        return d[STORE_DELAY_SECONDS_KEY]

    return DEFAULT_STATE_STORE_DELAY_SECONDS


class EtcdBackedState:
    def __init__(self, etcd_path):
        self._etcd = etcd3.Etcd3Client(
            host="192.168.0.11",
            port=2379,
            ca_cert="/etc/cheesecave/ca.pem",
            cert_key="/etc/cheesecave/client-key.pem",
            cert_cert="/etc/cheesecave/client.pem",
        )
        self._etcd_path = etcd_path

        stored_state, _ = self._etcd.get(self._etcd_path)

        if stored_state is None:
            self.state = self.default_state()
        else:
            self.state = json.loads(stored_state)

        self._store_state_timer = None
        self._store_state()
        self._watch_state()

    def __getattr__(self, name):
        # This is needed when the object is in `__init__` to avoid a recursion loop before the `state` attribute is set.
        if name == 'state':
            return None

        return self.state[name]

    def __setattr__(self, name, value):
        if self.state is not None and name in self.state:
            self.state[name] = value
        else:
            super().__setattr__(name, value)

    def default_state(self):
        raise NotImplementedError()

    def state_changed(self):
        pass

    @property
    def _store_delay_seconds(self):
        return dict_store_delay_seconds(self.state)

    def _store_state(self):
        state_serialized = json.dumps(self.state)
        self._etcd.put(self._etcd_path, state_serialized)

        self._start_store_state_timer()

    def _start_store_state_timer(self):
        self._store_state_timer = Timer(
            self._store_delay_seconds, self._store_state)
        self._store_state_timer.start()

    def _watch_state(self):
        self._etcd.add_watch_callback(key=self._etcd_path, callback=self.watch_callback)

    def watch_callback(self, response):
        for e in response.events:
            if isinstance(e, etcd3.events.PutEvent) and e.key == self._etcd_path:
                watched_value = json.loads(e.value)
                if watched_value == self.state:
                    continue

                # Special casing for when the store delay changes.
                if dict_store_delay_seconds(watched_value) != self._store_delay_seconds:
                    self._store_state_timer.cancel()
                    self._start_store_state_timer()

                self.state = watched_value
                self.state_changed()
