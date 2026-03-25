# BlockVerify API Reference

Base URL: `http://localhost:5000/api`

All responses are JSON. Write endpoints mine a new block (takes 1-5 seconds).

## Write Endpoints

### POST /api/register
Register a new AI model.

Request: `{"modelName": "ResNet50-v1", "modelHash": "abc123...", "metadata": "optional", "owner": "alice"}`

Success (200): `{"success": true, "modelId": "a1b2c3d4...", "blockIndex": 5, "message": "..."}`

Errors: 400 (missing fields), 500 (server error)

### POST /api/verify
Verify model integrity against stored hash.

Request: `{"modelId": "a1b2c3d4...", "providedHash": "xyz789...", "verifier": "bob"}`

Success (200): `{"success": true, "isValid": true/false, "message": "...", "blockIndex": 6, "storedHash": "...", "providedHash": "..."}`

Errors: 400 (missing fields), 404 (model not found)

### POST /api/add-version
Add new version to existing model (owner only).

Request: `{"modelId": "...", "newHash": "...", "changelog": "Fixed preprocessing bug", "owner": "alice"}`

Success (200): `{"success": true, "version": 2, "blockIndex": 7, "message": "..."}`

Errors: 400, 403 (not owner), 404 (not found)

### POST /api/deactivate
Soft-delete a model (owner only).

Request: `{"modelId": "...", "owner": "alice"}`

Success (200): `{"success": true, "message": "Model deactivated"}`

## Read Endpoints

### GET /api/models/:owner
All models by owner. Returns `{"success": true, "models": [...], "count": N}`

### GET /api/model/:modelId
Single model details. Returns `{"success": true, "model": {...}}`

### GET /api/versions/:modelId
Version history. Returns `{"success": true, "versions": [...], "currentVersion": N}`

### GET /api/audit/:modelId
Verification audit trail. Returns `{"success": true, "verifications": [...], "count": N}`

### GET /api/chain
Full blockchain. Returns `{"success": true, "chain": [...], "length": N}`

### GET /api/chain/validate
Validate chain integrity. Returns `{"success": true, "isValid": true/false, "errors": [...], "message": "..."}`

### GET /api/stats
Platform statistics. Returns `{"totalModels": N, "totalVerifications": N, "totalBlocks": N}`

## Error Format

All errors follow: `{"success": false, "error": "Description"}`

HTTP status codes: 200 (success), 400 (bad request), 403 (forbidden), 404 (not found), 500 (server error)
