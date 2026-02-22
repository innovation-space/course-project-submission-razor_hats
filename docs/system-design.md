# BlockVerify System Design

BlockVerify is engineered to establish a decentralized and mathematically secure root of trust for AI models. By mapping the lifecycle of an AI model to an Ethereum smart contract interface, we ensure absolute transparency. Below is the high-level architecture and system design detailing how the various components interact.

## High-Level Architecture Diagram

```ascii
+-----------------------+
|  AI Engineer/User     |  <-- Initiates hash generation of local AI model & clicks "Verify/Register"
+----------+------------+
           |
           v
+-----------------------+
|  React Frontend WebUI |  <-- Web interface for viewing dashboards and triggering actions
+----------+------------+      (Calculates SHA-256 locally using CryptoJS/WebCrypto)
           |
           v
+-----------------------+
|  MetaMask Extension   |  <-- Injected Web3 Provider handling cryptographic signing & wallet keys
+----------+------------+
           | 
           |  (JSON-RPC over HTTPS/WSS)
           v
+-----------------------+
|  Ethereum Blockchain  |  <-- Decentralized Node Network (e.g. Infura/Alchemy or local Hardhat)
|                       |
|  +-----------------+  |
|  | BlockVerify.sol |  |  <-- Smart Contract enforcing logic, state changes, and RBAC
|  +-----------------+  |
+-----------------------+
```

## Data Flow Explanation

1. **Model Finalization**: An AI Engineer finalizes training a model (e.g., `model.pt`). The model's binary remains securely stored on either an internal company server, AWS S3, or IPFS.
2. **Local Hashing**: The Engineer hashes the resulting binary file using a secure, client-side SHA-256 implementation on the BlockVerify frontend.
3. **Transaction Signing**: The frontend builds a transaction object aimed at the `BlockVerify.sol` smart contract (e.g., calling `registerModel` with the computed hash). MetaMask intercepts this, prompting the user for cryptographic approval and gas fees.
4. **Blockchain Execution**: The transaction routes to an Ethereum miner/validator. The smart contract updates its state to append the new hash-chain securely and immutably.
5. **Client Verification**: When a client application later wishes to use the AI model, they compute the SHA-256 hash of their local model payload, call the `verifyModel` read-only logic via public nodes, and receive absolute confirmation of whether the hash matches the legitimate, registered state-on-chain.

## Security Considerations

- **Private Key Management**: The system is only as secure as the private keys of the Model Owners. If an owner's MetaMask account is compromised, the attacker can push malicious version updates using `addVersion`. Multi-Signature (MultiSig) wallets should be used for production administration.
- **Client-Side Hashing**: The SHA-256 hash must be computed strictly on the client side (or a highly secure build pipeline). Sending the raw model to an intermediary backend to perform the hash exposes it to man-in-the-middle manipulation.
- **Gas Limit Vulnerabilities**: On-chain arrays (such as version histories) can grow indefinitely. Queries must be paginated to avoid exceeding block gas limits and creating denial-of-service conditions.
- **Reentrancy**: Standard Solidity security practices are employed. All state changes are executed before external calls (CEI pattern), neutralizing reentrancy attacks.

## Role Hierarchy

BlockVerify relies on Role-Based Access Control (RBAC) enforced intrinsically via the Smart Contract.

1. **Admin (Superuser)**
   - Usually a DAO or the core deployer of the multi-tenant contract.
   - Can pause the entire contract in an emergency using standard `Pausable` mechanics.
   - Can forcefully deactivate models that are confirmed to contain malware/illegal structures.

2. **Model Owner**
   - The address that instantiated (`registerModel`) the specific model, or received ownership via `transferModelOwnership`.
   - Has exclusive rights to call `addVersion`, `deactivateModel`, and `reactivateModel`.

3. **Auditor**
   - A specialized, read-only authorized role (typically regulatory bodies or automated verification pipelines).
   - Granted exclusive rights to view deep tracking data, such as accessing `getVerificationLog()`.

4. **Public Entities**
   - Anyone connected to the blockchain.
   - Can freely call read-only functions like `verifyModel`, `getModel`, and `getVersionHistory` without permission.
