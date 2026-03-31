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

import os
import json
from flask import Flask, request, jsonify, g
from flask_cors import CORS
from blockchain import Blockchain, Block
from auth import auth_bp, require_auth
from time import time
import hashlib

# ------------------------------------------------------------------ #
#  App & state initialisation                                         #
# ------------------------------------------------------------------ #

app = Flask(__name__)
CORS(app)
app.register_blueprint(auth_bp)

# Persistence file paths
DATA_DIR = os.path.join(os.path.dirname(__file__), "data")
REGISTRY_FILE = os.path.join(DATA_DIR, "models_registry.json")
LOGS_FILE     = os.path.join(DATA_DIR, "verification_logs.json")
CHAIN_FILE    = os.path.join(DATA_DIR, "chain.json")

os.makedirs(DATA_DIR, exist_ok=True)

# ------------------------------------------------------------------ #
#  Persistence helpers                                                 #
# ------------------------------------------------------------------ #

def save_state():
    """Persist registry, logs, and chain to JSON files."""
    with open(REGISTRY_FILE, "w") as f:
        json.dump(models_registry, f, indent=2)
    with open(LOGS_FILE, "w") as f:
        json.dump(verification_logs, f, indent=2)
    with open(CHAIN_FILE, "w") as f:
        json.dump(blockchain.get_chain(), f, indent=2)


def load_state():
    """Restore registry, logs, and chain from JSON files if they exist."""
    global models_registry, verification_logs

    if os.path.exists(REGISTRY_FILE):
        with open(REGISTRY_FILE) as f:
            models_registry.update(json.load(f))

    if os.path.exists(LOGS_FILE):
        with open(LOGS_FILE) as f:
            verification_logs.update(json.load(f))

    if os.path.exists(CHAIN_FILE):
        with open(CHAIN_FILE) as f:
            chain_data = json.load(f)
        # Rebuild Block objects from saved dicts
        rebuilt = []
        for bd in chain_data:
            b = Block(
                index=bd["index"],
                timestamp=bd["timestamp"],
                transactions=bd["transactions"],
                previous_hash=bd["previous_hash"],
                nonce=bd["nonce"],
            )
            b.hash = bd["hash"]   # restore mined hash directly
            rebuilt.append(b)
        if rebuilt:
            blockchain.chain = rebuilt


# Custom blockchain (difficulty 4 → hash must start with "0000")
blockchain = Blockchain(difficulty=4)

# In-memory registries (persisted to disk on every write)
models_registry = {}        # modelId  → model dict
verification_logs = {}      # modelId  → [verification records]

# Load saved state on startup
load_state()

# ------------------------------------------------------------------ #
#  Rate limiter                                                        #
# ------------------------------------------------------------------ #

# Tracks recent write timestamps per owner: { owner: [t1, t2, ...] }
_rate_log: dict = {}

RATE_LIMIT      = 10    # max requests
RATE_WINDOW_SEC = 60    # per this many seconds


def check_rate_limit(owner: str) -> tuple[bool, str]:
    """
    Return (allowed, error_message).
    Sliding-window rate limiter: at most RATE_LIMIT write operations
    per owner within RATE_WINDOW_SEC seconds.
    """
    now = time()
    timestamps = _rate_log.get(owner, [])
    # Drop timestamps outside the window
    timestamps = [t for t in timestamps if now - t < RATE_WINDOW_SEC]
    if len(timestamps) >= RATE_LIMIT:
        wait = int(RATE_WINDOW_SEC - (now - timestamps[0]))
        _rate_log[owner] = timestamps
        return False, (
            f"Rate limit exceeded: max {RATE_LIMIT} operations per "
            f"{RATE_WINDOW_SEC}s. Try again in {wait}s."
        )
    timestamps.append(now)
    _rate_log[owner] = timestamps
    return True, ""


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
@require_auth
def register_model():
    """Register a new AI model on the blockchain."""
    try:
        data = request.get_json()
        owner = g.user   # comes from the verified JWT — cannot be spoofed

        if not data.get("modelName"):
            return jsonify({"success": False, "error": "Model name is required"}), 400
        if not data.get("modelHash"):
            return jsonify({"success": False, "error": "Model hash is required"}), 400

        allowed, err = check_rate_limit(owner)
        if not allowed:
            return jsonify({"success": False, "error": err}), 429

        model_id = generate_model_id(data["modelName"], data["modelHash"], owner)

        tx = {
            "type": "register",
            "modelId": model_id,
            "modelName": data["modelName"],
            "modelHash": data["modelHash"],
            "metadata": data.get("metadata", ""),
            "owner": owner,
            "timestamp": time(),
        }

        blockchain.add_transaction(tx)
        new_block = blockchain.mine_pending_transactions()
        if new_block is None:
            return jsonify({"success": False, "error": "Mining failed: no pending transactions"}), 500

        models_registry[model_id] = {
            "modelId": model_id,
            "modelName": data["modelName"],
            "modelHash": data["modelHash"],
            "metadata": data.get("metadata", ""),
            "owner": owner,
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
                "attempts": new_block.attempts,
                "message": "Model registered successfully",
            }
        ), 200

    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/api/verify", methods=["POST"])
