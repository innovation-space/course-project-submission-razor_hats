"""
BlockVerify Custom Blockchain Implementation
=============================================

A custom blockchain built from scratch to demonstrate deep understanding
of blockchain fundamentals: cryptographic hashing, proof-of-work consensus,
chain linking, and tamper-proof validation.

Author: razor_hats team
"""

import hashlib
import json
from time import time


class Block:
    """
    A single block in the blockchain.

    Each block contains:
        - index:          Position in the chain (0 = genesis)
        - timestamp:      Unix epoch when the block was created
        - transactions:   List of transaction dicts stored in this block
        - previous_hash:  SHA-256 hash of the previous block (chain link)
        - nonce:          Counter incremented during proof-of-work mining
        - hash:           SHA-256 hash of this block's contents
    """

    def __init__(self, index, timestamp, transactions, previous_hash, nonce=0):
        self.index = index
        self.timestamp = timestamp
        self.transactions = transactions
        self.previous_hash = previous_hash
        self.nonce = nonce
        self.hash = self.calculate_hash()

    def calculate_hash(self):
        """
        Compute the SHA-256 hash of the block's contents.

        The hash covers index, timestamp, transactions, previous_hash,
        and nonce. Changing ANY field produces a completely different hash
        (avalanche effect), which is the foundation of tamper detection.

        Returns:
            str: 64-character hexadecimal hash string.
        """
        block_string = json.dumps(
            {
                "index": self.index,
                "timestamp": self.timestamp,
                "transactions": self.transactions,
                "previous_hash": self.previous_hash,
                "nonce": self.nonce,
            },
            sort_keys=True,
        )
        return hashlib.sha256(block_string.encode()).hexdigest()

    def mine_block(self, difficulty):
        """
        Perform proof-of-work mining.

        Repeatedly increments the nonce and recalculates the hash until
        the hash starts with ``difficulty`` leading zeros.

        Example:
            difficulty = 4  →  hash must start with "0000"

        Args:
            difficulty (int): Number of leading zeros required.

        Returns:
            int: Total number of hash attempts (mining work done).
        """
        target = "0" * difficulty
        attempts = 0

        while self.hash[:difficulty] != target:
            self.nonce += 1
            self.hash = self.calculate_hash()
            attempts += 1

        return attempts

    def to_dict(self):
        """Serialize the block to a JSON-friendly dictionary."""
        return {
            "index": self.index,
            "timestamp": self.timestamp,
            "transactions": self.transactions,
            "previous_hash": self.previous_hash,
            "nonce": self.nonce,
            "hash": self.hash,
        }
