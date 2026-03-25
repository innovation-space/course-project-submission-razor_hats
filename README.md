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

## 📦 Installation & Running

### Backend

```bash
cd backend
pip install -r requirements.txt
python app.py
```

Server starts at `http://localhost:5000`

### Frontend

```bash
cd frontend
python3 -m http.server 3000
```

Open `http://localhost:3000` in your browser.

---

## 🎮 How to Use

1. **Enter your username** in the header (e.g. "alice")
2. **Register Model** → Upload AI model file → SHA-256 hash computed → stored on blockchain
3. **Verify Model** → Upload same file later → compare hash → integrity confirmed or denied
4. **Explore Blockchain** → View all blocks with hashes, nonces, and transactions
5. **Validate Chain** → Prove the blockchain hasn't been tampered with

---

## 🧪 Testing

```bash
cd backend
pytest tests/ -v                          # Run all tests
pytest tests/ -v --cov=. --cov-report=term-missing   # With coverage
pytest tests/ --cov=. --cov-report=html   # HTML coverage report
```

---

## 📊 Project Structure

```
blockverify/
├── backend/
│   ├── app.py                  # Flask REST API
│   ├── blockchain.py           # Custom blockchain (Block + Blockchain)
│   ├── requirements.txt
│   └── tests/
│       ├── test_blockchain.py  # Blockchain core tests
│       └── test_api.py         # API endpoint tests
├── frontend/
│   └── index.html              # Complete web UI
├── docs/
│   ├── ARCHITECTURE.md
│   ├── BLOCKCHAIN_CONCEPTS.md
│   └── API_REFERENCE.md
├── README.md
├── .gitignore
└── LICENSE
```

---

## 🔐 Security Features

- **SHA-256 Hashing** — Cryptographic fingerprint for every block
- **Proof-of-Work** — Computational cost prevents tampering (difficulty 4)
- **Chain Linking** — Each block references the previous block's hash
- **Tamper Detection** — Validation walks the entire chain and detects modifications
- **Immutable Audit Trail** — Every verification event is logged on-chain

---

## 📈 Blockchain Concepts Demonstrated

1. **Block Structure** — index, timestamp, transactions, previous_hash, nonce, hash
2. **Proof-of-Work Mining** — Find nonce that produces hash with N leading zeros
3. **Chain Linking** — previous_hash creates a tamper-evident linked list
4. **Validation** — Walk chain to verify hashes and links
5. **Immutability** — Modifying any block breaks all subsequent blocks

See [docs/BLOCKCHAIN_CONCEPTS.md](docs/BLOCKCHAIN_CONCEPTS.md) for detailed explanations.

---

## 👥 Team

**Team Name:** razor_hats

---

## 📚 References

- Nakamoto, S. (2008). *Bitcoin: A Peer-to-Peer Electronic Cash System*
- Narayanan et al. (2016). *Bitcoin and Cryptocurrency Technologies*. Princeton University Press
- NIST (2015). *Secure Hash Standard (SHS)*. FIPS PUB 180-4

---

## 📄 License

MIT License — see [LICENSE](LICENSE).

## 🙏 Acknowledgments

- Professor @manoov — Course Instructor
- BCSE324L Foundations of Blockchain Technology, VIT
