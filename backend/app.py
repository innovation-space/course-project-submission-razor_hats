"""
BlockVerify Flask REST API
==========================

Provides HTTP endpoints for the BlockVerify AI-model integrity
verification system.  Every write operation (register, verify,
add-version) creates a blockchain transaction and mines a new block.

Run:
    python app.py          → http://localhost:5000

Author: razor_hats team
"""

from flask import Flask, request, jsonify
from flask_cors import CORS
from blockchain import Blockchain, Block
from time import time
import hashlib
import json
import os

# ------------------------------------------------------------------ #
#  App & state initialisation                                         #
# ------------------------------------------------------------------ #

app = Flask(__name__)
CORS(app)

# Custom blockchain (difficulty 4 → hash must start with "0000")
blockchain = Blockchain(difficulty=4)

# In-memory registries (would be a DB in production)
models_registry = {}        # modelId  → model dict
verification_logs = {}      # modelId  → [verification records]

# Persistence file path
DATA_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "blockverify_data.json")


# ------------------------------------------------------------------ #
#  Persistence                                                         #
# ------------------------------------------------------------------ #

def save_state():
    """Persist blockchain, registries, and logs to disk."""
    if app.config.get("TESTING"):
        return
    data = {
        "chain": blockchain.get_chain(),
        "difficulty": blockchain.difficulty,
        "models_registry": models_registry,
        "verification_logs": verification_logs,
    }
    with open(DATA_FILE, "w") as f:
        json.dump(data, f, indent=2)


def load_state():
    """Load persisted state from disk if file exists."""
    if not os.path.exists(DATA_FILE):
        return
    try:
        with open(DATA_FILE, "r") as f:
            data = json.load(f)
        # Rebuild blockchain from serialized chain
        blockchain.chain = []
        for bd in data["chain"]:
            b = Block(bd["index"], bd["timestamp"], bd["transactions"], bd["previous_hash"], bd["nonce"])
            b.hash = bd["hash"]  # Override recalculated hash with stored hash
            blockchain.chain.append(b)
        models_registry.update(data.get("models_registry", {}))
        verification_logs.update(data.get("verification_logs", {}))
        print(f"  Loaded {len(blockchain.chain)} blocks from disk")
    except Exception as e:
        print(f"  Warning: Could not load saved state: {e}")


# Load persisted data on startup
load_state()


# ------------------------------------------------------------------ #
#  Helpers                                                             #
# ------------------------------------------------------------------ #

def generate_model_id(model_name, model_hash, owner):
    """Deterministic, collision-resistant model ID (first 16 hex chars)."""
    unique = f"{model_name}{model_hash}{owner}{time()}"
    return hashlib.sha256(unique.encode()).hexdigest()[:16]


# ------------------------------------------------------------------ #
#  WRITE endpoints (mine a block)                                      #
# ------------------------------------------------------------------ #

@app.route("/api/register", methods=["POST"])
def register_model():
    """Register a new AI model on the blockchain."""
    try:
        data = request.get_json()

        if not data.get("modelName"):
            return jsonify({"success": False, "error": "Model name is required"}), 400
        if not data.get("modelHash"):
            return jsonify({"success": False, "error": "Model hash is required"}), 400
        if not data.get("owner"):
            return jsonify({"success": False, "error": "Owner is required"}), 400

        model_id = generate_model_id(
            data["modelName"], data["modelHash"], data["owner"]
        )

        tx = {
            "type": "register",
            "modelId": model_id,
            "modelName": data["modelName"],
            "modelHash": data["modelHash"],
            "metadata": data.get("metadata", ""),
            "owner": data["owner"],
            "timestamp": time(),
        }

        blockchain.add_transaction(tx)
        new_block = blockchain.mine_pending_transactions()

        models_registry[model_id] = {
            "modelId": model_id,
            "modelName": data["modelName"],
            "modelHash": data["modelHash"],
            "metadata": data.get("metadata", ""),
            "owner": data["owner"],
            "registeredAt": tx["timestamp"],
            "blockIndex": new_block.index,
            "currentVersion": 1,
            "isActive": True,
            "versions": [
                {
                    "version": 1,
                    "hash": data["modelHash"],
                    "timestamp": tx["timestamp"],
                    "changelog": "Initial version",
                    "blockIndex": new_block.index,
                }
            ],
        }
        verification_logs[model_id] = []
        save_state()

        return jsonify(
            {
                "success": True,
                "modelId": model_id,
                "blockIndex": new_block.index,
                "miningTime": new_block.mining_time,
                "miningAttempts": new_block.mining_attempts,
                "message": "Model registered successfully",
            }
        ), 200

    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/api/verify", methods=["POST"])
