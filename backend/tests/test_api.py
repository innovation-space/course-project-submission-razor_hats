"""
Tests for the Flask REST API endpoints.

Run:
    pytest backend/tests/test_api.py -v
"""

import pytest
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app import app, blockchain, models_registry, verification_logs


# Reset all state before each test so tests don't interfere with each other
@pytest.fixture(autouse=True)
def reset_state():
    """Reset the blockchain and registries before each test."""
    blockchain.chain = [blockchain._create_genesis_block()]
    blockchain.pending_transactions = []
    models_registry.clear()
    verification_logs.clear()
    yield


# Flask test client fixture
@pytest.fixture
def client():
    app.config["TESTING"] = True
    with app.test_client() as c:
        yield c


# Helper – register a model and return the parsed JSON
def _register(client, name="TestModel", hash_val="abc123", owner="alice", metadata=""):
    return client.post(
        "/api/register",
        json={"modelName": name, "modelHash": hash_val, "metadata": metadata, "owner": owner},
    )


# ═══════════════════════════════════════════════════════════════════
#  /api/register
# ═══════════════════════════════════════════════════════════════════


class TestRegister:

    def test_register_success(self, client):
        resp = _register(client)
        data = resp.get_json()
        assert resp.status_code == 200
        assert data["success"] is True
        assert "modelId" in data
        assert "blockIndex" in data

    def test_register_missing_name(self, client):
        resp = client.post("/api/register", json={"modelHash": "abc", "owner": "alice"})
        assert resp.status_code == 400
        assert resp.get_json()["success"] is False

    def test_register_missing_hash(self, client):
        resp = client.post("/api/register", json={"modelName": "M", "owner": "alice"})
        assert resp.status_code == 400

    def test_register_missing_owner(self, client):
        resp = client.post("/api/register", json={"modelName": "M", "modelHash": "h"})
        assert resp.status_code == 400

    def test_register_creates_block(self, client):
        before = len(blockchain.chain)
        _register(client)
        assert len(blockchain.chain) == before + 1

    def test_register_stores_in_registry(self, client):
        data = _register(client).get_json()
        assert data["modelId"] in models_registry

    def test_register_initial_version_is_one(self, client):
        data = _register(client).get_json()
        model = models_registry[data["modelId"]]
        assert model["currentVersion"] == 1
        assert len(model["versions"]) == 1
