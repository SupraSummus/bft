from unittest import TestCase
import hashlib

from bft.connection import MemoryConnection
from bft.rbc import RBC, RBCSender


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
        while loopback.size > 0:
            d = rbc.feed(node_name, loopback.receive())

        output = rbc.output_stream.read_all()
        self.assertEqual(len(output), 2)
        self.assertIn(b'A message I\'d like to broadcast.', output)
        self.assertIn(b'Thank you for cooperation.', output)

    def test_n4_f1(self):
        connections = {
            (start, end): MemoryConnection()
            for start in range(4)
            for end in range(4)
        }
        def conns(peer):
            return {
                end: c
                for (start, end), c in connections.items()
                if start == peer
            }

        class RBCFailed(RBC):
            """Failed RBC peer - it just does nothing"""
            def feed(self, peer, data):
                pass

        rbc_common_args = {
            'sender': 0,
            'hash_function': lambda d: hashlib.sha512(d).digest(),
        }
        rbcs = {
            0: RBCSender(connections=conns(0), **rbc_common_args),
            1: RBC(connections=conns(1), **rbc_common_args),
            2: RBC(connections=conns(2), **rbc_common_args),
            3: RBCFailed(connections=conns(3), **rbc_common_args),  # this is the corrupted peer
        }

        rbcs[0].send(b'A message I\'d like to broadcast.')
        while True:
            traffic = False
            for (f, t), c in connections.items():
                if c.size > 0:
                    traffic = True
                    rbcs[t].feed(f, c.receive())
            if not traffic:
                break

        for peer in range(3):
            self.assertEqual(
                rbcs[peer].output_stream.read_all(),
                [b'A message I\'d like to broadcast.'],
            )
