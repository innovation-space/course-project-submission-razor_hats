"""
Tests for the Flask REST API endpoints.

Run:
    pytest backend/tests/test_api.py -v
"""

import pytest
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app import app, blockchain, models_registry, verification_logs, _rate_log


# Reset all state before each test so tests don't interfere with each other
@pytest.fixture(autouse=True)
def reset_state():
    """Reset the blockchain, registries, and rate-limit log before each test."""
    blockchain.chain = [blockchain._create_genesis_block()]
    blockchain.pending_transactions = []
    models_registry.clear()
    verification_logs.clear()
    _rate_log.clear()
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


# ═══════════════════════════════════════════════════════════════════
#  /api/verify
# ═══════════════════════════════════════════════════════════════════


class TestVerify:

    def test_verify_valid(self, client):
        # Register first, then verify with the exact same hash — should pass
        model_id = _register(client, hash_val="correct").get_json()["modelId"]
        resp = client.post(
            "/api/verify",
            json={"modelId": model_id, "providedHash": "correct", "verifier": "bob"},
        )
        data = resp.get_json()
        assert resp.status_code == 200
        assert data["isValid"] is True

    def test_verify_invalid(self, client):
        # Provide a wrong hash — integrity check should fail
        model_id = _register(client, hash_val="correct").get_json()["modelId"]
        resp = client.post(
            "/api/verify",
            json={"modelId": model_id, "providedHash": "WRONG", "verifier": "bob"},
        )
        data = resp.get_json()
        assert data["isValid"] is False

    def test_verify_nonexistent_model(self, client):
        resp = client.post(
            "/api/verify",
            json={"modelId": "ghost", "providedHash": "h", "verifier": "bob"},
        )
        assert resp.status_code == 404

    def test_verify_missing_model_id(self, client):
        resp = client.post("/api/verify", json={"providedHash": "h"})
        assert resp.status_code == 400

    def test_verify_missing_hash(self, client):
        resp = client.post("/api/verify", json={"modelId": "x"})
        assert resp.status_code == 400

    def test_verify_creates_block(self, client):
        # Each verification should mine a new block
        model_id = _register(client).get_json()["modelId"]
        before = len(blockchain.chain)
        client.post("/api/verify", json={"modelId": model_id, "providedHash": "abc123"})
        assert len(blockchain.chain) == before + 1

    def test_verify_logged_in_audit(self, client):
        # Verification result should be saved to the audit log
        model_id = _register(client).get_json()["modelId"]
        client.post(
            "/api/verify",
            json={"modelId": model_id, "providedHash": "abc123", "verifier": "carol"},
        )
        assert len(verification_logs[model_id]) == 1
        assert verification_logs[model_id][0]["verifier"] == "carol"


# ═══════════════════════════════════════════════════════════════════
#  /api/add-version
# ═══════════════════════════════════════════════════════════════════


class TestAddVersion:

    def test_add_version_success(self, client):
        model_id = _register(client, owner="alice").get_json()["modelId"]
        resp = client.post(
            "/api/add-version",
            json={"modelId": model_id, "newHash": "v2hash", "changelog": "fix bug", "owner": "alice"},
        )
        data = resp.get_json()
        assert resp.status_code == 200
        assert data["version"] == 2

    def test_add_version_wrong_owner(self, client):
        # Only the original owner should be allowed to add versions
        model_id = _register(client, owner="alice").get_json()["modelId"]
        resp = client.post(
            "/api/add-version",
            json={"modelId": model_id, "newHash": "v2", "changelog": "c", "owner": "mallory"},
        )
        assert resp.status_code == 403

    def test_add_version_updates_hash(self, client):
        # After adding a version, the model's stored hash should be the new one
        model_id = _register(client, hash_val="old", owner="alice").get_json()["modelId"]
        client.post(
            "/api/add-version",
            json={"modelId": model_id, "newHash": "new", "changelog": "c", "owner": "alice"},
        )
        assert models_registry[model_id]["modelHash"] == "new"

    def test_add_version_not_found(self, client):
        resp = client.post(
            "/api/add-version",
            json={"modelId": "nope", "newHash": "h", "changelog": "c", "owner": "a"},
        )
        assert resp.status_code == 404


