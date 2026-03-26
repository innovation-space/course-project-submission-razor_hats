# BlockVerify System Architecture

## Overview

BlockVerify is a three-layer application: a browser-based frontend communicates over HTTP/JSON with a Flask REST API, which delegates all blockchain operations to a custom Python blockchain engine. All state is held in memory.

```
┌───────────────────────────────────────────┐
│       Frontend (HTML / CSS / JS)          │
│  File upload, SHA-256 hashing,            │
│  UI tabs, blockchain explorer             │
└──────────────┬────────────────────────────┘
               │ fetch() — JSON over HTTP
               ▼
┌───────────────────────────────────────────┐
│       Flask REST API  (app.py)            │
│  Route handlers, input validation,        │
│  business logic, CORS                     │
└──────────────┬────────────────────────────┘
               │ Python function calls
               ▼
┌───────────────────────────────────────────┐
│  Custom Blockchain  (blockchain.py)       │
│  Block class, Blockchain class,           │
│  proof-of-work, chain validation          │
└──────────────┬────────────────────────────┘
               │
               ▼
┌───────────────────────────────────────────┐
│     In-Memory Storage                     │
│  blockchain.chain  (list of Block)        │
│  models_registry   (dict)                 │
│  verification_logs (dict)                 │
└───────────────────────────────────────────┘
```

## Layer Details

### Frontend

A single HTML file (`frontend/index.html`) with embedded CSS and JavaScript. It computes SHA-256 hashes entirely in the browser using the Web Crypto API (`crypto.subtle.digest`), so model files never leave the user's machine. User identity is a simple text username — there is no wallet or key-pair management.

### Flask API

The API (`backend/app.py`) exposes RESTful endpoints for registration, verification, version management, and blockchain queries. Every write operation (register, verify, add-version) creates a blockchain transaction, adds it to the pending pool, and mines a new block via proof-of-work before returning a response.

### Custom Blockchain

The blockchain engine (`backend/blockchain.py`) implements two classes. The `Block` class stores data and computes SHA-256 hashes, and implements proof-of-work mining. The `Blockchain` class manages the chain, creates the genesis block, handles the pending transaction pool, performs mining, and validates chain integrity.

## Data Flow — Registration

1. User selects a file in the browser.
2. Browser computes SHA-256(file) → 64-char hex string.
3. Frontend sends POST /api/register with name, hash, owner.
4. Flask creates a transaction dict and adds it to pending pool.
5. `mine_pending_transactions()` creates a new Block, runs proof-of-work.
6. Mined block is appended to the chain.
7. Model metadata stored in `models_registry` dict.
8. Response returns modelId and blockIndex.

## Data Flow — Verification

1. User uploads the same (or different) file.
2. Browser computes SHA-256 → hex.
3. Frontend sends POST /api/verify with modelId and hash.
4. Flask compares provided hash with stored hash.
5. Result (valid/invalid) is recorded as a transaction and mined into a block.
6. Verification record appended to `verification_logs`.
7. Response returns isValid boolean plus both hashes for comparison.

## Security Model

All security stems from the blockchain properties: SHA-256 hashing makes tampering detectable, proof-of-work makes re-mining expensive, chain linking propagates any break forward through the chain, and validation walks the entire chain to verify integrity. Input validation on every API endpoint prevents malformed requests.
