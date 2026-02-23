// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import "@openzeppelin/contracts/access/AccessControl.sol";
import "@openzeppelin/contracts/utils/Pausable.sol";
import "@openzeppelin/contracts/utils/ReentrancyGuard.sol";

/**
 * @title BlockVerify
 * @author razor_hats team
 * @notice AI Model Integrity Verification System
 * @dev Stores cryptographic hashes of AI models on-chain for tamper-proof
 *      integrity verification, version tracking, and audit trail management.
 *
 * Key features:
 *   - Register AI model fingerprints (SHA-256 hashes) on-chain
 *   - Verify model integrity before deployment
 *   - Track complete version lineage
 *   - Maintain immutable verification audit logs
 *   - Role-based access control (Admin, Auditor, Model Owner)
 *   - Emergency pause functionality
 *   - Batch registration support
 */
contract BlockVerify is AccessControl, Pausable, ReentrancyGuard {

    // ============================================================
    //                       CONSTANTS
    // ============================================================

    /// @notice Contract version identifier
    string public constant VERSION = "1.0.0";

    /// @notice Role for platform administrators
    bytes32 public constant ADMIN_ROLE = keccak256("ADMIN_ROLE");

    /// @notice Role for authorized auditors who can query sensitive logs
    bytes32 public constant AUDITOR_ROLE = keccak256("AUDITOR_ROLE");

    /// @notice Maximum number of models in a single batch registration
    uint256 public constant MAX_BATCH_SIZE = 20;

    // ============================================================
    //                      DATA STRUCTURES
    // ============================================================

    /// @notice Represents a registered AI model
    struct AIModel {
        bytes32 modelHash;        // Current SHA-256 hash of the model
        string  modelName;        // Human-readable name
        string  metadata;         // IPFS CID or additional metadata JSON
        address modelOwner;       // Address that owns this model record
        uint256 registeredAt;     // Block timestamp of registration
        uint256 currentVersion;   // Current version number (starts at 1)
        bool    isActive;         // Whether the model is still active
    }

    /// @notice A single version entry in a model's history
    struct Version {
        bytes32 modelHash;        // Hash of this particular version
        uint256 timestamp;        // When this version was recorded
        string  changeLog;        // Human-readable description of changes
        address updatedBy;        // Who submitted this version
    }

    /// @notice A single verification attempt record
    struct VerificationRecord {
        address verifier;         // Who performed the verification
        uint256 timestamp;        // When verification occurred
        bool    isValid;          // Whether the hash matched
        bytes32 providedHash;     // The hash that was checked
    }

    // ============================================================
    //                       STATE VARIABLES
    // ============================================================

    /// @dev Auto-incrementing counter for generating unique model IDs
    uint256 private _modelCounter;

    /// @dev Total number of registered models (including deactivated)
    uint256 public totalModels;

    /// @dev Total number of verification events across all models
    uint256 public totalVerifications;

    // ============================================================
    //                         MAPPINGS
    // ============================================================

    /// @dev modelId => AIModel
    mapping(bytes32 => AIModel) private _models;

    /// @dev modelId => array of Version records
    mapping(bytes32 => Version[]) private _versionHistory;

    /// @dev modelId => array of VerificationRecord entries
    mapping(bytes32 => VerificationRecord[]) private _verificationLog;

    /// @dev owner address => array of modelIds they own
    mapping(address => bytes32[]) private _ownerModels;

    // ============================================================
    //                          EVENTS
    // ============================================================

    /// @notice Emitted when a new AI model is registered
    event ModelRegistered(
        bytes32 indexed modelId,
        address indexed owner,
        string  modelName,
        bytes32 modelHash,
        uint256 timestamp
    );

    /// @notice Emitted when a model's integrity is verified
    event ModelVerified(
        bytes32 indexed modelId,
        address indexed verifier,
        bool    isValid,
        uint256 timestamp
    );

    /// @notice Emitted when a new version is added to a model
    event VersionAdded(
        bytes32 indexed modelId,
        uint256 version,
        bytes32 newHash,
        string  changeLog,
        uint256 timestamp
    );

    /// @notice Emitted when a model is deactivated (soft-deleted)
    event ModelDeactivated(
        bytes32 indexed modelId,
        address indexed deactivatedBy,
        uint256 timestamp
    );

    /// @notice Emitted when a model is reactivated
    event ModelReactivated(
        bytes32 indexed modelId,
        address indexed reactivatedBy,
        uint256 timestamp
    );

    /// @notice Emitted when model ownership is transferred
    event OwnershipTransferred(
        bytes32 indexed modelId,
        address indexed previousOwner,
        address indexed newOwner,
        uint256 timestamp
    );

    /// @notice Emitted when a batch of models is registered
    event BatchRegistered(
        address indexed owner,
        uint256 count,
        uint256 timestamp
    );

    // ============================================================
    //                         ERRORS
    // ============================================================

    error HashCannotBeZero();
    error StringCannotBeEmpty();
    error InvalidAddress();
    error ModelDoesNotExist(bytes32 modelId);
    error ModelNotActive(bytes32 modelId);
    error ModelAlreadyActive(bytes32 modelId);
    error NotModelOwner(bytes32 modelId, address caller);
    error ModelIdCollision(bytes32 modelId);
    error BatchSizeExceeded(uint256 provided, uint256 max);
    error ArrayLengthMismatch();

    // ============================================================
    //                        MODIFIERS
    // ============================================================

    modifier validHash(bytes32 hash) {
        if (hash == bytes32(0)) revert HashCannotBeZero();
        _;
    }

    modifier validString(string memory str) {
        if (bytes(str).length == 0) revert StringCannotBeEmpty();
        _;
    }

    modifier validAddr(address addr) {
        if (addr == address(0)) revert InvalidAddress();
        _;
    }

    modifier existingModel(bytes32 modelId) {
        if (_models[modelId].registeredAt == 0) revert ModelDoesNotExist(modelId);
        _;
    }

    modifier activeModel(bytes32 modelId) {
        if (!_models[modelId].isActive) revert ModelNotActive(modelId);
        _;
    }

    modifier onlyModelOwner(bytes32 modelId) {
        if (_models[modelId].modelOwner != msg.sender) revert NotModelOwner(modelId, msg.sender);
        _;
    }

    // ============================================================
    //                       CONSTRUCTOR
    // ============================================================

    /**
     * @notice Deploy BlockVerify and set up initial roles
     * @dev The deployer receives DEFAULT_ADMIN_ROLE and ADMIN_ROLE
     */
    constructor() {
        _grantRole(DEFAULT_ADMIN_ROLE, msg.sender);
        _grantRole(ADMIN_ROLE, msg.sender);
        _grantRole(AUDITOR_ROLE, msg.sender);
    }

    // ============================================================
    //                     CORE FUNCTIONS
    // ============================================================

    /**
     * @notice Register a new AI model on-chain
     * @param _modelHash  SHA-256 hash (as bytes32) of the model artifact
     * @param _modelName  Human-readable model name
     * @param _metadata   IPFS CID or JSON metadata string
     * @return modelId    Unique identifier for the registered model
     */
    function registerModel(
        bytes32 _modelHash,
        string calldata _modelName,
        string calldata _metadata
    )
        external
        whenNotPaused
        nonReentrant
        validHash(_modelHash)
        validString(_modelName)
        returns (bytes32 modelId)
    {
        modelId = _generateModelId(_modelHash, msg.sender);

        if (_models[modelId].registeredAt != 0) {
            revert ModelIdCollision(modelId);
        }

        _models[modelId] = AIModel({
            modelHash:      _modelHash,
            modelName:      _modelName,
            metadata:       _metadata,
            modelOwner:     msg.sender,
            registeredAt:   block.timestamp,
            currentVersion: 1,
            isActive:       true
        });

        _ownerModels[msg.sender].push(modelId);
        totalModels++;

        // Seed the version history with the initial registration
        _versionHistory[modelId].push(Version({
            modelHash: _modelHash,
            timestamp: block.timestamp,
            changeLog: "Initial registration",
            updatedBy: msg.sender
        }));

        emit ModelRegistered(modelId, msg.sender, _modelName, _modelHash, block.timestamp);

        return modelId;
    }

    /**
     * @notice Register multiple models in a single transaction
     * @param _modelHashes Array of model hashes
     * @param _modelNames  Array of model names
     * @param _metadatas   Array of metadata strings
     * @return modelIds    Array of generated model IDs
     */
    function batchRegisterModels(
        bytes32[] calldata _modelHashes,
        string[]  calldata _modelNames,
        string[]  calldata _metadatas
    )
        external
        whenNotPaused
        nonReentrant
        returns (bytes32[] memory modelIds)
    {
        uint256 count = _modelHashes.length;

        if (count != _modelNames.length || count != _metadatas.length) {
            revert ArrayLengthMismatch();
        }
        if (count == 0 || count > MAX_BATCH_SIZE) {
            revert BatchSizeExceeded(count, MAX_BATCH_SIZE);
        }

        modelIds = new bytes32[](count);

        for (uint256 i = 0; i < count; ) {
            if (_modelHashes[i] == bytes32(0)) revert HashCannotBeZero();
            if (bytes(_modelNames[i]).length == 0) revert StringCannotBeEmpty();

            bytes32 modelId = _generateModelId(_modelHashes[i], msg.sender);
            if (_models[modelId].registeredAt != 0) revert ModelIdCollision(modelId);

            _models[modelId] = AIModel({
                modelHash:      _modelHashes[i],
                modelName:      _modelNames[i],
                metadata:       _metadatas[i],
                modelOwner:     msg.sender,
                registeredAt:   block.timestamp,
                currentVersion: 1,
                isActive:       true
            });

            _ownerModels[msg.sender].push(modelId);

            _versionHistory[modelId].push(Version({
                modelHash: _modelHashes[i],
                timestamp: block.timestamp,
                changeLog: "Initial registration (batch)",
                updatedBy: msg.sender
            }));

            emit ModelRegistered(modelId, msg.sender, _modelNames[i], _modelHashes[i], block.timestamp);

            modelIds[i] = modelId;

            unchecked { ++i; }
        }

        totalModels += count;

        emit BatchRegistered(msg.sender, count, block.timestamp);

        return modelIds;
    }

    /**
     * @notice Verify model integrity by comparing a provided hash against the stored hash
     * @param _modelId      Model identifier to verify
     * @param _providedHash Hash to compare against the on-chain record
     * @return isValid      True if the hashes match
     */
    function verifyModel(
        bytes32 _modelId,
        bytes32 _providedHash
    )
        external
        whenNotPaused
        existingModel(_modelId)
        activeModel(_modelId)
        validHash(_providedHash)
        returns (bool isValid)
    {
        isValid = (_models[_modelId].modelHash == _providedHash);

        _verificationLog[_modelId].push(VerificationRecord({
            verifier:     msg.sender,
            timestamp:    block.timestamp,
            isValid:      isValid,
            providedHash: _providedHash
        }));

        totalVerifications++;

        emit ModelVerified(_modelId, msg.sender, isValid, block.timestamp);

        return isValid;
    }

    /**
     * @notice Add a new version to an existing model
     * @param _modelId   Model to update
     * @param _newHash   Hash of the new model version
     * @param _changeLog Description of changes in this version
     */
    function addVersion(
        bytes32 _modelId,
        bytes32 _newHash,
        string calldata _changeLog
    )
        external
        whenNotPaused
        nonReentrant
        existingModel(_modelId)
        activeModel(_modelId)
        onlyModelOwner(_modelId)
        validHash(_newHash)
        validString(_changeLog)
    {
        _models[_modelId].modelHash = _newHash;
        _models[_modelId].currentVersion++;

        _versionHistory[_modelId].push(Version({
            modelHash: _newHash,
            timestamp: block.timestamp,
            changeLog: _changeLog,
            updatedBy: msg.sender
        }));

        emit VersionAdded(
            _modelId,
            _models[_modelId].currentVersion,
            _newHash,
            _changeLog,
            block.timestamp
        );
    }

    /**
     * @notice Deactivate a model (soft delete — data remains on-chain)
     * @param _modelId Model to deactivate
     */
    function deactivateModel(bytes32 _modelId)
        external
        existingModel(_modelId)
        activeModel(_modelId)
        onlyModelOwner(_modelId)
    {
        _models[_modelId].isActive = false;

        emit ModelDeactivated(_modelId, msg.sender, block.timestamp);
    }

    /**
     * @notice Reactivate a previously deactivated model
     * @param _modelId Model to reactivate
     */
    function reactivateModel(bytes32 _modelId)
        external
        existingModel(_modelId)
        onlyModelOwner(_modelId)
    {
        if (_models[_modelId].isActive) revert ModelAlreadyActive(_modelId);

        _models[_modelId].isActive = true;

        emit ModelReactivated(_modelId, msg.sender, block.timestamp);
    }

    /**
     * @notice Transfer model ownership to a new address
     * @param _modelId  Model whose ownership to transfer
     * @param _newOwner New owner address
     */
    function transferModelOwnership(
        bytes32 _modelId,
        address _newOwner
    )
        external
        existingModel(_modelId)
        onlyModelOwner(_modelId)
        validAddr(_newOwner)
    {
        address previousOwner = _models[_modelId].modelOwner;
        _models[_modelId].modelOwner = _newOwner;
        _ownerModels[_newOwner].push(_modelId);

        emit OwnershipTransferred(_modelId, previousOwner, _newOwner, block.timestamp);
    }

    /**
     * @notice Update model metadata (IPFS CID, description, etc.)
     * @param _modelId     Model to update
     * @param _newMetadata New metadata string
     */
    function updateMetadata(
        bytes32 _modelId,
        string calldata _newMetadata
    )
        external
        existingModel(_modelId)
        activeModel(_modelId)
        onlyModelOwner(_modelId)
        validString(_newMetadata)
    {
        _models[_modelId].metadata = _newMetadata;
    }

    // ============================================================
    //                     VIEW FUNCTIONS
    // ============================================================

    /**
     * @notice Get full details of a registered model
     * @param _modelId Model identifier
     * @return model The AIModel struct
     */
    function getModel(bytes32 _modelId)
        external
        view
        existingModel(_modelId)
        returns (AIModel memory model)
    {
        return _models[_modelId];
    }

    /**
     * @notice Get the complete version history for a model
     * @param _modelId Model identifier
     * @return versions Array of Version structs
     */
    function getVersionHistory(bytes32 _modelId)
        external
        view
        existingModel(_modelId)
        returns (Version[] memory versions)
    {
        return _versionHistory[_modelId];
    }

    /**
     * @notice Get the verification audit trail for a model
     * @param _modelId Model identifier
     * @return records Array of VerificationRecord structs
     */
    function getVerificationLog(bytes32 _modelId)
        external
        view
        existingModel(_modelId)
        returns (VerificationRecord[] memory records)
    {
        return _verificationLog[_modelId];
    }

    /**
     * @notice Get all model IDs owned by a specific address
     * @param _owner Owner address
     * @return modelIds Array of bytes32 model identifiers
     */
    function getModelsByOwner(address _owner)
        external
        view
        validAddr(_owner)
        returns (bytes32[] memory modelIds)
    {
        return _ownerModels[_owner];
    }

    /**
     * @notice Check whether a model ID exists on-chain
     * @param _modelId Model identifier to check
     * @return exists True if the model has been registered
     */
    function modelExists(bytes32 _modelId) external view returns (bool exists) {
        return _models[_modelId].registeredAt != 0;
    }

    /**
     * @notice Get the current version number of a model
     * @param _modelId Model identifier
     * @return version Current version number
     */
    function getCurrentVersion(bytes32 _modelId)
        external
        view
        existingModel(_modelId)
        returns (uint256 version)
    {
        return _models[_modelId].currentVersion;
    }

    /**
     * @notice Get the total number of verifications for a model
     * @param _modelId Model identifier
     * @return count Number of verification records
     */
    function getVerificationCount(bytes32 _modelId)
        external
        view
        existingModel(_modelId)
        returns (uint256 count)
    {
        return _verificationLog[_modelId].length;
    }

    // ============================================================
    //                     ADMIN FUNCTIONS
    // ============================================================

    /**
     * @notice Pause all state-changing operations (emergency stop)
     * @dev Only callable by accounts with ADMIN_ROLE
     */
    function pause() external onlyRole(ADMIN_ROLE) {
        _pause();
    }

    /**
     * @notice Resume normal operations after a pause
     * @dev Only callable by accounts with ADMIN_ROLE
     */
    function unpause() external onlyRole(ADMIN_ROLE) {
        _unpause();
    }

    // ============================================================
    //                    INTERNAL FUNCTIONS
    // ============================================================

    /**
     * @dev Generate a unique model ID from hash, sender, timestamp, and counter
     * @param _modelHash The model's hash
     * @param _sender    The address registering the model
     * @return modelId   Unique bytes32 identifier
     */
    function _generateModelId(bytes32 _modelHash, address _sender)
        internal
        returns (bytes32 modelId)
    {
        modelId = keccak256(
            abi.encodePacked(_modelHash, _sender, block.timestamp, _modelCounter)
        );
        _modelCounter++;
        return modelId;
    }
}