def verify_model():
    """Verify AI model integrity against the stored hash."""
    try:
        data = request.get_json()

        if not data.get("modelId"):
            return jsonify({"success": False, "error": "Model ID is required"}), 400
        if not data.get("providedHash"):
            return jsonify({"success": False, "error": "Hash is required"}), 400

        model = models_registry.get(data["modelId"])
        if not model:
            return jsonify({"success": False, "error": "Model not found"}), 404
        if not model["isActive"]:
            return jsonify({"success": False, "error": "Model is deactivated"}), 400

        is_valid = model["modelHash"] == data["providedHash"]

        tx = {
            "type": "verify",
            "modelId": data["modelId"],
            "providedHash": data["providedHash"],
            "storedHash": model["modelHash"],
            "isValid": is_valid,
            "verifier": data.get("verifier", "anonymous"),
            "timestamp": time(),
        }

        blockchain.add_transaction(tx)
        new_block = blockchain.mine_pending_transactions()

        verification_logs[data["modelId"]].append(
            {
                "verifier": tx["verifier"],
                "timestamp": tx["timestamp"],
                "isValid": is_valid,
                "providedHash": data["providedHash"],
                "blockIndex": new_block.index,
            }
        )
        save_state()

        return jsonify(
            {
                "success": True,
                "isValid": is_valid,
                "message": "Model integrity VERIFIED — hash matches"
                if is_valid
                else "INTEGRITY MISMATCH — hash does not match",
                "blockIndex": new_block.index,
                "miningTime": new_block.mining_time,
                "miningAttempts": new_block.mining_attempts,
                "storedHash": model["modelHash"],
                "providedHash": data["providedHash"],
            }
        ), 200

    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/api/add-version", methods=["POST"])
def add_version():
    """Add a new version to an existing model."""
    try:
        data = request.get_json()

        if not data.get("modelId"):
            return jsonify({"success": False, "error": "Model ID is required"}), 400
        if not data.get("newHash"):
            return jsonify({"success": False, "error": "New hash is required"}), 400
        if not data.get("changelog"):
            return jsonify({"success": False, "error": "Changelog is required"}), 400
        if not data.get("owner"):
            return jsonify({"success": False, "error": "Owner is required"}), 400

        model = models_registry.get(data["modelId"])
        if not model:
            return jsonify({"success": False, "error": "Model not found"}), 404
        if model["owner"] != data["owner"]:
            return jsonify({"success": False, "error": "Only the model owner can add versions"}), 403
        if not model["isActive"]:
            return jsonify({"success": False, "error": "Model is deactivated"}), 400

        new_ver = model["currentVersion"] + 1

        tx = {
            "type": "add_version",
            "modelId": data["modelId"],
            "version": new_ver,
            "newHash": data["newHash"],
            "previousHash": model["modelHash"],
            "changelog": data["changelog"],
            "owner": data["owner"],
            "timestamp": time(),
        }

        blockchain.add_transaction(tx)
        new_block = blockchain.mine_pending_transactions()

        model["modelHash"] = data["newHash"]
        model["currentVersion"] = new_ver
        model["versions"].append(
            {
                "version": new_ver,
                "hash": data["newHash"],
                "timestamp": tx["timestamp"],
                "changelog": data["changelog"],
                "blockIndex": new_block.index,
            }
        )
        save_state()

        return jsonify(
            {
                "success": True,
                "version": new_ver,
                "blockIndex": new_block.index,
                "miningTime": new_block.mining_time,
                "miningAttempts": new_block.mining_attempts,
                "message": f"Version {new_ver} added successfully",
            }
        ), 200

    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/api/deactivate", methods=["POST"])
