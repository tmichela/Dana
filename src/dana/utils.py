import json


class CachedStore(dict):
    def __init__(self, client, key):
        super().__init__()
        self._client = client
        self._key = key

        reply = client.get_storage({'keys': [key]})
        if reply['msg'] == 'Key does not exist.':
            pass
        elif reply['result'] == 'success':
            data = json.loads(reply['storage'][key])
            self.init_data(data)
        else:
            raise RuntimeError(reply['msg'])

    def init_data(self, data):
        self.update(data)

    def commit(self):
        self._client.update_storage({
            'storage': {self._key: json.dumps(self, default=str)}})
