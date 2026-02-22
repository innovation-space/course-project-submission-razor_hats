# 🔗 BlockVerify — AI Model Integrity Verification System

[![Solidity](https://img.shields.io/badge/Solidity-0.8.19-blue)](https://docs.soliditylang.org/)
[![Hardhat](https://img.shields.io/badge/Hardhat-2.22-yellow)](https://hardhat.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-green)](LICENSE)
[![Polygon Amoy](https://img.shields.io/badge/Network-Polygon%20Amoy-purple)](https://amoy.polygonscan.com/)

**BlockVerify** is a blockchain-based platform that ensures AI models remain authentic and untampered throughout their lifecycle. It stores cryptographic fingerprints (SHA-256 hashes) of trained AI models on the Polygon blockchain to provide immutable proof of integrity, version history tracking, and verification audit trails.

---
## Members

 23BKT0059 - Shubhangam Singh
 23BKT0073 - Mihir Dixit
 23BKT0091 - Aditya Kumar 

---
## 📖 Table of Contents

- [Problem Statement](#-problem-statement)
- [Solution](#-solution)
- [Features](#-features)
- [Architecture](#-architecture)
- [Tech Stack](#-tech-stack)
- [Quick Start](#-quick-start)
- [Smart Contract API](#-smart-contract-api)
- [Frontend](#-frontend)
- [Testing](#-testing)
- [Deployment](#-deployment)
- [Team](#-team)
- [License](#-license)

---

## 🎯 Problem Statement

AI models are vulnerable to tampering at multiple stages:

- **Distribution** — Models can be modified during transfer between systems
- **Deployment** — Unauthorized changes before production use
- **Execution** — Runtime model substitution attacks
- **Updates** — Version confusion and rollback attacks

In high-stakes domains like healthcare diagnostics, autonomous vehicles, and financial fraud detection, there is no decentralized, transparent mechanism to verify that the model running in production is exactly the model that was trained and audited.

## 💡 Solution

BlockVerify stores only the cryptographic hash and metadata of each AI model on-chain (keeping actual model files off-chain), enabling:

1. **Registration** — Compute SHA-256 hash of a model artifact and record it immutably on the blockchain
2. **Verification** — Before deploying or executing a model, re-hash it and compare against the on-chain record
3. **Version Tracking** — Maintain a complete, tamper-proof history of all model versions
4. **Audit Trail** — Every verification attempt is logged on-chain with timestamps and results

---

## ✨ Features

| Feature | Description |
|---|---|
| Model Registration | Store model hash, name, and metadata on-chain |
| Integrity Verification | Compare a model file's hash against the blockchain record |
| Version History | Immutable log of every model version with changelogs |
| Audit Trail | Every verification attempt is recorded on-chain |
| Batch Registration | Register up to 20 models in a single transaction |
| Role-Based Access Control | Admin, Auditor, and Model Owner roles via OpenZeppelin |
| Emergency Pause | Admin can halt all state-changing operations |
| Ownership Transfer | Transfer model ownership between addresses |
| Model Deactivation / Reactivation | Soft-delete and restore models |

---

## 🏗 Architecture

```
┌─────────────────────────────────────────────────────────┐
│              User Interface (HTML + JS)                  │
│  File Upload → SHA-256 Hash → MetaMask Tx Signing       │
└─────────────────────┬───────────────────────────────────┘
                      │ ethers.js v6
                      ▼
┌─────────────────────────────────────────────────────────┐
│           Polygon Amoy Blockchain                        │
│  BlockVerify.sol (AccessControl + Pausable + ReentrancyGuard) │
│  - registerModel()   - verifyModel()                     │
│  - addVersion()      - batchRegisterModels()             │
│  - deactivateModel() - transferModelOwnership()          │
└─────────────────────────────────────────────────────────┘
```

### Data Flow

**Registration:** File → SHA-256 → keccak256(bytes32) → `registerModel()` → On-chain record + event

**Verification:** File → SHA-256 → keccak256(bytes32) → `verifyModel()` → Match/Mismatch result + audit log

---

## 🛠 Tech Stack

| Layer | Technology |
|---|---|
| Smart Contracts | Solidity 0.8.19, OpenZeppelin v5 |
| Development | Hardhat 2.22 |
| Testing | Mocha, Chai, Hardhat Toolbox |
| Frontend | HTML5, CSS3, ethers.js v6 |
| Wallet | MetaMask |
| Blockchain | Polygon Amoy Testnet |
| Security | AccessControl, Pausable, ReentrancyGuard |

---

## 🚀 Quick Start

### Prerequisites

- Node.js ≥ 18.x
- MetaMask browser extension
- Polygon Amoy testnet MATIC ([faucet](https://faucet.polygon.technology/))

### Installation

```bash
# Clone the repository
git clone https://github.com/innovation-space/course-project-submission-razor_hats.git
cd course-project-submission-razor_hats

# Install dependencies
npm install

# Create environment file
cp .env.example .env
# Edit .env with your private key and RPC URL
```

### Compile

```bash
npx hardhat compile
```

### Test

```bash
# Run all tests
npx hardhat test

# Run with gas reporting
REPORT_GAS=true npx hardhat test

# Run with coverage
npx hardhat coverage
```

### Deploy Locally

```bash
# Start local node
npx hardhat node

# Deploy in another terminal
npx hardhat run scripts/deploy.js --network localhost
```

### Deploy to Polygon Amoy

```bash
npx hardhat run scripts/deploy.js --network polygonAmoy
```

---

## 📜 Smart Contract API

### Core Functions

| Function | Description | Access |
|---|---|---|
| `registerModel(hash, name, metadata)` | Register a new AI model | Anyone |
| `verifyModel(modelId, hash)` | Verify model integrity | Anyone |
| `addVersion(modelId, hash, changeLog)` | Add new version | Model Owner |
| `batchRegisterModels(hashes[], names[], metas[])` | Batch register (max 20) | Anyone |
| `deactivateModel(modelId)` | Soft-delete a model | Model Owner |
| `reactivateModel(modelId)` | Restore a deactivated model | Model Owner |
| `transferModelOwnership(modelId, newOwner)` | Transfer ownership | Model Owner |
| `updateMetadata(modelId, newMetadata)` | Update model metadata | Model Owner |

### View Functions

| Function | Returns |
|---|---|
| `getModel(modelId)` | Full model details (AIModel struct) |
| `getVersionHistory(modelId)` | Array of Version structs |
| `getVerificationLog(modelId)` | Array of VerificationRecord structs |
| `getModelsByOwner(address)` | Array of model IDs |
| `modelExists(modelId)` | Boolean |
| `getCurrentVersion(modelId)` | Version number |
| `getVerificationCount(modelId)` | Number of verifications |

### Admin Functions

| Function | Description |
|---|---|
| `pause()` | Emergency halt all state-changing operations |
| `unpause()` | Resume normal operations |

### Events

- `ModelRegistered(modelId, owner, name, hash, timestamp)`
- `ModelVerified(modelId, verifier, isValid, timestamp)`
- `VersionAdded(modelId, version, newHash, changeLog, timestamp)`
- `ModelDeactivated(modelId, deactivatedBy, timestamp)`
- `ModelReactivated(modelId, reactivatedBy, timestamp)`
- `OwnershipTransferred(modelId, previousOwner, newOwner, timestamp)`
- `BatchRegistered(owner, count, timestamp)`

---

## 🖥 Frontend

The web interface (`frontend/index.html`) provides:

- **Connect Wallet** — MetaMask integration
- **Register** — Upload file, compute hash, register on-chain
- **Verify** — Upload file, enter Model ID, check integrity
- **Versions** — View version history and add new versions
- **Audit Trail** — View all verification attempts
- **My Models** — Dashboard of your registered models

### Running the Frontend

After deployment, update `CONTRACT_ADDRESS` in `frontend/index.html`, then open the file in a browser with MetaMask installed.

---

## 🧪 Testing

### Test Categories

- **Deployment Tests** — Role setup, initial state
- **Registration Tests** — Valid/invalid inputs, events, counters
- **Verification Tests** — Hash matching, audit logging, edge cases
- **Version Tracking Tests** — Version updates, history, access control
- **Deactivation Tests** — Deactivate, reactivate, permissions
- **Ownership Transfer Tests** — Transfer, permissions after transfer
- **Batch Registration Tests** — Multiple models, size limits
- **Pause Tests** — Emergency stop, resume
- **Gas Optimization Tests** — Gas usage within limits
- **Full Lifecycle Integration** — End-to-end model lifecycle

### Running Tests

```bash
npx hardhat test                    # All tests
REPORT_GAS=true npx hardhat test    # With gas report
npx hardhat coverage                # Coverage report
```

---

## 🚢 Deployment

### Polygon Amoy Testnet

1. Get testnet MATIC from the [Polygon faucet](https://faucet.polygon.technology/)
2. Configure `.env` with your private key
3. Run `npx hardhat run scripts/deploy.js --network polygonAmoy`
4. Verify: `npx hardhat verify --network polygonAmoy <CONTRACT_ADDRESS>`

### Deployed Contract

| Network | Address |
|---|---|
| Polygon Amoy | *Update after deployment* |

---

## 👥 Team

**Team Name:** razor_hats

| Member | Role |
|---|---|
| Member 1 | Smart Contract Development |
| Member 2 | Frontend & Testing |
| Member 3 | Documentation & Deployment |

---

## 📄 License

This project is licensed under the MIT License — see [LICENSE](LICENSE) for details.

---

## 🙏 Acknowledgments

- [OpenZeppelin](https://openzeppelin.com/) for secure contract libraries
- [Hardhat](https://hardhat.org/) for the development framework
- [Polygon](https://polygon.technology/) for the testnet infrastructure
- Professor @manoov for course guidance