# ═══════════════════════════════════════════════════════════════════
#  READ endpoints
# ═══════════════════════════════════════════════════════════════════


class TestReadEndpoints:

    def test_get_models_by_owner(self, client):
        _register(client, name="M1", owner="alice")
        _register(client, name="M2", owner="alice")
        _register(client, name="M3", owner="bob")

        resp = client.get("/api/models/alice")
        data = resp.get_json()
        assert data["count"] == 2

    def test_get_models_empty(self, client):
        resp = client.get("/api/models/nobody")
        assert resp.get_json()["count"] == 0

    def test_get_model_detail(self, client):
        model_id = _register(client, name="Detail").get_json()["modelId"]
        resp = client.get(f"/api/model/{model_id}")
        data = resp.get_json()
        assert data["success"] is True
        assert data["model"]["modelName"] == "Detail"

    def test_get_model_not_found(self, client):
        assert client.get("/api/model/ghost").status_code == 404

    def test_get_versions(self, client):
        model_id = _register(client, owner="alice").get_json()["modelId"]
        client.post(
            "/api/add-version",
            json={"modelId": model_id, "newHash": "v2", "changelog": "v2 log", "owner": "alice"},
        )
        resp = client.get(f"/api/versions/{model_id}")
        data = resp.get_json()
        assert data["currentVersion"] == 2
        assert len(data["versions"]) == 2

    def test_get_audit_log(self, client):
        model_id = _register(client).get_json()["modelId"]
        client.post("/api/verify", json={"modelId": model_id, "providedHash": "abc123", "verifier": "v"})
        client.post("/api/verify", json={"modelId": model_id, "providedHash": "wrong", "verifier": "v"})

        resp = client.get(f"/api/audit/{model_id}")
        data = resp.get_json()
        assert data["count"] == 2

    def test_get_audit_not_found(self, client):
        assert client.get("/api/audit/ghost").status_code == 404


# ═══════════════════════════════════════════════════════════════════
#  Chain endpoints
# ═══════════════════════════════════════════════════════════════════


class TestChainEndpoints:

    def test_get_chain(self, client):
        resp = client.get("/api/chain")
        data = resp.get_json()
        assert data["success"] is True
        assert data["length"] >= 1

    def test_get_chain_grows_after_register(self, client):
        # Each registration mines a block, so chain length should increase
        before = client.get("/api/chain").get_json()["length"]
        _register(client)
        after = client.get("/api/chain").get_json()["length"]
        assert after == before + 1

    def test_validate_chain_valid(self, client):
        _register(client)
        resp = client.get("/api/chain/validate")
        data = resp.get_json()
        assert data["isValid"] is True

    def test_get_stats(self, client):
        _register(client)
        resp = client.get("/api/stats")
        data = resp.get_json()
        assert data["totalModels"] == 1
        assert data["totalBlocks"] >= 2

    def test_stats_count_verifications(self, client):
        model_id = _register(client).get_json()["modelId"]
        client.post("/api/verify", json={"modelId": model_id, "providedHash": "abc123"})
        data = client.get("/api/stats").get_json()
        assert data["totalVerifications"] == 1


# ═══════════════════════════════════════════════════════════════════
#  /api/deactivate
# ═══════════════════════════════════════════════════════════════════


