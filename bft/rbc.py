from collections import namedtuple
import struct
import logging

from reedsolo import RSCodec

from .utils import max_corrupted_peers


logger = logging.getLogger(__name__)


def encode_ec_blocks(data, min_needed_to_decode, total_blocks):
    with_ec = RSCodec(
        nsym=total_blocks - min_needed_to_decode,
        nsize=total_blocks,
    ).encode(data)
    # split encoded data between blocks
    return [
        data[i::total_blocks]
        for i in range(total_blocks)
    ]


def decode_ec_blocks(blocks, min_needed_to_decode):
    n = len(blocks)
    block_size = max([
        len(b)
        for b in blocks
        if b is not None
    ])

    # gather whole bytestring and missing positions
    data = bytearray(block_size * min_needed_to_decode)
    missing = set()
    for i, b in enumerate(blocks):
        if b is None:
            missing.update(range(i, len(data), n))
        else:
            data[i::n] = b

    # if no redundancy is added skip reedsolo (it has a bug)
    # https://github.com/tomerfiliba/reedsolomon/issues/13
    if n - min_needed_to_decode == 0:
        assert len(missing) == 0
        return data

    # feed into Reed-Solomon decoder
    return RSCodec(
        nsym=n - min_needed_to_decode,  # number of extra bytes per chunk
        nsize=n,  # encoded chunk size
    ).decode(data, erase_pos=missing)


class _RBCMessage(namedtuple(
    '_RBCMessage',
    ('type', 'root_hash', 'block_hashes', 'block_number', 'block'),
)):
    binary_format = ('!'  # network order
        'B'  # message type
        'H'  # number of blocks
        'H'  # block number
        'H'  # hash size
    )
    # + root hash
    # + n * block hash
    # + block data to the end of buffer
    
    def encode(self):
        header = struct.pack(
            self.binary_format,
            self.type,
            len(self.block_hashes),
            self.block_number,
            len(self.root_hash),
        )
        return b''.join([
            header,
            self.root_hash,
            *self.block_hashes,
            self.block,
        ])

    @classmethod
    def decode(cls, data):
        header_size = struct.calcsize(cls.binary_format)
        t, block_count, block_number, hash_size = struct.unpack(
            cls.binary_format,
            data[:header_size],
        )
        root_hash, *block_hashes = [
            data[header_size + n*hash_size:header_size + n*hash_size + hash_size]
            for n in range(block_count + 1)
        ]
        block = data[header_size + hash_size + block_count * hash_size:]
        return cls(
            type=t,
            root_hash=root_hash,
            block_hashes=block_hashes,
            block_number=block_number,
            block=block,
        )


class _RBCRound:
    """Signle RBC transmitted value, at different stages of completion

    This class is rather for internal use.
    """

    def __init__(self, block_hashes, hash_function):
        self.hash_function = hash_function

        self.block_hashes = block_hashes
        self.blocks = [None for _ in block_hashes]
        self.block_count = 0

        self.ready_sent = False
        self.ready_received = set()

    @property
    def root_hash(self):
        return self.hash_function(b''.join(self.block_hashes))

    @property
    def data(self):
        n = len(self.block_hashes)
        f = max_corrupted_peers(n)
        original_data = decode_ec_blocks(self.blocks, n - 2*f)
        blocks = encode_ec_blocks(original_data, n - 2*f, n)
        block_hashes = list(map(self.hash_function, blocks))
        if block_hashes == self.block_hashes:
            return original_data
        else:
            return None

    def feed_block(self, block_number, block):
        if self.blocks[block_number] is None:
            self.blocks[block_number] = block
            self.block_count += 1


class RBC:
    """Reliable broadcast"""

    # message types
    VALUE = 0
    ECHO = 1
    READY = 2

    def __init__(self, sender, connections, hash_function, **kwargs):
        super().__init__(**kwargs)
        self.sender = sender
        self.connections = connections
        self.hash_function = hash_function

        # dict sequential number -> peer
        self.peer_numbers = {
            peer: i
            for i, peer in enumerate(sorted(connections.keys()))
        }

        # root hash -> RBC round
        self.rounds = {}

    def feed(self, peer, message_data):
        message = _RBCMessage.decode(message_data)
        if message is None:
            return None

        n = len(self.connections)
        f = max_corrupted_peers(n)

        if message.type == RBC.VALUE:
            if peer != self.sender:
                logger.info("got VALUE from non-sender peer %s", peer)
                return None

            self._multicast(_RBCMessage(
                RBC.ECHO,
                message.root_hash,
                message.block_hashes,
                message.block_number,
                message.block,
            ).encode())

        elif message.type == RBC.ECHO:
            # validate the message
            if message.block_number != self.peer_numbers[peer]:
                logger.info("got ECHO with block number mismatch from peer %s", peer)
                return None
            if self.hash_function(message.block) != message.block_hashes[message.block_number]:
                return None
            if self.hash_function(b''.join(message.block_hashes)) != message.root_hash:
                return None

            # register block data
            rbc_round = self.rounds.setdefault(
                message.root_hash,
                _RBCRound(message.block_hashes, hash_function=self.hash_function),
            )
            rbc_round.feed_block(message.block_number, message.block)

            # got enough ECHOes to multicast READY
            if rbc_round.block_count == n - f:
                original_data = rbc_round.data
                if rbc_round.data is not None:
                    if not rbc_round.ready_sent:
                        rbc_round.ready_sent = True
                        self._multicast(_RBCMessage(
                            type=RBC.READY,
                            root_hash=message.root_hash,
                            block_hashes=[],
                            block_number=0,
                            block=bytes(),
                        ).encode())
                else:
                    logger.warning("couldnt decode data in round %s", message.root_hash)

            # got enough ECHOes and READYs to output a value
            if rbc_round.block_count == n - 2*f and len(rbc_round.ready_received) >= 2*f + 1:
                return rbc_round.data

        elif message.type == RBC.READY:
            rbc_round = self.rounds.get(message.root_hash)
            if rbc_round is None:
                return None
            rbc_round.ready_received.add(peer)

            # got enough READYs to multicast ready
            if len(rbc_round.ready_received) == f + 1 and not rbc_round.ready_sent:
                rbc_round.ready_sent = True
                self._multicast(_RBCMessage(
                    type=RBC.READY,
                    root_hash=message.root_hash,
                    block_hashes=[],
                    block_number=0,
                    block=bytes(),
                ).encode())

            # got enough ECHOes and READYs to output a value
            if rbc_round.block_count >= n - 2*f and len(rbc_round.ready_received) == 2*f + 1:
                return rbc_round.data

        else:
            logger.info("got malformed message from peer %s", peer)

    def _multicast(self, message):
        for c in self.connections.values():
            c.send(message)

class RBCSender(RBC):

    def send(self, data):
        n = len(self.connections)
        f = max_corrupted_peers(n)
        blocks = encode_ec_blocks(data, n - 2*f, n)
        block_hashes = list(map(self.hash_function, blocks))
        root_hash = self.hash_function(b''.join(block_hashes))

        for peer, connection in self.connections.items():
            i = self.peer_numbers[peer]
            connection.send(_RBCMessage(
                type=RBC.VALUE,
                root_hash=root_hash,
                block_hashes=block_hashes,
                block_number=i,
                block=blocks[i],
            ).encode())
