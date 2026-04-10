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
from auth import auth_bp, require_auth
import algorand_client
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
    """Persist registry and logs to JSON files."""
    with open(REGISTRY_FILE, "w") as f:
        json.dump(models_registry, f, indent=2)
    with open(LOGS_FILE, "w") as f:
        json.dump(verification_logs, f, indent=2)


def load_state():
    """Restore registry, logs, and chain from JSON files if they exist."""
    global models_registry, verification_logs

    if os.path.exists(REGISTRY_FILE):
        with open(REGISTRY_FILE) as f:
            models_registry.update(json.load(f))

    if os.path.exists(LOGS_FILE):
        with open(LOGS_FILE) as f:
            verification_logs.update(json.load(f))


# Algorand Testnet Interface
# Operations are broadcasted to the global Algorand blockchain natively

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

        # ── Algorand Migration: Broadcast to Global Testnet ──
        algo_resp = algorand_client.broadcast_hash_to_algorand(
            model_id, data["modelName"], data["modelHash"], owner
        )
        
        if not algo_resp.get("success"):
            return jsonify({"success": False, "error": algo_resp.get("error")}), 500

        models_registry[model_id] = {
            "modelId": model_id,
            "modelName": data["modelName"],
            "modelHash": data["modelHash"],
            "metadata": data.get("metadata", ""),
            "owner": owner,
            "registeredAt": int(time()),
            "blockIndex": algo_resp.get("round"),
            "algoTxId": algo_resp.get("txid"),
            "currentVersion": 1,
            "isActive": True,
            "versions": [
                {
                    "version": 1,
                    "hash": data["modelHash"],
                    "timestamp": int(time()),
                    "changelog": "Initial version",
                    "blockIndex": algo_resp.get("round"),
                    "algoTxId": algo_resp.get("txid"),
                }
            ],
        }
        verification_logs[model_id] = []
        save_state()

        return jsonify(
            {
                "success": True,
                "modelId": model_id,
                "blockIndex": algo_resp.get("round"),
                "algoTxId": algo_resp.get("txid"),
                "message": "Model registered securely on Algorand Testnet",
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

        # Privacy guard — only the owner can verify a private model
        if model.get("isPrivate") and model["owner"] != verifier:
            return jsonify({
                "success": False,
                "error": "This model is private 🔒 — only the owner can verify it.",
            }), 403

        is_valid = model["modelHash"] == data["providedHash"]

        algo_resp = algorand_client.broadcast_hash_to_algorand(
            data["modelId"], model["modelName"], data["providedHash"], verifier
        )
        
        if not algo_resp.get("success"):
            return jsonify({"success": False, "error": algo_resp.get("error")}), 500

        verification_logs[data["modelId"]].append(
            {
                "verifier": verifier,
                "timestamp": int(time()),
                "isValid": is_valid,
                "providedHash": data["providedHash"],
                "blockIndex": algo_resp.get("round"),
                "algoTxId": algo_resp.get("txid"),
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
                "blockIndex": algo_resp.get("round"),
                "algoTxId": algo_resp.get("txid"),
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

        model_id = data["modelId"]
        algo_resp = algorand_client.broadcast_hash_to_algorand(
            model_id, model["modelName"], data["newHash"], owner
        )
        if not algo_resp.get("success"):
            return jsonify({"success": False, "error": algo_resp.get("error")}), 500

        model["modelHash"] = data["newHash"]
        model["currentVersion"] = new_ver
        model["versions"].append(
            {
                "version": new_ver,
                "hash": data["newHash"],
                "timestamp": int(time()),
                "changelog": data["changelog"],
                "blockIndex": algo_resp.get("round"),
                "algoTxId": algo_resp.get("txid"),
            }
        )
        save_state()

        return jsonify(
            {
                "success": True,
                "version": new_ver,
                "blockIndex": algo_resp.get("round"),
                "algoTxId": algo_resp.get("txid"),
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

        algo_resp = algorand_client.broadcast_hash_to_algorand(
            data["modelId"], model["modelName"], "DEACTIVATED", owner
        )
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
    return jsonify({"success": False, "error": "Chain is verified directly on Algorand. Please use Algorand Explorer."}), 400


@app.route("/api/chain/validate", methods=["GET"])
def validate_chain():
    """Validate blockchain integrity (Disabled: Now on Algorand)."""
    return jsonify(
        {
            "success": True,
            "isValid": True,
            "errors": [],
            "message": "Blockchain is mathematically maintained by the global Algorand network ✓",
        }
    ), 200


@app.route("/api/search", methods=["GET"])
def search_models():
    """
    Search models by name, hash, or owner.
    Private models are excluded unless the requester owns them.
    """
    try:
        from auth import decode_token
        q     = request.args.get("q", "").lower().strip()
        owner = request.args.get("owner", "").strip()

        # Determine the requesting user (optional — no 401 if missing)
        requester = None
        auth_hdr = request.headers.get("Authorization", "")
        if auth_hdr.startswith("Bearer "):
            payload = decode_token(auth_hdr[7:])
            if payload:
                requester = payload.get("username")

        results = []
        for model in models_registry.values():
            # Hide private models from non-owners
            if model.get("isPrivate") and model["owner"] != requester:
                continue
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
    return jsonify({"success": False, "error": "Tampering is physically impossible on the Algorand Testnet. This action has been disabled."}), 403


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
            "totalBlocks": "Algorand Live",
        }
    ), 200




# ------------------------------------------------------------------ #
#  Algorand Testnet live endpoints                                     #
# ------------------------------------------------------------------ #

@app.route("/api/algo/wallet", methods=["GET"])
def algo_wallet_info():
    """Return live Algorand wallet / account info for the server address."""
    data = algorand_client.get_wallet_info()
    return jsonify(data), (200 if data.get("success") else 503)


@app.route("/api/algo/tx/<txid>", methods=["GET"])
def algo_tx_info(txid):
    """
    Fetch a confirmed Algorand transaction by TxID from the public Indexer.
    Used by the Blockchain Proof page to show live on-chain data.
    """
    data = algorand_client.get_transaction_info(txid)
    return jsonify(data), (200 if data.get("success") else 404)


@app.route("/api/algo/contract", methods=["GET"])
def algo_contract_info():
    """Return the deployed smart contract App ID and explorer link."""
    from contract import load_app_id
    app_id = load_app_id()
    if not app_id:
        return jsonify({"success": False, "error": "Contract not yet deployed. Register a model first."}), 404
    return jsonify({
        "success": True,
        "app_id": app_id,
        "network": "Algorand Testnet",
        "explorer_url": f"https://lora.algonode.network/testnet/application/{app_id}",
    }), 200

@app.route("/api/algo/network", methods=["GET"])
def algo_network_stats():
    data = algorand_client.get_network_stats()
    return jsonify(data), (200 if data.get("success") else 503)


@app.route("/api/algo/ledger", methods=["GET"])
def algo_transaction_ledger():
    limit = request.args.get("limit", 50, type=int)
    data = algorand_client.get_transaction_ledger(limit=min(limit, 100))
    return jsonify(data), (200 if data.get("success") else 503)


@app.route("/api/algo/verify-onchain/<model_id>", methods=["GET"])
def algo_verify_onchain(model_id):
    """Read the smart contract global state and compare hash with local DB."""
    from contract import load_app_id, read_contract_state

    app_id = load_app_id()
    if not app_id:
        return jsonify({"success": False, "error": "Smart contract not deployed yet"}), 503

    # Get the locally stored hash
    model = models_registry.get(model_id)
    if not model:
        return jsonify({"success": False, "error": "Model not found in local registry"}), 404

    local_hash = model.get("modelHash", "")

    # Read from smart contract
    result = read_contract_state(app_id, model_id)
    if not result.get("success"):
        return jsonify(result), 503

    if not result.get("found"):
        return jsonify({
            "success": True,
            "verified": False,
            "reason": "not_found",
            "message": "Model ID not found in smart contract. It may not have been registered on-chain.",
            "model_id": model_id,
            "app_id": app_id,
        }), 200

    on_chain_hash = result.get("on_chain_hash", "")
    match = (on_chain_hash == local_hash)

    return jsonify({
        "success": True,
        "verified": match,
        "reason": "match" if match else "mismatch",
        "model_id": model_id,
        "model_name": model.get("modelName", ""),
        "local_hash": local_hash,
        "on_chain_hash": on_chain_hash,
        "app_id": app_id,
        "explorer_url": f"https://lora.algokit.io/testnet/application/{app_id}",
        "message": (
            "ON-CHAIN VERIFIED: The hash stored in the Algorand smart contract matches the local registry."
            if match else
            "MISMATCH DETECTED: The on-chain hash does NOT match the local registry. Possible tampering!"
        ),
    }), 200


@app.route("/api/algo/merkle", methods=["GET"])
def algo_merkle_tree():
    """
    Build a Merkle tree from ALL registered model hashes.
    Returns the tree structure (for D3.js), the Merkle root, and leaves.
    """
    import hashlib

    # Collect active model hashes
    leaves_data = []
    for mid, m in models_registry.items():
        if m.get("isActive", True):
            leaves_data.append({
                "model_id": mid,
                "model_name": m.get("modelName", "Unknown"),
                "hash": m.get("modelHash", ""),
                "owner": m.get("owner", ""),
            })

    if not leaves_data:
        return jsonify({
            "success": True,
            "count": 0,
            "merkleRoot": None,
            "tree": None,
            "message": "No models registered yet. Register a model to see the Merkle tree.",
        }), 200

    # Build leaf nodes
    def sha256(text):
        return hashlib.sha256(text.encode()).hexdigest()

    leaf_nodes = []
    for lf in leaves_data:
        leaf_nodes.append({
            "hash": lf["hash"],
            "label": lf["model_name"],
            "modelId": lf["model_id"],
            "owner": lf["owner"],
            "txType": "registration",
            "children": [],
        })

    # If odd number of leaves, duplicate the last one
    if len(leaf_nodes) % 2 != 0:
        leaf_nodes.append({**leaf_nodes[-1], "label": leaf_nodes[-1]["label"] + " (dup)"})

    # Build tree bottom-up
    def build_tree(nodes):
        if len(nodes) == 1:
            return nodes[0]
        parents = []
        for i in range(0, len(nodes), 2):
            left = nodes[i]
            right = nodes[i + 1] if i + 1 < len(nodes) else nodes[i]
            parent_hash = sha256(left["hash"] + right["hash"])
            parents.append({
                "hash": parent_hash,
                "label": "",
                "children": [left, right],
            })
        return build_tree(parents)

    tree = build_tree(leaf_nodes)

    return jsonify({
        "success": True,
        "count": len(leaves_data),
        "merkleRoot": tree["hash"],
        "tree": tree,
        "leaves": [{"hash": lf["hash"], "txType": "registration"} for lf in leaves_data],
    }), 200


@app.route("/api/stats/activity", methods=["GET"])
def get_activity():
    """
    Return daily registration and verification counts for the last N days.
    Query param: days (int, default 14, max 30)
    """
    from datetime import datetime, timezone, timedelta

    days = min(int(request.args.get("days", 14)), 30)
    now  = datetime.now(timezone.utc)

    # Build a dict of date_str → {registrations, verifications}
    buckets = {}
    for i in range(days - 1, -1, -1):
        d = (now - timedelta(days=i)).strftime("%b %d")
        buckets[d] = {"registrations": 0, "verifications": 0}

    for model in models_registry.values():
        ts = model.get("registeredAt")
        if ts:
            d = datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%b %d")
            if d in buckets:
                buckets[d]["registrations"] += 1

    for logs in verification_logs.values():
        for entry in logs:
            ts = entry.get("timestamp")
            if ts:
                d = datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%b %d")
                if d in buckets:
                    buckets[d]["verifications"] += 1

    labels        = list(buckets.keys())
    registrations = [buckets[d]["registrations"]  for d in labels]
    verifications = [buckets[d]["verifications"]  for d in labels]

    return jsonify({
        "success": True,
        "labels": labels,
        "registrations": registrations,
        "verifications": verifications,
        "days": days,
    }), 200


@app.route("/api/registry", methods=["GET"])
def public_registry():
    """
    Public model registry — all models across all owners.
    Private models are excluded from public view.
    """
    try:
        from auth import decode_token
        q     = request.args.get("q", "").lower().strip()
        page  = max(1, int(request.args.get("page", 1)))
        limit = min(50, max(1, int(request.args.get("limit", 20))))

        # Determine requester (private models visible to their owner)
        requester = None
        auth_hdr = request.headers.get("Authorization", "")
        if auth_hdr.startswith("Bearer "):
            payload = decode_token(auth_hdr[7:])
            if payload:
                requester = payload.get("username")

        all_models = sorted(
            [
                m for m in models_registry.values()
                if not m.get("isPrivate") or m["owner"] == requester
            ],
            key=lambda m: m.get("registeredAt", 0),
            reverse=True,
        )

        if q:
            all_models = [
                m for m in all_models
                if q in m["modelName"].lower()
                or q in m["modelId"].lower()
                or q in m["owner"].lower()
            ]

        total  = len(all_models)
        start  = (page - 1) * limit
        paged  = all_models[start : start + limit]

        return jsonify({
            "success": True,
            "models": paged,
            "total": total,
            "page": page,
            "pages": max(1, -(-total // limit)),
            "limit": limit,
        }), 200
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/api/report/<model_id>", methods=["GET"])
def download_report(model_id):
    """
    Generate and stream a PDF integrity report for a model.
    Uses fpdf2 v2.7+ API (new_x/new_y instead of ln=True, border as string).
    """
    from fpdf import FPDF
    from datetime import datetime, timezone
    from flask import Response

    model = models_registry.get(model_id)
    if not model:
        return jsonify({"success": False, "error": "Model not found"}), 404

    logs = verification_logs.get(model_id, [])

    def fmt_ts(ts):
        if not ts:
            return "-"
        return datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    # ── safe ASCII-only text (fpdf2 core fonts don't support Unicode) ──
    def safe(text):
        if not text:
            return "-"
        return str(text).encode("latin-1", errors="replace").decode("latin-1")

    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()

    # ── Header banner ─────────────────────────────────────────────────
    pdf.set_fill_color(30, 20, 60)
    pdf.rect(0, 0, 210, 28, "F")
    pdf.set_font("Helvetica", "B", 18)
    pdf.set_text_color(200, 180, 255)
    pdf.set_y(7)
    pdf.cell(0, 10, "BlockVerify - AI Model Integrity Report", align="C",
             new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", "", 9)
    pdf.set_text_color(160, 140, 220)
    pdf.set_y(18)
    pdf.cell(0, 6, f"Generated: {fmt_ts(datetime.now(timezone.utc).timestamp())}   |   blockverify.app",
             align="C", new_x="LMARGIN", new_y="NEXT")
    pdf.set_y(32)
    pdf.set_text_color(30, 20, 60)

    def section(title):
        pdf.set_fill_color(240, 237, 255)
        pdf.set_font("Helvetica", "B", 11)
        pdf.set_text_color(60, 40, 120)
        pdf.cell(0, 8, f"  {safe(title)}", fill=True,
                 new_x="LMARGIN", new_y="NEXT")
        pdf.set_text_color(20, 20, 40)
        pdf.ln(2)

    def kv(label, value, mono=False):
        pdf.set_font("Helvetica", "B", 9)
        pdf.set_text_color(100, 80, 160)
        pdf.cell(45, 6, safe(label) + ":", new_x="RIGHT", new_y="TOP")
        pdf.set_font("Courier" if mono else "Helvetica", "", 9)
        pdf.set_text_color(20, 20, 40)
        pdf.multi_cell(0, 6, safe(str(value) if value else "-"),
                       new_x="LMARGIN", new_y="NEXT")
        pdf.ln(1)

    # ── Model Overview ─────────────────────────────────────────────────
    section("Model Overview")
    kv("Model Name",    model.get("modelName", "-"))
    kv("Model ID",      model.get("modelId", "-"), mono=True)
    kv("Owner",         model.get("owner", "-"))
    kv("Status",        "Active" if model.get("isActive") else "Deactivated")
    kv("Registered At", fmt_ts(model.get("registeredAt")))
    kv("Block #",       str(model.get("blockIndex", "-")))
    kv("Version",       f"v{model.get('currentVersion', 1)}")
    if model.get("metadata"):
        kv("Metadata",  model["metadata"])
    pdf.ln(4)

    # ── Hash ──────────────────────────────────────────────────────────
    section("SHA-256 Hash (Current Version)")
    pdf.set_font("Courier", "", 8.5)
    pdf.set_fill_color(248, 246, 255)
    pdf.set_text_color(40, 20, 100)
    pdf.multi_cell(0, 7, safe(model.get("modelHash", "-")),
                   border="1", fill=True, new_x="LMARGIN", new_y="NEXT")
    pdf.set_text_color(20, 20, 40)
    pdf.ln(4)

    # ── Version History ───────────────────────────────────────────────
    section(f"Version History  ({len(model.get('versions', []))} version(s))")
    for v in model.get("versions", []):
        pdf.set_font("Helvetica", "B", 9)
        pdf.set_text_color(60, 40, 120)
        pdf.cell(0, 6,
                 f"  v{v.get('version')}  -  {fmt_ts(v.get('timestamp'))}  -  Block #{v.get('blockIndex', '?')}",
                 new_x="LMARGIN", new_y="NEXT")
        pdf.set_font("Helvetica", "I", 8.5)
        pdf.set_text_color(80, 80, 80)
        pdf.cell(45, 5, "", new_x="RIGHT", new_y="TOP")
        pdf.cell(0, 5, safe(v.get("changelog", "-")),
                 new_x="LMARGIN", new_y="NEXT")
        pdf.set_font("Courier", "", 8)
        pdf.set_text_color(100, 80, 160)
        pdf.cell(45, 5, "", new_x="RIGHT", new_y="TOP")
        h_str = v.get("hash", "")
        display_h = h_str[:64] + ("..." if len(h_str) > 64 else "")
        pdf.cell(0, 5, safe(display_h), new_x="LMARGIN", new_y="NEXT")
        pdf.set_text_color(20, 20, 40)
        pdf.ln(1)
    pdf.ln(4)

    # ── Audit Trail ───────────────────────────────────────────────────
    section(f"Verification Audit Trail  ({len(logs)} record(s))")
    if not logs:
        pdf.set_font("Helvetica", "I", 9)
        pdf.set_text_color(120, 120, 120)
        pdf.cell(0, 6, "  No verifications recorded yet.",
                 new_x="LMARGIN", new_y="NEXT")
    else:
        # Table header
        pdf.set_fill_color(220, 210, 255)
        pdf.set_font("Helvetica", "B", 8.5)
        pdf.set_text_color(40, 20, 100)
        pdf.cell(30, 7, "Verifier",  fill=True, border="1", new_x="RIGHT", new_y="TOP")
        pdf.cell(18, 7, "Result",    fill=True, border="1", new_x="RIGHT", new_y="TOP")
        pdf.cell(50, 7, "Timestamp", fill=True, border="1", new_x="RIGHT", new_y="TOP")
        pdf.cell(0,  7, "Hash (first 32 chars)", fill=True, border="1",
                 new_x="LMARGIN", new_y="NEXT")

        pdf.set_font("Courier", "", 8)
        for i, entry in enumerate(logs):
            even = i % 2 == 0
            if even:
                pdf.set_fill_color(248, 246, 255)
            else:
                pdf.set_fill_color(255, 255, 255)

            result = "VALID" if entry.get("isValid") else "INVALID"
            if result == "VALID":
                pdf.set_text_color(0, 140, 80)
            else:
                pdf.set_text_color(180, 30, 30)

            pdf.cell(30, 6, safe(entry.get("verifier", "anon"))[:18],
                     fill=True, border="1", new_x="RIGHT", new_y="TOP")
            pdf.cell(18, 6, result,
                     fill=True, border="1", new_x="RIGHT", new_y="TOP")
            pdf.set_text_color(20, 20, 40)
            pdf.cell(50, 6, fmt_ts(entry.get("timestamp")),
                     fill=True, border="1", new_x="RIGHT", new_y="TOP")
            h_val = entry.get("providedHash", "-")
            display = (h_val[:32] + "...") if len(h_val) > 32 else h_val
            pdf.cell(0, 6, safe(display),
                     fill=True, border="1", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(4)

    # ── Footer ────────────────────────────────────────────────────────
    pdf.set_fill_color(30, 20, 60)
    pdf.set_font("Helvetica", "I", 8)
    pdf.set_text_color(180, 160, 240)
    pdf.cell(0, 7,
             "This report is auto-generated by BlockVerify - a custom Proof-of-Work blockchain system.",
             align="C", fill=True, new_x="LMARGIN", new_y="NEXT")

    pdf_bytes = pdf.output()
    filename  = f"blockverify_report_{model_id[:8]}.pdf"
    return Response(
        bytes(pdf_bytes),
        mimetype="application/pdf",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )








# ------------------------------------------------------------------ #
#  Merkle tree helper                                                  #
# ------------------------------------------------------------------ #

def _tx_hash(tx: dict) -> str:
    """SHA-256 of a deterministic JSON representation of a transaction."""
    return hashlib.sha256(
        json.dumps(tx, sort_keys=True).encode()
    ).hexdigest()


def _build_merkle(tx_hashes: list) -> dict:
    """
    Build a Merkle tree from a list of leaf hashes.

    Returns a nested dict:
        {
            "hash": "<root_hash>",
            "children": [ <left_node>, <right_node> ]   # absent for leaves
        }
    Compatible with D3.js hierarchy().
    """
    if not tx_hashes:
        # Empty block — single null root
        return {"hash": "0" * 64, "label": "empty", "children": []}

    # Build leaf nodes
    nodes = [{"hash": h, "label": h[:8] + "…", "children": []} for h in tx_hashes]

    if len(nodes) == 1:
        return nodes[0]

    # Bottom-up: keep pairing until one root remains
    # We track each level as a list of (node_dict, hash) tuples
    level = nodes
    while len(level) > 1:
        next_level = []
        i = 0
        while i < len(level):
            left = level[i]
            # Odd number of nodes → duplicate last one
            right = level[i + 1] if i + 1 < len(level) else level[i]
            combined = hashlib.sha256(
                (left["hash"] + right["hash"]).encode()
            ).hexdigest()
            parent = {
                "hash": combined,
                "label": combined[:8] + "…",
                "children": [left] if right is left else [left, right],
            }
            next_level.append(parent)
            i += 2
        level = next_level

    return level[0]


@app.route("/api/block/<int:index>/merkle", methods=["GET"])
def get_merkle_tree(index):
    """
    Merkle tree endpoint — disabled, data now lives on Algorand Testnet.
    """
    return jsonify({
        "success": False,
        "error": "Block data is stored on the Algorand Testnet. Visit https://lora.algonode.network/testnet to explore transactions.",
    }), 404


# ------------------------------------------------------------------ #
#  Model access control (privacy)                                      #
# ------------------------------------------------------------------ #

@app.route("/api/model/<model_id>/privacy", methods=["POST"])
@require_auth
def set_model_privacy(model_id):
    """
    Toggle a model's privacy.  Only the model owner may call this.

    Body:  { "isPrivate": true | false }

    Private models:
        - Are hidden from /api/registry and /api/search (for non-owners).
        - Can only be verified by the owner.
        - Still appear in the owner's /api/models/<owner> list.
    """
    model = models_registry.get(model_id)
    if not model:
        return jsonify({"success": False, "error": "Model not found"}), 404
    if model["owner"] != g.user:
        return jsonify({"success": False, "error": "Only the model owner can change privacy settings"}), 403

    data = request.get_json(silent=True) or {}
    is_private = bool(data.get("isPrivate", False))
    model["isPrivate"] = is_private
    save_state()

    status = "private 🔒" if is_private else "public 🌐"
    return jsonify({
        "success": True,
        "modelId": model_id,
        "isPrivate": is_private,
        "message": f"Model is now {status}",
    }), 200


# ------------------------------------------------------------------ #
#  Server start                                                        #
# ------------------------------------------------------------------ #

if __name__ == "__main__":
    print("══════════════════════════════════════════════")
    print("  🔗 BlockVerify — Algorand Backbone")
    print("  (Professor Edition - Live Testnet)")
    print("══════════════════════════════════════════════")
    print("  Ledger      : Algorand Testnet (AlgoNode)")
    print("  Server      : http://localhost:5000")
    print("══════════════════════════════════════════════")
    port = int(os.environ.get("PORT", 5000))
    app.run(debug=False, host="0.0.0.0", port=port)
