BFT - Byzantine Fault Tolerant lib
==================================

Work in progress

Goal is to implement algorithm described in whitepaper <https://eprint.iacr.org/2016/199>, called "Honey Badger BFT".

It consists of multiple building blocks:
* treshold cryptography
* erasure coding (EC)
* reliable broadcast (RBC)
* binary agreement
* asynchronous common subset (ACS)

bftd
----

Idea for `bftd` program (or `blockchain`):

                     +-------------+
                     | blockchaind |
    stdin         -> | FD:0   FD:1 | -> stdout
    broadcast in  -> | FD:3   FD:5 | -> broadcast out
    initial state -> | FD:4        | -> final state
                     |             | -> messages
                     |
                     |            +----------------------------+
                     |            | <state transition command> |
                     | state   -> |                       FD:1 | -> new state
                     | peer    -> |                            | -> stdout
                     | message -> | FD:0
                     |            +--------------------------
                     +---------
