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


class Blockchain:
    """
    The blockchain — a cryptographically linked list of blocks secured
    by proof-of-work.

    Attributes:
        chain (list[Block]):           Ordered list of mined blocks.
        difficulty (int):              PoW difficulty (leading zeros).
        pending_transactions (list):   Transactions waiting to be mined.
    """

    def __init__(self, difficulty=4):
        self.chain = []
        self.difficulty = difficulty
        self.pending_transactions = []

        # Mine the genesis block
        self.chain.append(self._create_genesis_block())

    def _create_genesis_block(self):
        """Create and mine the first block (index 0, previous_hash '0')."""
        genesis = Block(
            index=0,
            timestamp=time(),
            transactions=[{"type": "genesis", "message": "BlockVerify Genesis Block"}],
            previous_hash="0",
        )
        genesis.mine_block(self.difficulty)
        return genesis

    def get_latest_block(self):
        """Return the most recent block in the chain."""
        return self.chain[-1]

    def add_transaction(self, transaction):
        """
        Add a transaction dict to the pending pool.

        The transaction will be included in the next mined block.
        """
        self.pending_transactions.append(transaction)

    def mine_pending_transactions(self):
        """
        Create a new block from all pending transactions, mine it
        (proof-of-work), and append it to the chain.

        Returns:
            Block | None: The newly mined block, or None if the pool
                          was empty.
        """
        if not self.pending_transactions:
            return None

        new_block = Block(
            index=len(self.chain),
            timestamp=time(),
            transactions=self.pending_transactions.copy(),
            previous_hash=self.get_latest_block().hash,
        )

        start_time = time()
        attempts = new_block.mine_block(self.difficulty)
        mining_time = time() - start_time

        self.chain.append(new_block)
        self.pending_transactions = []

        # Attach mining metrics for the caller (not serialized by to_dict)
        new_block.mining_attempts = attempts
        new_block.mining_time = round(mining_time, 4)

        return new_block

    def is_chain_valid(self):
        """
        Walk the entire chain and verify integrity.

        Checks performed on every block (except genesis):
            1. Recalculated hash matches stored hash (tamper check).
            2. ``previous_hash`` matches the preceding block's hash (link check).
            3. Hash satisfies the difficulty requirement (PoW check).

        Genesis-specific checks:
            - index == 0
            - previous_hash == "0"

        Returns:
            dict: {"valid": bool, "errors": list[str]}
        """
        errors = []

        # --- Genesis checks ---
        genesis = self.chain[0]
        if genesis.index != 0:
            errors.append("Genesis block has wrong index")
        if genesis.previous_hash != "0":
            errors.append("Genesis block has wrong previous_hash")

        # --- Walk the rest of the chain ---
        for i in range(1, len(self.chain)):
            current = self.chain[i]
            previous = self.chain[i - 1]

            # Check 1 – hash integrity
            if current.hash != current.calculate_hash():
                errors.append(
                    f"Block {i}: Hash is invalid (block data was tampered)"
                )

            # Check 2 – chain link
            if current.previous_hash != previous.hash:
                errors.append(
                    f"Block {i}: previous_hash doesn't match previous block's hash"
                )

            # Check 3 – proof-of-work
            if not current.hash.startswith("0" * self.difficulty):
                errors.append(
                    f"Block {i}: Hash doesn't meet difficulty requirement"
                )

        return {"valid": len(errors) == 0, "errors": errors}

    def get_chain(self):
        """Return the full chain as a list of dicts."""
        return [block.to_dict() for block in self.chain]

    def get_stats(self):
        """Return high-level blockchain statistics."""
        return {
            "total_blocks": len(self.chain),
            "difficulty": self.difficulty,
            "pending_transactions": len(self.pending_transactions),
            "latest_block_hash": self.get_latest_block().hash,
        }
