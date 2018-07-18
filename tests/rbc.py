from unittest import TestCase
import hashlib

from bft.connection import MemoryConnection
from bft.rbc import RBCSender


class RBCTestCase(TestCase):
    def test_single_node(self):
        """Single node should be able to bradcast messages to itself."""
        loopback = MemoryConnection()
        node_name = 'the one'
        rbc = RBCSender(
            sender=node_name,
            connections={node_name: loopback},
            hash_function=lambda d: hashlib.sha512(d).digest(),
        )

        rbc.send(b'A message I\'d like to broadcast.')
        rbc.send(b'Thank you for cooperation.')
        output = []
        while loopback.size > 0:
            d = rbc.feed(node_name, loopback.receive())
            if d is not None:
                output.append(d)

        self.assertEqual(len(output), 2)
        self.assertIn(b'A message I\'d like to broadcast.', output)
        self.assertIn(b'Thank you for cooperation.', output)
