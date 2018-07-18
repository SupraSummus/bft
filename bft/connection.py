class WriteConnection:
    """Writing end of reliable, ordered, message stream."""
    def send(self, message):
        raise NotImplementedError()


class ReadConnection:
    """Reading end of reliable, ordered, message stream."""
    def receive(self):
        raise NotImplementedError()


class MemoryConnection(WriteConnection, ReadConnection):
    def __init__(self):
        self._buffer = []

    def send(self, message):
        self._buffer.append(message)

    def receive(self):
        return self._buffer.pop(0)

    @property
    def size(self):
        return len(self._buffer)
