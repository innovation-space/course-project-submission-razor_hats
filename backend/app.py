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
from blockchain import Blockchain
from time import time
import hashlib

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

        return jsonify(
            {
                "success": True,
                "modelId": model_id,
                "blockIndex": new_block.index,
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

        return jsonify(
            {
                "success": True,
                "isValid": is_valid,
                "message": "Model integrity VERIFIED — hash matches"
                if is_valid
                else "INTEGRITY MISMATCH — hash does not match",
                "blockIndex": new_block.index,
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

        return jsonify(
            {
                "success": True,
                "version": new_ver,
                "blockIndex": new_block.index,
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
        blockchain.mine_pending_transactions()

        return jsonify({"success": True, "message": "Model deactivated"}), 200
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5000)
