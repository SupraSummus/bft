from unittest import TestCase

from bft.ec import RSErasureCoding


class ECTestCase(TestCase):
    def test_2_of_5_lost(self):
        c = RSErasureCoding(3, 5)
        blocks = c.encode(b'012345678')
        self.assertEqual(len(blocks), 5)
        blocks[0] = None
        blocks[1] = None
        self.assertEqual(
            c.decode(blocks),
            b'012345678',
        )