@require_auth
def verify_model():
    """Verify AI model integrity against the stored hash."""
    try:
        data = request.get_json()
        verifier = g.user   # JWT-authenticated username

        if not data.get("modelId"):
            return jsonify({"success": False, "error": "Model ID is required"}), 400
        if not data.get("providedHash"):
            return jsonify({"success": False, "error": "Hash is required"}), 400

        allowed, err = check_rate_limit(verifier)
        if not allowed:
            return jsonify({"success": False, "error": err}), 429

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
            "verifier": verifier,
            "timestamp": time(),
        }

        blockchain.add_transaction(tx)
        new_block = blockchain.mine_pending_transactions()
        if new_block is None:
            return jsonify({"success": False, "error": "Mining failed: no pending transactions"}), 500

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
                "attempts": new_block.attempts,
                "storedHash": model["modelHash"],
                "providedHash": data["providedHash"],
            }
        ), 200

    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/api/add-version", methods=["POST"])
@require_auth
def add_version():
    """Add a new version to an existing model."""
    try:
        data = request.get_json()
        owner = g.user

        if not data.get("modelId"):
            return jsonify({"success": False, "error": "Model ID is required"}), 400
        if not data.get("newHash"):
            return jsonify({"success": False, "error": "New hash is required"}), 400
        if not data.get("changelog"):
            return jsonify({"success": False, "error": "Changelog is required"}), 400

        allowed, err = check_rate_limit(owner)
        if not allowed:
            return jsonify({"success": False, "error": err}), 429

        model = models_registry.get(data["modelId"])
        if not model:
            return jsonify({"success": False, "error": "Model not found"}), 404
        if model["owner"] != owner:
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
            "owner": owner,
            "timestamp": time(),
        }

        blockchain.add_transaction(tx)
        new_block = blockchain.mine_pending_transactions()
        if new_block is None:
            return jsonify({"success": False, "error": "Mining failed: no pending transactions"}), 500

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
                "attempts": new_block.attempts,
                "message": f"Version {new_ver} added successfully",
            }
        ), 200

    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/api/deactivate", methods=["POST"])
@require_auth
def deactivate_model():
    """Soft-delete (deactivate) a model."""
    try:
        data = request.get_json()
        owner = g.user

        if not data or not data.get("modelId"):
            return jsonify({"success": False, "error": "modelId is required"}), 400

        allowed, err = check_rate_limit(owner)
        if not allowed:
            return jsonify({"success": False, "error": err}), 429

        model = models_registry.get(data["modelId"])
        if not model:
            return jsonify({"success": False, "error": "Model not found"}), 404
        if model["owner"] != owner:
            return jsonify({"success": False, "error": "Only the owner can deactivate"}), 403

        model["isActive"] = False

        tx = {"type": "deactivate", "modelId": data["modelId"], "owner": owner, "timestamp": time()}
        blockchain.add_transaction(tx)
        blockchain.mine_pending_transactions()
        save_state()

        return jsonify({"success": True, "message": "Model deactivated"}), 200
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