class TestDeactivate:

    def test_deactivate_success(self, client):
        model_id = _register(client, owner="alice").get_json()["modelId"]
        resp = client.post("/api/deactivate", json={"modelId": model_id, "owner": "alice"})
        assert resp.status_code == 200
        assert resp.get_json()["success"] is True

    def test_deactivate_wrong_owner(self, client):
        # A different user should not be allowed to deactivate someone else's model
        model_id = _register(client, owner="alice").get_json()["modelId"]
        resp = client.post("/api/deactivate", json={"modelId": model_id, "owner": "mallory"})
        assert resp.status_code == 403

    def test_deactivate_not_found(self, client):
        resp = client.post("/api/deactivate", json={"modelId": "ghost", "owner": "alice"})
        assert resp.status_code == 404

    def test_verify_deactivated_model_fails(self, client):
        # Once deactivated, the model should no longer be verifiable
        model_id = _register(client, owner="alice").get_json()["modelId"]
        client.post("/api/deactivate", json={"modelId": model_id, "owner": "alice"})
        resp = client.post("/api/verify", json={"modelId": model_id, "providedHash": "abc123", "verifier": "bob"})
        assert resp.status_code == 400

    def test_add_version_deactivated_fails(self, client):
        # A deactivated model should also block new version uploads
        model_id = _register(client, owner="alice").get_json()["modelId"]
        client.post("/api/deactivate", json={"modelId": model_id, "owner": "alice"})
        resp = client.post("/api/add-version", json={"modelId": model_id, "newHash": "h", "changelog": "c", "owner": "alice"})
        assert resp.status_code == 400


# ═══════════════════════════════════════════════════════════════════
#  Edge cases
# ═══════════════════════════════════════════════════════════════════


class TestEdgeCases:

    def test_add_version_missing_changelog(self, client):
        model_id = _register(client, owner="alice").get_json()["modelId"]
        resp = client.post("/api/add-version", json={"modelId": model_id, "newHash": "h", "owner": "alice"})
        assert resp.status_code == 400

    def test_add_version_missing_hash(self, client):
        model_id = _register(client, owner="alice").get_json()["modelId"]
        resp = client.post("/api/add-version", json={"modelId": model_id, "changelog": "c", "owner": "alice"})
        assert resp.status_code == 400

    def test_add_version_missing_owner(self, client):
        model_id = _register(client, owner="alice").get_json()["modelId"]
        resp = client.post("/api/add-version", json={"modelId": model_id, "newHash": "h", "changelog": "c"})
        assert resp.status_code == 400

    def test_multiple_versions_increment(self, client):
        # Each new version should increment the version counter by exactly 1
        model_id = _register(client, owner="alice").get_json()["modelId"]
        client.post("/api/add-version", json={"modelId": model_id, "newHash": "v2", "changelog": "v2", "owner": "alice"})
        resp = client.post("/api/add-version", json={"modelId": model_id, "newHash": "v3", "changelog": "v3", "owner": "alice"})
        assert resp.get_json()["version"] == 3


# ═══════════════════════════════════════════════════════════════════
#  /api/search
# ═══════════════════════════════════════════════════════════════════