def deactivate_model():
    """Soft-delete (deactivate) a model."""
    try:
        data = request.get_json()
        model = models_registry.get(data.get("modelId"))
        if not model:
            return jsonify({"success": False, "error": "Model not found"}), 404
        if model["owner"] != data.get("owner"):
            return jsonify({"success": False, "error": "Only the owner can deactivate"}), 403

        model["isActive"] = False

        tx = {"type": "deactivate", "modelId": data["modelId"], "owner": data["owner"], "timestamp": time()}
        blockchain.add_transaction(tx)
        new_block = blockchain.mine_pending_transactions()
        save_state()

        return jsonify({
            "success": True,
            "message": "Model deactivated",
            "miningTime": new_block.mining_time,
            "miningAttempts": new_block.mining_attempts,
        }), 200
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/api/reactivate", methods=["POST"])
def reactivate_model():
    """Re-activate a previously deactivated model."""
    try:
        data = request.get_json()
        model = models_registry.get(data.get("modelId"))
        if not model:
            return jsonify({"success": False, "error": "Model not found"}), 404
        if model["owner"] != data.get("owner"):
            return jsonify({"success": False, "error": "Only the owner can reactivate"}), 403
        if model["isActive"]:
            return jsonify({"success": False, "error": "Model is already active"}), 400

        model["isActive"] = True

        tx = {"type": "reactivate", "modelId": data["modelId"], "owner": data["owner"], "timestamp": time()}
        blockchain.add_transaction(tx)
        new_block = blockchain.mine_pending_transactions()
        save_state()

        return jsonify({
            "success": True,
            "message": "Model reactivated",
            "miningTime": new_block.mining_time,
            "miningAttempts": new_block.mining_attempts,
        }), 200
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


# ------------------------------------------------------------------ #
#  READ endpoints                                                      #
# ------------------------------------------------------------------ #

@app.route("/api/models/<owner>", methods=["GET"])
def get_models_by_owner(owner):
    """Return all models registered by *owner*."""
    try:
        owner_models = [m for m in models_registry.values() if m["owner"] == owner]
        return jsonify({"success": True, "models": owner_models, "count": len(owner_models)}), 200
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/api/model/<model_id>", methods=["GET"])
def get_model(model_id):
    """Return details of a single model."""
    model = models_registry.get(model_id)
    if not model:
        return jsonify({"success": False, "error": "Model not found"}), 404
    return jsonify({"success": True, "model": model}), 200


@app.route("/api/versions/<model_id>", methods=["GET"])
def get_versions(model_id):
    """Return version history for a model."""
    model = models_registry.get(model_id)
    if not model:
        return jsonify({"success": False, "error": "Model not found"}), 404
    return jsonify({"success": True, "versions": model["versions"], "currentVersion": model["currentVersion"]}), 200


@app.route("/api/audit/<model_id>", methods=["GET"])
def get_audit_log(model_id):
    """Return the verification audit trail for a model."""
    if model_id not in verification_logs:
        return jsonify({"success": False, "error": "Model not found"}), 404
    logs = verification_logs[model_id]
    return jsonify({"success": True, "verifications": logs, "count": len(logs)}), 200


@app.route("/api/chain", methods=["GET"])
def get_chain():
    """Return the entire blockchain."""
    return jsonify({"success": True, "chain": blockchain.get_chain(), "length": len(blockchain.chain)}), 200


@app.route("/api/chain/validate", methods=["GET"])
def validate_chain():
    """Validate blockchain integrity and return errors (if any)."""
    result = blockchain.is_chain_valid()
    return jsonify(
        {
            "success": True,
            "isValid": result["valid"],
            "errors": result["errors"],
            "message": "Blockchain is valid ✓" if result["valid"] else "Blockchain has integrity errors ✗",
        }
    ), 200


@app.route("/api/stats", methods=["GET"])
def get_stats():
    """Return high-level platform statistics."""
    total_verifications = sum(len(v) for v in verification_logs.values())
    return jsonify(
        {
            "totalModels": len(models_registry),
            "totalVerifications": total_verifications,
            "totalBlocks": len(blockchain.chain),
        }
    ), 200


@app.route("/api/search", methods=["GET"])
def search_models():
    """Search models by name keyword (case-insensitive)."""
    q = request.args.get("q", "").strip().lower()
    if not q:
        return jsonify({"success": False, "error": "Query parameter 'q' is required"}), 400
    matches = [m for m in models_registry.values() if q in m["modelName"].lower()]
    return jsonify({"success": True, "results": matches, "count": len(matches)}), 200


# ------------------------------------------------------------------ #
#  Server start                                                        #
# ------------------------------------------------------------------ #

if __name__ == "__main__":
    print("══════════════════════════════════════════════")
    print("  🔗 BlockVerify — Custom Blockchain Server")
    print("  (Milestone 2 Final Submission Version)")
    print("══════════════════════════════════════════════")
    print(f"  Difficulty  : {blockchain.difficulty} leading zeros")
    print(f"  Genesis hash: {blockchain.get_latest_block().hash}")
    print("  Server      : http://localhost:5000")
    print("══════════════════════════════════════════════")
    app.run(debug=True, port=5000)
