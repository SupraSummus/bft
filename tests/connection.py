from unittest import TestCase

from bft.connection import MemoryConnection


class MemoryConnectionTestCase(TestCase):
    def setUp(self):
        self.connection = MemoryConnection()

    def test_write_read(self):
        self.connection.send(b'aaa')
        self.connection.send(b'bbb')
        self.assertEqual(self.connection.receive(), b'aaa')
        self.assertEqual(self.connection.receive(), b'bbb')

    def test_read_empty(self):
        self.assertRaises(
            Exception,
            self.connection.receive,
        )
