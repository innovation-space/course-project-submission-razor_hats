"""
BlockVerify — Algorand Integration Tests
=========================================
Verifies that the Algorand client module loads correctly
and that the TEAL smart contract source files are valid.

NOTE: All Algorand network calls are mocked in test_api.py.
      These tests validate the local contract/wallet setup only.
"""

import os
import json
import pytest

# ── Path helpers ───────────────────────────────────────────────────────
BACKEND_DIR  = os.path.dirname(os.path.dirname(__file__))
DATA_DIR     = os.path.join(BACKEND_DIR, "data")
TEAL_DIR     = BACKEND_DIR


class TestAlgorandSetup:
    """Verify Algorand-related files and modules load correctly."""

    def test_approval_teal_exists(self):
        """The TEAL approval program file must exist."""
        path = os.path.join(TEAL_DIR, "approval.teal")
        assert os.path.isfile(path), "approval.teal not found"

    def test_clear_teal_exists(self):
        """The TEAL clear state program file must exist."""
        path = os.path.join(TEAL_DIR, "clear.teal")
        assert os.path.isfile(path), "clear.teal not found"

    def test_approval_teal_has_pragma(self):
        """The approval program must start with a valid TEAL pragma."""
        with open(os.path.join(TEAL_DIR, "approval.teal")) as f:
            first_line = f.readline().strip()
        assert first_line.startswith("#pragma version"), \
            f"Expected '#pragma version ...' but got: {first_line}"

    def test_approval_teal_contains_register(self):
        """The approval program must contain the 'register' method selector."""
        with open(os.path.join(TEAL_DIR, "approval.teal")) as f:
            content = f.read()
        assert 'byte "register"' in content, \
            "approval.teal missing 'register' method"

    def test_approval_teal_contains_app_global_put(self):
        """The approval program must write to global state."""
        with open(os.path.join(TEAL_DIR, "approval.teal")) as f:
            content = f.read()
        assert "app_global_put" in content, \
            "approval.teal missing app_global_put instruction"

    def test_clear_teal_approves(self):
        """The clear program must contain 'int 1 / return' to approve."""
        with open(os.path.join(TEAL_DIR, "clear.teal")) as f:
            content = f.read()
        assert "int 1" in content and "return" in content, \
            "clear.teal must contain 'int 1' and 'return'"

    def test_contract_module_loads(self):
        """The contract module must import without errors."""
        import contract  # noqa: F401

    def test_algorand_client_module_loads(self):
        """The algorand_client module must import without errors."""
        import algorand_client  # noqa: F401

    def test_wallet_file_format(self):
        """If a wallet file exists, it must have address and private_key."""
        wallet_path = os.path.join(DATA_DIR, "algo_wallet.json")
        if not os.path.exists(wallet_path):
            pytest.skip("No wallet file yet (first run)")
        with open(wallet_path) as f:
            data = json.load(f)
        assert "address" in data, "Wallet missing 'address'"
        assert "private_key" in data, "Wallet missing 'private_key'"
        assert len(data["address"]) == 58, "Algorand address must be 58 chars"
