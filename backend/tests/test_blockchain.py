"""
Tests for the custom blockchain core (Block and Blockchain classes).

Run:
    pytest backend/tests/test_blockchain.py -v
"""

import pytest
import sys
import os
from time import time

# Ensure backend is on the import path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from blockchain import Block, Blockchain


# ═══════════════════════════════════════════════════════════════════
#  Block Tests
# ═══════════════════════════════════════════════════════════════════


class TestBlock:
    """Unit tests for the Block class."""

    def test_block_creation(self):
        """Block should store all provided attributes."""
        ts = time()
        b = Block(index=1, timestamp=ts, transactions=[{"a": 1}], previous_hash="abc")
        assert b.index == 1
        assert b.timestamp == ts
        assert b.transactions == [{"a": 1}]
        assert b.previous_hash == "abc"
        assert b.nonce == 0

    def test_hash_is_computed_on_creation(self):
        """Hash must be a 64-char hex string assigned at construction."""
        b = Block(0, time(), [], "0")
        assert isinstance(b.hash, str)
        assert len(b.hash) == 64

    def test_hash_is_deterministic(self):
        """Recalculating the hash with unchanged data must return the same value."""
        b = Block(1, 1234567890.0, [{"x": 1}], "prev")
        assert b.hash == b.calculate_hash()

    def test_hash_changes_when_data_changes(self):
        """Modifying any field must change the hash (avalanche effect)."""
        b = Block(1, 1234567890.0, [{"x": 1}], "prev")
        original = b.hash

        b.transactions = [{"x": 2}]
        assert b.calculate_hash() != original

    def test_hash_changes_with_nonce(self):
        """Different nonce values must produce different hashes."""
        b = Block(1, 1234567890.0, [], "0")
        h0 = b.calculate_hash()
        b.nonce = 999
        h1 = b.calculate_hash()
        assert h0 != h1

    def test_proof_of_work_meets_difficulty(self):
        """After mining, the hash must start with `difficulty` zeros."""
        b = Block(1, time(), [{"test": True}], "0")
        difficulty = 2
        b.mine_block(difficulty)
        assert b.hash.startswith("0" * difficulty)

    def test_proof_of_work_increments_nonce(self):
        """Mining must increment the nonce at least once."""
        b = Block(1, time(), [], "0")
        b.mine_block(2)
        assert b.nonce > 0

    def test_proof_of_work_returns_attempts(self):
        """mine_block should return the number of hash attempts."""
        b = Block(1, time(), [], "0")
        attempts = b.mine_block(2)
        assert isinstance(attempts, int)
        assert attempts >= 1

    def test_higher_difficulty_requires_more_work(self):
        """Higher difficulty should generally require more attempts."""
        b_easy = Block(1, time(), [{"d": "easy"}], "0")
        attempts_easy = b_easy.mine_block(1)

        b_hard = Block(1, time(), [{"d": "hard"}], "0")
        attempts_hard = b_hard.mine_block(3)

        # Not guaranteed every single time but overwhelmingly likely
        assert attempts_hard >= attempts_easy

    def test_to_dict_returns_all_fields(self):
        """to_dict must include every block attribute."""
        b = Block(2, 100.0, [{"t": 1}], "prev_hash")
        d = b.to_dict()
        assert d["index"] == 2
        assert d["timestamp"] == 100.0
        assert d["transactions"] == [{"t": 1}]
        assert d["previous_hash"] == "prev_hash"
        assert "nonce" in d
        assert "hash" in d

    def test_to_dict_is_json_serializable(self):
        """to_dict output must survive a JSON round-trip."""
        import json
        b = Block(0, time(), [{"key": "value"}], "0")
        json.dumps(b.to_dict())  # Should not raise
