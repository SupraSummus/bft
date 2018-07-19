from reedsolo import RSCodec


class ErasureCoding:

    def __init__(self, payload_size, encoded_size):
        """Data can be decoded after loosing up to `encoded_size - payload_size` blocks."""
        assert payload_size <= encoded_size
        self.payload_size = payload_size
        self.encoded_size = encoded_size

    def encode(self, data):
        """Should return list of bytestrings."""
        raise NotImplementedError()

    def decode(self, blocks):
        """Takes list of blocks (lost are set to Nones) and returns recustructed message."""
        raise NotImplementedError()


class PatchedRSCodec(RSCodec):
    def decode(self, data, erase_pos, only_erasures):
        if self.nsym == 0:
            # if no redundancy is added skip reedsolo (it has a bug)
            # https://github.com/tomerfiliba/reedsolomon/issues/13
            assert len(erase_pos) == 0
            assert only_erasures
            return (data, b'')
        else:
            return super().decode(
                data,
                erase_pos=erase_pos, only_erasures=only_erasures,
            )


class RSErasureCoding(ErasureCoding):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.codec = PatchedRSCodec(
            nsym=self.encoded_size - self.payload_size,
            nsize=self.encoded_size,
        )

    def encode(self, data):
        assert len(data) % self.payload_size == 0
        parts = [
            self.codec.encode(data[off:off + self.payload_size])
            for off in range(0, len(data), self.payload_size)
        ]
        # transpose parts to split redundant bits between blocks
        return [bytes(b) for b in zip(*parts)]

    def decode(self, blocks):
        assert len(blocks) == self.encoded_size
        block_size = None
        for b in blocks:
            if b is not None:
                if block_size is None:
                    block_size = len(b)
                else:
                    assert block_size == len(b)
        assert block_size is not None

        parts = []
        for off in range(block_size):
            part = bytes(
                block[off] if block is not None else 0
                for block in blocks
            )
            # `i + 1` is because of reedsolo bug
            # https://github.com/lrq3000/reedsolomon/issues/3
            missing = set(
                i
                for i, block in enumerate(blocks)
                if block is None
            )
            parts.append(self.codec.decode(part, erase_pos=missing, only_erasures=True)[0])

        return b''.join(parts)
