const { expect } = require("chai");
const { ethers } = require("hardhat");
const {
  loadFixture,
} = require("@nomicfoundation/hardhat-toolbox/network-helpers");

describe("BlockVerify", function () {
  // ──────────────────────────── Fixtures ────────────────────────────

  async function deployBlockVerifyFixture() {
    const [owner, user1, user2, auditor, attacker] =
      await ethers.getSigners();

    const BlockVerify = await ethers.getContractFactory("BlockVerify");
    const blockVerify = await BlockVerify.deploy();
    await blockVerify.waitForDeployment();

    const ADMIN_ROLE = await blockVerify.ADMIN_ROLE();
    const AUDITOR_ROLE = await blockVerify.AUDITOR_ROLE();

    // Grant auditor role
    await blockVerify.grantRole(AUDITOR_ROLE, auditor.address);

    return { blockVerify, owner, user1, user2, auditor, attacker, ADMIN_ROLE, AUDITOR_ROLE };
  }

  // Helper: register a model and return the modelId from the event
  async function registerAndGetId(contract, signer, hash, name, metadata) {
    const tx = await contract.connect(signer).registerModel(hash, name, metadata);
    const receipt = await tx.wait();

    // Find the ModelRegistered event
    const event = receipt.logs
      .map((log) => {
        try {
          return contract.interface.parseLog({ topics: log.topics, data: log.data });
        } catch {
          return null;
        }
      })
      .find((e) => e && e.name === "ModelRegistered");

    return { modelId: event.args.modelId, receipt, tx };
  }

  // ──────────────────── Deployment & Setup Tests ────────────────────

  describe("Deployment", function () {
    it("Should set the deployer as default admin", async function () {
      const { blockVerify, owner } = await loadFixture(deployBlockVerifyFixture);
      const DEFAULT_ADMIN_ROLE = await blockVerify.DEFAULT_ADMIN_ROLE();
      expect(await blockVerify.hasRole(DEFAULT_ADMIN_ROLE, owner.address)).to.be.true;
    });

    it("Should set the deployer as ADMIN_ROLE", async function () {
      const { blockVerify, owner, ADMIN_ROLE } = await loadFixture(deployBlockVerifyFixture);
      expect(await blockVerify.hasRole(ADMIN_ROLE, owner.address)).to.be.true;
    });

    it("Should set the deployer as AUDITOR_ROLE", async function () {
      const { blockVerify, owner, AUDITOR_ROLE } = await loadFixture(deployBlockVerifyFixture);
      expect(await blockVerify.hasRole(AUDITOR_ROLE, owner.address)).to.be.true;
    });

    it("Should have version 1.0.0", async function () {
      const { blockVerify } = await loadFixture(deployBlockVerifyFixture);
      expect(await blockVerify.VERSION()).to.equal("1.0.0");
    });

    it("Should start with zero total models", async function () {
      const { blockVerify } = await loadFixture(deployBlockVerifyFixture);
      expect(await blockVerify.totalModels()).to.equal(0);
    });

    it("Should start with zero total verifications", async function () {
      const { blockVerify } = await loadFixture(deployBlockVerifyFixture);
      expect(await blockVerify.totalVerifications()).to.equal(0);
    });
  });

  // ──────────────────── Model Registration Tests ────────────────────

  describe("registerModel", function () {
    it("Should register a model with valid inputs", async function () {
      const { blockVerify, user1 } = await loadFixture(deployBlockVerifyFixture);

      const modelHash = ethers.id("my-ai-model-v1");
      const { modelId } = await registerAndGetId(
        blockVerify, user1, modelHash, "GPT-Health-v1", "ipfs://QmABC123"
      );

      const model = await blockVerify.getModel(modelId);
      expect(model.modelHash).to.equal(modelHash);
      expect(model.modelName).to.equal("GPT-Health-v1");
      expect(model.metadata).to.equal("ipfs://QmABC123");
      expect(model.modelOwner).to.equal(user1.address);
      expect(model.currentVersion).to.equal(1);
      expect(model.isActive).to.be.true;
    });

    it("Should emit ModelRegistered event", async function () {
      const { blockVerify, user1 } = await loadFixture(deployBlockVerifyFixture);
      const modelHash = ethers.id("event-test-model");

      await expect(
        blockVerify.connect(user1).registerModel(modelHash, "EventModel", "meta")
      ).to.emit(blockVerify, "ModelRegistered");
    });

    it("Should increment totalModels counter", async function () {
      const { blockVerify, user1 } = await loadFixture(deployBlockVerifyFixture);

      await blockVerify.connect(user1).registerModel(ethers.id("m1"), "M1", "meta");
      expect(await blockVerify.totalModels()).to.equal(1);

      await blockVerify.connect(user1).registerModel(ethers.id("m2"), "M2", "meta");
      expect(await blockVerify.totalModels()).to.equal(2);
    });

    it("Should create initial version history entry", async function () {
      const { blockVerify, user1 } = await loadFixture(deployBlockVerifyFixture);
      const modelHash = ethers.id("version-test");

      const { modelId } = await registerAndGetId(
        blockVerify, user1, modelHash, "VersionTest", "meta"
      );

      const history = await blockVerify.getVersionHistory(modelId);
      expect(history.length).to.equal(1);
      expect(history[0].modelHash).to.equal(modelHash);
      expect(history[0].changeLog).to.equal("Initial registration");
      expect(history[0].updatedBy).to.equal(user1.address);
    });

    it("Should add modelId to owner's model list", async function () {
      const { blockVerify, user1 } = await loadFixture(deployBlockVerifyFixture);

      const { modelId } = await registerAndGetId(
        blockVerify, user1, ethers.id("owner-list-test"), "OwnerListTest", "meta"
      );

      const ownerModels = await blockVerify.getModelsByOwner(user1.address);
      expect(ownerModels).to.include(modelId);
    });

    it("Should revert with zero hash", async function () {
      const { blockVerify, user1 } = await loadFixture(deployBlockVerifyFixture);

      await expect(
        blockVerify.connect(user1).registerModel(ethers.ZeroHash, "Model", "meta")
      ).to.be.revertedWithCustomError(blockVerify, "HashCannotBeZero");
    });

    it("Should revert with empty model name", async function () {
      const { blockVerify, user1 } = await loadFixture(deployBlockVerifyFixture);

      await expect(
        blockVerify.connect(user1).registerModel(ethers.id("hash"), "", "meta")
      ).to.be.revertedWithCustomError(blockVerify, "StringCannotBeEmpty");
    });

    it("Should allow empty metadata", async function () {
      const { blockVerify, user1 } = await loadFixture(deployBlockVerifyFixture);
      // metadata is not checked with validString, so empty is fine
      // Actually let's check — our contract uses calldata but doesn't validate metadata
      const modelHash = ethers.id("empty-meta");
      const { modelId } = await registerAndGetId(
        blockVerify, user1, modelHash, "EmptyMeta", ""
      );
      const model = await blockVerify.getModel(modelId);
      expect(model.metadata).to.equal("");
    });

    it("Should allow multiple models from the same owner", async function () {
      const { blockVerify, user1 } = await loadFixture(deployBlockVerifyFixture);

      await registerAndGetId(blockVerify, user1, ethers.id("m1"), "Model1", "meta");
      await registerAndGetId(blockVerify, user1, ethers.id("m2"), "Model2", "meta");
      await registerAndGetId(blockVerify, user1, ethers.id("m3"), "Model3", "meta");

      const ownerModels = await blockVerify.getModelsByOwner(user1.address);
      expect(ownerModels.length).to.equal(3);
    });
  });

  // ──────────────────── Model Verification Tests ────────────────────

  describe("verifyModel", function () {
    it("Should return true for matching hash", async function () {
      const { blockVerify, user1, user2 } = await loadFixture(deployBlockVerifyFixture);
      const modelHash = ethers.id("verify-test");

      const { modelId } = await registerAndGetId(
        blockVerify, user1, modelHash, "VerifyModel", "meta"
      );

      // user2 verifies the model
      const tx = await blockVerify.connect(user2).verifyModel(modelId, modelHash);
      const receipt = await tx.wait();

      const event = receipt.logs
        .map((log) => {
          try { return blockVerify.interface.parseLog({ topics: log.topics, data: log.data }); }
          catch { return null; }
        })
        .find((e) => e && e.name === "ModelVerified");

      expect(event.args.isValid).to.be.true;
    });

    it("Should return false for non-matching hash", async function () {
      const { blockVerify, user1, user2 } = await loadFixture(deployBlockVerifyFixture);
      const modelHash = ethers.id("original-hash");

      const { modelId } = await registerAndGetId(
        blockVerify, user1, modelHash, "VerifyFalse", "meta"
      );

      const wrongHash = ethers.id("tampered-hash");
      const tx = await blockVerify.connect(user2).verifyModel(modelId, wrongHash);
      const receipt = await tx.wait();

      const event = receipt.logs
        .map((log) => {
          try { return blockVerify.interface.parseLog({ topics: log.topics, data: log.data }); }
          catch { return null; }
        })
        .find((e) => e && e.name === "ModelVerified");

      expect(event.args.isValid).to.be.false;
    });

    it("Should emit ModelVerified event", async function () {
      const { blockVerify, user1, user2 } = await loadFixture(deployBlockVerifyFixture);
      const modelHash = ethers.id("event-verify");

      const { modelId } = await registerAndGetId(
        blockVerify, user1, modelHash, "EventVerify", "meta"
      );

      await expect(
        blockVerify.connect(user2).verifyModel(modelId, modelHash)
      ).to.emit(blockVerify, "ModelVerified");
    });

    it("Should log verification record in audit trail", async function () {
      const { blockVerify, user1, user2 } = await loadFixture(deployBlockVerifyFixture);
      const modelHash = ethers.id("audit-trail-test");

      const { modelId } = await registerAndGetId(
        blockVerify, user1, modelHash, "AuditTest", "meta"
      );

      await blockVerify.connect(user2).verifyModel(modelId, modelHash);

      const log = await blockVerify.getVerificationLog(modelId);
      expect(log.length).to.equal(1);
      expect(log[0].verifier).to.equal(user2.address);
      expect(log[0].isValid).to.be.true;
      expect(log[0].providedHash).to.equal(modelHash);
    });

    it("Should increment totalVerifications", async function () {
      const { blockVerify, user1, user2 } = await loadFixture(deployBlockVerifyFixture);
      const modelHash = ethers.id("count-verify");

      const { modelId } = await registerAndGetId(
        blockVerify, user1, modelHash, "CountVerify", "meta"
      );

      await blockVerify.connect(user2).verifyModel(modelId, modelHash);
      expect(await blockVerify.totalVerifications()).to.equal(1);

      await blockVerify.connect(user2).verifyModel(modelId, ethers.id("wrong"));
      expect(await blockVerify.totalVerifications()).to.equal(2);
    });

    it("Should revert for non-existent model", async function () {
      const { blockVerify, user1 } = await loadFixture(deployBlockVerifyFixture);

      await expect(
        blockVerify.connect(user1).verifyModel(ethers.id("nonexistent"), ethers.id("hash"))
      ).to.be.revertedWithCustomError(blockVerify, "ModelDoesNotExist");
    });

    it("Should revert for deactivated model", async function () {
      const { blockVerify, user1, user2 } = await loadFixture(deployBlockVerifyFixture);
      const modelHash = ethers.id("deactivated-verify");

      const { modelId } = await registerAndGetId(
        blockVerify, user1, modelHash, "DeactVerify", "meta"
      );

      await blockVerify.connect(user1).deactivateModel(modelId);

      await expect(
        blockVerify.connect(user2).verifyModel(modelId, modelHash)
      ).to.be.revertedWithCustomError(blockVerify, "ModelNotActive");
    });