@app.route("/api/audit/<model_id>/export", methods=["GET"])
def export_audit_csv(model_id):
    """
    Export the audit trail for a model as a downloadable CSV file.

    Columns: modelId, verifier, result, providedHash, blockIndex, timestamp
    """
    import csv, io
    from datetime import datetime
    from flask import Response

    if model_id not in verification_logs:
        return jsonify({"success": False, "error": "Model not found"}), 404

    logs = verification_logs[model_id]
    model_name = models_registry.get(model_id, {}).get("modelName", model_id)

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["modelId", "modelName", "verifier", "result", "providedHash", "blockIndex", "timestamp"])
    for entry in logs:
        ts = entry.get("timestamp", "")
        if ts:
            ts = datetime.utcfromtimestamp(ts).strftime("%Y-%m-%d %H:%M:%S UTC")
        writer.writerow([
            model_id,
            model_name,
            entry.get("verifier", "anonymous"),
            "VALID" if entry.get("isValid") else "INVALID",
            entry.get("providedHash", ""),
            entry.get("blockIndex", ""),
            ts,
        ])

    csv_data = output.getvalue()
    filename = f"audit_{model_id[:8]}.csv"
    return Response(
        csv_data,
        mimetype="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


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


@app.route("/api/search", methods=["GET"])
def search_models():
    """
    Search models by name, hash, or owner.

    Query params:
        q     (str) : substring to match against modelName and modelHash
        owner (str) : filter by exact owner (optional)

    Returns:
        JSON with matching models list and count.
    """
    try:
        q     = request.args.get("q", "").lower().strip()
        owner = request.args.get("owner", "").strip()

        results = []
        for model in models_registry.values():
            if owner and model["owner"] != owner:
                continue
            if q and not (
                q in model["modelName"].lower() or
                q in model["modelHash"].lower() or
                q in model["modelId"].lower()
            ):
                continue
            results.append(model)

        return jsonify({"success": True, "models": results, "count": len(results)}), 200
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/api/tamper-demo", methods=["POST"])
def tamper_demo():
    """
    Non-destructive tamper simulation.

    Temporarily mutates block 1 (first real block after genesis), runs
    chain validation to capture the detected errors, then restores the
    block to its original state and re-validates to confirm restoration.

    Returns a JSON report showing before/after validation results.
    """
    if len(blockchain.chain) < 2:
        return jsonify({
            "success": False,
            "error": "Need at least 2 blocks to run a tamper demo. Register a model first.",
        }), 400

    target = blockchain.chain[1]

    # Save originals
    original_transactions = [tx.copy() for tx in target.transactions]
    original_hash = target.hash

    # --- TAMPER ---
    target.transactions[0]["__TAMPERED__"] = "SIMULATED ATTACK INJECTED"
    tampered_result = blockchain.is_chain_valid()

    # --- RESTORE ---
    target.transactions = original_transactions
    target.hash = original_hash
    restored_result = blockchain.is_chain_valid()

    return jsonify({
        "success": True,
        "targetBlock": target.index,
        "tampered": {
            "isValid": tampered_result["valid"],
            "errors": tampered_result["errors"],
        },
        "restored": {
            "isValid": restored_result["valid"],
            "errors": restored_result["errors"],
        },
        "message": "Tamper simulation complete — blockchain detected the attack and was restored.",
    }), 200


@app.route("/api/rate-limit-status", methods=["GET"])
def rate_limit_status():
    """Return remaining write quota for a given owner within the current window."""
    owner = request.args.get("owner", "").strip()
    if not owner:
        return jsonify({"success": False, "error": "owner param required"}), 400
    now = time()
    timestamps = _rate_log.get(owner, [])
    timestamps = [t for t in timestamps if now - t < RATE_WINDOW_SEC]
    used = len(timestamps)
    remaining = max(0, RATE_LIMIT - used)
    return jsonify({
        "success": True,
        "owner": owner,
        "limit": RATE_LIMIT,
        "windowSeconds": RATE_WINDOW_SEC,
        "used": used,
        "remaining": remaining,
    }), 200


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
    port = int(os.environ.get("PORT", 5000))
    app.run(debug=False, host="0.0.0.0", port=port)
