# BlockVerify Smart Contract API Reference

The `BlockVerify.sol` smart contract provides the core mechanisms for anchoring AI model hashes to the Ethereum blockchain, ensuring their immutability. Below is the documentation for all public functions available in the contract.

---

### `registerModel(string memory _modelHash, string memory _modelName)`
Registers a new AI model on the blockchain with an initial version.
- **Purpose**: Creates the primary record for a new AI model.
- **Parameters**: 
  - `_modelHash` (string): The SHA-256 hash of the initial model file.
  - `_modelName` (string): A human-readable identifier for the model.
- **Return Values**: 
  - `uint256`: The assigned, unique `modelId` for the freshly registered model.
- **Access Control**: Anyone (Caller becomes the Model Owner).
- **Example Usage**:
  ```solidity
  uint256 newModelId = blockVerify.registerModel("e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855", "FraudDetection_v1");
  ```

---

### `verifyModel(uint256 _modelId, string memory _providedHash)`
Verifies if a provided SHA-256 hash matches the current active version of a registered model.
- **Purpose**: Allows consumers to mathematical prove that their local model copy is untampered.
- **Parameters**: 
  - `_modelId` (uint256): The unique ID of the registered model.
  - `_providedHash` (string): The SHA-256 hash computed from the local model file.
- **Return Values**: 
  - `bool`: `true` if the hashes match and the model is active, `false` otherwise.
- **Access Control**: Anyone.
- **Example Usage**:
  ```solidity
  bool isValid = blockVerify.verifyModel(1, "e3b0c44298fc1c149...");
  ```

---

### `addVersion(uint256 _modelId, string memory _newModelHash, string memory _versionData)`
Publishes a new version or update for an existing, registered model.
- **Purpose**: Iterates a model's lifecycle while maintaining a trail of previous valid hashes.
- **Parameters**: 
  - `_modelId` (uint256): The unique ID of the model.
  - `_newModelHash` (string): The SHA-256 hash of the updated model file.
  - `_versionData` (string): Optional metadata (e.g., "v2.0: optimized weights").
- **Return Values**: None.
- **Access Control**: Restricted to Model Owner.
- **Example Usage**:
  ```solidity
  blockVerify.addVersion(1, "b5a7c442...", "v2.0 Release");
  ```

---

### `deactivateModel(uint256 _modelId)`
Temporarily or permanently flags a model as inactive.
- **Purpose**: Prevents further version additions and causes `verifyModel` to return false. Used when a model is deprecated or discovered to be flawed.
- **Parameters**: 
  - `_modelId` (uint256): The ID of the model to deactivate.
- **Return Values**: None.
- **Access Control**: Restricted to Model Owner or Admin.
- **Example Usage**:
  ```solidity
  blockVerify.deactivateModel(1);
  ```

---

### `reactivateModel(uint256 _modelId)`
Re-enables a previously deactivated model.
- **Purpose**: Restores verification capabilities for a model that was temporarily suspended.
- **Parameters**: 
  - `_modelId` (uint256): The ID of the model to reactivate.
- **Return Values**: None.
- **Access Control**: Restricted to Model Owner or Admin.
- **Example Usage**:
  ```solidity
  blockVerify.reactivateModel(1);
  ```

---

### `transferModelOwnership(uint256 _modelId, address _newOwner)`
Transfers the administrative rights of a model to a new Ethereum address.
- **Purpose**: Enables the transfer of assets or delegation of maintenance to other teams/wallets.
- **Parameters**: 
  - `_modelId` (uint256): The ID of the model being transferred.
  - `_newOwner` (address): The Ethereum address of the incoming owner.
- **Return Values**: None.
- **Access Control**: Restricted to current Model Owner.
- **Example Usage**:
  ```solidity
  blockVerify.transferModelOwnership(1, 0x1234567890123456789012345678901234567890);
  ```

---

### `getModel(uint256 _modelId)`
Retrieves the metadata and current state of a specific model.
- **Purpose**: Fetches basic read-only details about a model for the frontend interfaces.
- **Parameters**: 
  - `_modelId` (uint256): The ID of the model.
- **Return Values**: 
  - `modelName` (string)
  - `owner` (address)
  - `isActive` (bool)
  - `currentHash` (string)
  - `versionCount` (uint256)
- **Access Control**: Anyone.
- **Example Usage**:
  ```solidity
  (string memory name, address owner, bool active, string memory hash, uint256 count) = blockVerify.getModel(1);
  ```

---

### `getModelsByOwner(address _owner)`
Retrieves an array of model IDs owned by a specific address.
- **Purpose**: Used for rendering user dashboards to display all models they manage.
- **Parameters**: 
  - `_owner` (address): The wallet address to query.
- **Return Values**: 
  - `uint256[]`: An array of associated model IDs.
- **Access Control**: Anyone.
- **Example Usage**:
  ```solidity
  uint256[] memory myModels = blockVerify.getModelsByOwner(msg.sender);
  ```

---

### `getVersionHistory(uint256 _modelId)`
Fetches the complete historical array of hashes and updates for a model.
- **Purpose**: Provides the immutable audit trail verifying how an AI model evolved.
- **Parameters**: 
  - `_modelId` (uint256): The ID of the requested model.
- **Return Values**: 
  - `Version[]`: An array of Version structs (containing hash, timestamp, and versionData).
- **Access Control**: Anyone.
- **Example Usage**:
  ```solidity
  Version[] memory history = blockVerify.getVersionHistory(1);
  ```

---

### `getVerificationLog(uint256 _modelId)`
Retrieves a log of all `verifyModel` requests made for a specific model (if tracking is enabled).
- **Purpose**: Allows model owners to see how often and when their model is being verified in production.
- **Parameters**: 
  - `_modelId` (uint256): The relevant model ID.
- **Return Values**: 
  - `VerificationRecord[]`: An array detailing the caller address, timestamp, and result (success/fail).
- **Access Control**: Restricted to Auditor or Model Owner.
- **Example Usage**:
  ```solidity
  VerificationRecord[] memory logs = blockVerify.getVerificationLog(1);
  ```
