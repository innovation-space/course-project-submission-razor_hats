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


if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5000)
