# BlockVerify Testing Guide

BlockVerify’s security guarantees require rigorous testing of the complex smart contract. This project utilizes Hardhat for deployment and automated testing, employing the Mocha framework and Chai assertions.

We currently maintain 60 distinct test cases spanning multiple operational branches and edge cases of the `BlockVerify.sol` smart contract.

## Running the Tests

To run the entire suite of 60 test cases against a local Hardhat Network, ensure dependencies are installed via `npm install`, then execute:

```bash
npx hardhat test
```

To run a specific test group or individual test file:

```bash
npx hardhat test test/BlockVerify.test.js
```

### Coverage Reports
To generate a comprehensive code coverage report for identifying untested logical branches:

```bash
npx hardhat coverage
```

## Test Group Breakdown

Our 60 test cases are conceptually categorized into distinct `describe()` blocks to ensure all aspects of the smart contract are validated independently.

1. **Deployment & Initialization**
   - Validates that the smart contract deploys correctly.
   - Asserts that the admin/creator role is properly assigned to the deployer address.
2. **Model Registration (`registerModel`)**
   - Tests valid hash formats (length and content).
   - Validates event emission (`ModelRegistered`).
   - Ensures correct initial version tracking and uniqueness.
3. **Model Verification (`verifyModel`)**
   - Tests successful matching.
   - Tests verification against invalid/tampered hashes (must fail).
   - Tests verification behavior when an active model is queried versus a deactivated model.
4. **Versioning (`addVersion`)**
   - Tests that only the Model Owner can add a version.
   - Validates that the current version updates gracefully.
   - Checks gas efficiency for adding multiple subsequent versions.
5. **Access Control & RBAC**
   - Evaluates all `require(msg.sender == owner)` restrictions.
   - Tests model deactivation, reactivation, and transferring ownership.
   - Ensures an attacker cannot manipulate models they do not own.

## How to Add New Tests

If you are contributing a new feature or fixing a bug, you must write corresponding test cases in `test/BlockVerify.test.js`.

1. **Locate the relevant `describe` block**. (e.g., if modifying `transferModelOwnership`, add the test to the "Access Control" block).
2. **Use the `it` pattern**: Write a descriptive name for what the test proves.
3. **Deploy a fresh instance**: Use the `loadFixture` pattern from Hardhat Foundation to reset the blockchain state to a clean slate before each new test.

### Common Test Patterns Used

- **`loadFixture`**: We use Hardhat's snapshotting (via `@nomicfoundation/hardhat-network-helpers`) so that the complex setup phase of deploying the `BlockVerify.sol` contract and funding test accounts is only run once per file, vastly reducing test execution time.
- **Revert Assertions**: For access control testing, we heavily rely on Chai's `expect().to.be.revertedWith()` to guarantee that unauthorized actions inherently fail.
- **Event Emissions**: Every state-changing transaction in BlockVerify emits an event (e.g., `ModelRegistered`, `ModelVerified`, `VersionAdded`). We test these using `expect().to.emit(contract...).withArgs()`.