class TestSearch:

    def test_search_no_params_returns_all(self, client):
        _register(client, name="Alpha", owner="alice")
        _register(client, name="Beta", owner="bob")
        resp = client.get("/api/search")
        data = resp.get_json()
        assert data["success"] is True
        assert data["count"] == 2

    def test_search_by_name_substring(self, client):
        _register(client, name="AlphaModel", owner="alice")
        _register(client, name="BetaModel", owner="bob")
        resp = client.get("/api/search?q=alpha")
        data = resp.get_json()
        assert data["count"] == 1
        assert data["models"][0]["modelName"] == "AlphaModel"

    def test_search_case_insensitive(self, client):
        _register(client, name="AlphaModel", owner="alice")
        resp = client.get("/api/search?q=ALPHA")
        assert resp.get_json()["count"] == 1

    def test_search_by_hash(self, client):
        _register(client, name="M1", hash_val="deadbeef", owner="alice")
        _register(client, name="M2", hash_val="cafebabe", owner="alice")
        resp = client.get("/api/search?q=deadbeef")
        assert resp.get_json()["count"] == 1

    def test_search_by_owner_filter(self, client):
        _register(client, name="M1", owner="alice")
        _register(client, name="M2", owner="alice")
        _register(client, name="M3", owner="bob")
        resp = client.get("/api/search?owner=alice")
        data = resp.get_json()
        assert data["count"] == 2

    def test_search_combined_q_and_owner(self, client):
        _register(client, name="AlphaModel", owner="alice")
        _register(client, name="AlphaModel", owner="bob")
        resp = client.get("/api/search?q=alpha&owner=alice")
        data = resp.get_json()
        assert data["count"] == 1
        assert data["models"][0]["owner"] == "alice"

    def test_search_no_match(self, client):
        _register(client, name="TestModel", owner="alice")
        resp = client.get("/api/search?q=zzznomatch")
        assert resp.get_json()["count"] == 0

    def test_search_empty_registry(self, client):
        resp = client.get("/api/search")
        data = resp.get_json()
        assert data["success"] is True
        assert data["count"] == 0

    def test_search_returns_mining_metrics(self, client):
        _register(client, name="M", owner="alice")
        data = client.get("/api/search").get_json()
        assert "modelId" in data["models"][0]


# ═══════════════════════════════════════════════════════════════════
#  /api/tamper-demo
# ═══════════════════════════════════════════════════════════════════


class TestTamperDemo:

    def test_tamper_demo_requires_two_blocks(self, client):
        # Genesis-only chain should be rejected
        resp = client.post("/api/tamper-demo")
        assert resp.status_code == 400
        assert resp.get_json()["success"] is False

    def test_tamper_demo_success(self, client):
        _register(client)  # mines block 1
        resp = client.post("/api/tamper-demo")
        data = resp.get_json()
        assert resp.status_code == 200
        assert data["success"] is True

    def test_tamper_demo_detects_attack(self, client):
        _register(client)
        data = client.post("/api/tamper-demo").get_json()
        assert data["tampered"]["isValid"] is False
        assert len(data["tampered"]["errors"]) > 0

    def test_tamper_demo_restores_chain(self, client):
        _register(client)
        data = client.post("/api/tamper-demo").get_json()
        assert data["restored"]["isValid"] is True
        assert data["restored"]["errors"] == []

    def test_tamper_demo_chain_still_valid_after(self, client):
        # Running the demo must leave the real chain intact
        _register(client)
        client.post("/api/tamper-demo")
        result = client.get("/api/chain/validate").get_json()
        assert result["isValid"] is True

    def test_tamper_demo_response_fields(self, client):
        _register(client)
        data = client.post("/api/tamper-demo").get_json()
        assert "targetBlock" in data
        assert "tampered" in data
        assert "restored" in data
        assert data["targetBlock"] == 1


# ═══════════════════════════════════════════════════════════════════
#  Mining metrics in responses
# ═══════════════════════════════════════════════════════════════════


class TestMiningMetrics:

    def test_register_returns_mining_time(self, client):
        data = _register(client).get_json()
        assert "miningTime" in data
        assert isinstance(data["miningTime"], (int, float))

    def test_register_returns_attempts(self, client):
        data = _register(client).get_json()
        assert "attempts" in data
        assert isinstance(data["attempts"], int)
        assert data["attempts"] >= 1

    def test_verify_returns_mining_metrics(self, client):
        model_id = _register(client).get_json()["modelId"]
        data = client.post("/api/verify", json={"modelId": model_id, "providedHash": "abc123"}).get_json()
        assert "miningTime" in data
        assert "attempts" in data

    def test_add_version_returns_mining_metrics(self, client):
        model_id = _register(client, owner="alice").get_json()["modelId"]
        data = client.post("/api/add-version", json={
            "modelId": model_id, "newHash": "v2", "changelog": "c", "owner": "alice"
        }).get_json()
        assert "miningTime" in data
        assert "attempts" in data
