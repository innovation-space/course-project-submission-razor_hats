# 🔗 BlockVerify — Custom Blockchain-Based AI Model Integrity Verification

[![Python](https://img.shields.io/badge/Python-3.8%2B-blue)](https://python.org)
[![Flask](https://img.shields.io/badge/Flask-3.x-green)](https://flask.palletsprojects.com/)
[![License: MIT](https://img.shields.io/badge/License-MIT-green)](LICENSE)

**BlockVerify** is a blockchain-based system for verifying AI model integrity through cryptographic hashing. Unlike typical blockchain projects that use existing platforms like Ethereum, this project **builds a custom blockchain from scratch in Python** to demonstrate deep understanding of blockchain fundamentals.

---

## 🚫 Why NOT Ethereum?

This project intentionally avoids Ethereum/Solidity to demonstrate mastery of the underlying computer science:

| Aspect | Ethereum Approach | Our Custom Approach |
|--------|-------------------|---------------------|
| Block Structure | Hidden by platform | Explicitly implemented in Python |
| Mining | Handled by network | Proof-of-work algorithm we wrote |
| Validation | Automatic | Manual validation logic |
| Hashing | keccak256() call | SHA-256 implementation |
| Smart Contracts | Solidity code | Python Flask REST API |
| Learning Outcome | How to use tools | How blockchain works internally |

> **Note:** We initially explored an Ethereum/Solidity approach (see archived branches `feature/smart-contracts` and `feature/documentation`), but pivoted to a custom blockchain to demonstrate deeper understanding of blockchain fundamentals as required by the course.

---

## 🏗 Architecture

```
Frontend (HTML/CSS/JS)
  ↓ fetch() HTTP/JSON
Flask REST API (app.py)
  ↓ Python calls
Custom Blockchain (blockchain.py)
  ↓
In-Memory Storage
```

## 🔧 Tech Stack

**Backend:** Python 3.8+, Flask, flask-cors, hashlib (SHA-256)
**Frontend:** HTML5, CSS3, Vanilla JS, Web Crypto API (SHA-256)
**Testing:** pytest, pytest-cov

---

*More sections coming soon: Installation, Usage, Testing, Project Structure*
