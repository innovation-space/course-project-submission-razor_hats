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

    // Core functions coming soon...
}
