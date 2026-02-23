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

    it("Should revert with zero hash", async function () {
      const { blockVerify, user1, user2 } = await loadFixture(deployBlockVerifyFixture);
      const modelHash = ethers.id("zero-hash-verify");

      const { modelId } = await registerAndGetId(
        blockVerify, user1, modelHash, "ZeroHashVerify", "meta"
      );

      await expect(
        blockVerify.connect(user2).verifyModel(modelId, ethers.ZeroHash)
      ).to.be.revertedWithCustomError(blockVerify, "HashCannotBeZero");
    });

    it("Should allow multiple verifications on the same model", async function () {
      const { blockVerify, user1, user2, auditor } = await loadFixture(deployBlockVerifyFixture);
      const modelHash = ethers.id("multi-verify");

      const { modelId } = await registerAndGetId(
        blockVerify, user1, modelHash, "MultiVerify", "meta"
      );

      await blockVerify.connect(user2).verifyModel(modelId, modelHash);
      await blockVerify.connect(auditor).verifyModel(modelId, modelHash);
      await blockVerify.connect(user1).verifyModel(modelId, ethers.id("wrong"));

      const log = await blockVerify.getVerificationLog(modelId);
      expect(log.length).to.equal(3);
      expect(log[0].isValid).to.be.true;
      expect(log[1].isValid).to.be.true;
      expect(log[2].isValid).to.be.false;
    });
  });

  // ──────────────────── Version Tracking Tests ────────────────────

  describe("addVersion", function () {
    it("Should add a new version successfully", async function () {
      const { blockVerify, user1 } = await loadFixture(deployBlockVerifyFixture);
      const hash1 = ethers.id("v1");

      const { modelId } = await registerAndGetId(
        blockVerify, user1, hash1, "VersionModel", "meta"
      );

      const hash2 = ethers.id("v2");
      await blockVerify.connect(user1).addVersion(modelId, hash2, "Improved accuracy");

      const model = await blockVerify.getModel(modelId);
      expect(model.modelHash).to.equal(hash2);
      expect(model.currentVersion).to.equal(2);
    });

    it("Should update version history array", async function () {
      const { blockVerify, user1 } = await loadFixture(deployBlockVerifyFixture);
      const hash1 = ethers.id("vh1");

      const { modelId } = await registerAndGetId(
        blockVerify, user1, hash1, "HistoryModel", "meta"
      );

      const hash2 = ethers.id("vh2");
      await blockVerify.connect(user1).addVersion(modelId, hash2, "Bug fix");

      const hash3 = ethers.id("vh3");
      await blockVerify.connect(user1).addVersion(modelId, hash3, "New features");

      const history = await blockVerify.getVersionHistory(modelId);
      expect(history.length).to.equal(3); // initial + 2 updates
      expect(history[0].changeLog).to.equal("Initial registration");
      expect(history[1].changeLog).to.equal("Bug fix");
      expect(history[2].changeLog).to.equal("New features");
    });

    it("Should emit VersionAdded event", async function () {
      const { blockVerify, user1 } = await loadFixture(deployBlockVerifyFixture);
      const hash1 = ethers.id("ve1");

      const { modelId } = await registerAndGetId(
        blockVerify, user1, hash1, "EventVersion", "meta"
      );

      await expect(
        blockVerify.connect(user1).addVersion(modelId, ethers.id("ve2"), "Update")
      ).to.emit(blockVerify, "VersionAdded");
    });

    it("Should only allow model owner to add versions", async function () {
      const { blockVerify, user1, attacker } = await loadFixture(deployBlockVerifyFixture);

      const { modelId } = await registerAndGetId(
        blockVerify, user1, ethers.id("sec1"), "SecModel", "meta"
      );

      await expect(
        blockVerify.connect(attacker).addVersion(modelId, ethers.id("evil"), "hacked")
      ).to.be.revertedWithCustomError(blockVerify, "NotModelOwner");
    });

    it("Should revert for inactive model", async function () {
      const { blockVerify, user1 } = await loadFixture(deployBlockVerifyFixture);
      const { modelId } = await registerAndGetId(
        blockVerify, user1, ethers.id("inactive-v"), "InactiveV", "meta"
      );

      await blockVerify.connect(user1).deactivateModel(modelId);

      await expect(
        blockVerify.connect(user1).addVersion(modelId, ethers.id("new"), "update")
      ).to.be.revertedWithCustomError(blockVerify, "ModelNotActive");
    });

    it("Should revert with empty changelog", async function () {
      const { blockVerify, user1 } = await loadFixture(deployBlockVerifyFixture);
      const { modelId } = await registerAndGetId(
        blockVerify, user1, ethers.id("empty-cl"), "EmptyCL", "meta"
      );

      await expect(
        blockVerify.connect(user1).addVersion(modelId, ethers.id("new"), "")
      ).to.be.revertedWithCustomError(blockVerify, "StringCannotBeEmpty");
    });

    it("Should make old hash fail verification after version update", async function () {
      const { blockVerify, user1, user2 } = await loadFixture(deployBlockVerifyFixture);
      const hash1 = ethers.id("old-hash");

      const { modelId } = await registerAndGetId(
        blockVerify, user1, hash1, "OldHash", "meta"
      );

      const hash2 = ethers.id("new-hash");
      await blockVerify.connect(user1).addVersion(modelId, hash2, "Updated");

      // Verify with old hash — should fail
      const tx1 = await blockVerify.connect(user2).verifyModel(modelId, hash1);
      const r1 = await tx1.wait();
      const ev1 = r1.logs
        .map((l) => { try { return blockVerify.interface.parseLog({ topics: l.topics, data: l.data }); } catch { return null; } })
        .find((e) => e && e.name === "ModelVerified");
      expect(ev1.args.isValid).to.be.false;

      // Verify with new hash — should pass
      const tx2 = await blockVerify.connect(user2).verifyModel(modelId, hash2);
      const r2 = await tx2.wait();
      const ev2 = r2.logs
        .map((l) => { try { return blockVerify.interface.parseLog({ topics: l.topics, data: l.data }); } catch { return null; } })
        .find((e) => e && e.name === "ModelVerified");
      expect(ev2.args.isValid).to.be.true;
    });
  });

  // ──────────────────── Deactivation / Reactivation Tests ────────────────────

  describe("deactivateModel & reactivateModel", function () {
    it("Should deactivate a model", async function () {
      const { blockVerify, user1 } = await loadFixture(deployBlockVerifyFixture);
      const { modelId } = await registerAndGetId(
        blockVerify, user1, ethers.id("deact"), "DeactModel", "meta"
      );

      await expect(
        blockVerify.connect(user1).deactivateModel(modelId)
      ).to.emit(blockVerify, "ModelDeactivated");

      const model = await blockVerify.getModel(modelId);
      expect(model.isActive).to.be.false;
    });

    it("Should reactivate a deactivated model", async function () {
      const { blockVerify, user1 } = await loadFixture(deployBlockVerifyFixture);
      const { modelId } = await registerAndGetId(
        blockVerify, user1, ethers.id("react"), "ReactModel", "meta"
      );

      await blockVerify.connect(user1).deactivateModel(modelId);

      await expect(
        blockVerify.connect(user1).reactivateModel(modelId)
      ).to.emit(blockVerify, "ModelReactivated");

      const model = await blockVerify.getModel(modelId);
      expect(model.isActive).to.be.true;
    });

    it("Should revert reactivation if already active", async function () {
      const { blockVerify, user1 } = await loadFixture(deployBlockVerifyFixture);
      const { modelId } = await registerAndGetId(
        blockVerify, user1, ethers.id("already-active"), "ActiveModel", "meta"
      );

      await expect(
        blockVerify.connect(user1).reactivateModel(modelId)
      ).to.be.revertedWithCustomError(blockVerify, "ModelAlreadyActive");
    });

    it("Should only allow model owner to deactivate", async function () {
      const { blockVerify, user1, attacker } = await loadFixture(deployBlockVerifyFixture);
      const { modelId } = await registerAndGetId(
        blockVerify, user1, ethers.id("owner-deact"), "OwnerDeact", "meta"
      );

      await expect(
        blockVerify.connect(attacker).deactivateModel(modelId)
      ).to.be.revertedWithCustomError(blockVerify, "NotModelOwner");
    });
  });

  // ──────────────────── Ownership Transfer Tests ────────────────────

  describe("transferModelOwnership", function () {
    it("Should transfer ownership successfully", async function () {
      const { blockVerify, user1, user2 } = await loadFixture(deployBlockVerifyFixture);
      const { modelId } = await registerAndGetId(
        blockVerify, user1, ethers.id("transfer"), "TransferModel", "meta"
      );

      await expect(
        blockVerify.connect(user1).transferModelOwnership(modelId, user2.address)
      ).to.emit(blockVerify, "OwnershipTransferred");

      const model = await blockVerify.getModel(modelId);
      expect(model.modelOwner).to.equal(user2.address);
    });

    it("Should allow new owner to add versions after transfer", async function () {
      const { blockVerify, user1, user2 } = await loadFixture(deployBlockVerifyFixture);
      const { modelId } = await registerAndGetId(
        blockVerify, user1, ethers.id("transfer-v"), "TransferV", "meta"
      );

      await blockVerify.connect(user1).transferModelOwnership(modelId, user2.address);

      // New owner can add version
      await expect(
        blockVerify.connect(user2).addVersion(modelId, ethers.id("new-v"), "New owner update")
      ).to.not.be.reverted;

      // Old owner cannot
      await expect(
        blockVerify.connect(user1).addVersion(modelId, ethers.id("old-v"), "Old owner update")
      ).to.be.revertedWithCustomError(blockVerify, "NotModelOwner");
    });

    it("Should revert transfer to zero address", async function () {
      const { blockVerify, user1 } = await loadFixture(deployBlockVerifyFixture);
      const { modelId } = await registerAndGetId(
        blockVerify, user1, ethers.id("zero-transfer"), "ZeroTransfer", "meta"
      );

      await expect(
        blockVerify.connect(user1).transferModelOwnership(modelId, ethers.ZeroAddress)
      ).to.be.revertedWithCustomError(blockVerify, "InvalidAddress");
    });
  });

  // ──────────────────── Batch Registration Tests ────────────────────

  describe("batchRegisterModels", function () {
    it("Should register multiple models in one transaction", async function () {
      const { blockVerify, user1 } = await loadFixture(deployBlockVerifyFixture);

      const hashes = [ethers.id("b1"), ethers.id("b2"), ethers.id("b3")];
      const names = ["Batch1", "Batch2", "Batch3"];
      const metas = ["meta1", "meta2", "meta3"];

      const tx = await blockVerify.connect(user1).batchRegisterModels(hashes, names, metas);
      await tx.wait();

      expect(await blockVerify.totalModels()).to.equal(3);

      const ownerModels = await blockVerify.getModelsByOwner(user1.address);
      expect(ownerModels.length).to.equal(3);
    });

    it("Should emit BatchRegistered event", async function () {
      const { blockVerify, user1 } = await loadFixture(deployBlockVerifyFixture);

      const hashes = [ethers.id("be1"), ethers.id("be2")];
      const names = ["BE1", "BE2"];
      const metas = ["m1", "m2"];

      await expect(
        blockVerify.connect(user1).batchRegisterModels(hashes, names, metas)
      ).to.emit(blockVerify, "BatchRegistered");
    });

    it("Should revert on array length mismatch", async function () {
      const { blockVerify, user1 } = await loadFixture(deployBlockVerifyFixture);

      await expect(
        blockVerify.connect(user1).batchRegisterModels(
          [ethers.id("x1"), ethers.id("x2")],
          ["Name1"],
          ["meta1", "meta2"]
        )
      ).to.be.revertedWithCustomError(blockVerify, "ArrayLengthMismatch");
    });

    it("Should revert on empty batch", async function () {
      const { blockVerify, user1 } = await loadFixture(deployBlockVerifyFixture);

      await expect(
        blockVerify.connect(user1).batchRegisterModels([], [], [])
      ).to.be.revertedWithCustomError(blockVerify, "BatchSizeExceeded");
    });

    it("Should revert if batch exceeds MAX_BATCH_SIZE", async function () {
      const { blockVerify, user1 } = await loadFixture(deployBlockVerifyFixture);

      const size = 21;
      const hashes = Array.from({ length: size }, (_, i) => ethers.id(`big-${i}`));
      const names = Array.from({ length: size }, (_, i) => `Big${i}`);
      const metas = Array.from({ length: size }, () => "meta");

      await expect(
        blockVerify.connect(user1).batchRegisterModels(hashes, names, metas)
      ).to.be.revertedWithCustomError(blockVerify, "BatchSizeExceeded");
    });
  });

  // ──────────────────── Metadata Update Tests ────────────────────

  describe("updateMetadata", function () {
    it("Should update metadata successfully", async function () {
      const { blockVerify, user1 } = await loadFixture(deployBlockVerifyFixture);
      const { modelId } = await registerAndGetId(
        blockVerify, user1, ethers.id("meta-upd"), "MetaUpdate", "old-meta"
      );

      await blockVerify.connect(user1).updateMetadata(modelId, "ipfs://QmNEW123");

      const model = await blockVerify.getModel(modelId);
      expect(model.metadata).to.equal("ipfs://QmNEW123");
    });

    it("Should revert for non-owner", async function () {
      const { blockVerify, user1, attacker } = await loadFixture(deployBlockVerifyFixture);
      const { modelId } = await registerAndGetId(
        blockVerify, user1, ethers.id("meta-sec"), "MetaSec", "meta"
      );

      await expect(
        blockVerify.connect(attacker).updateMetadata(modelId, "hacked")
      ).to.be.revertedWithCustomError(blockVerify, "NotModelOwner");
    });
  });

  // ──────────────────── Pause Tests ────────────────────

  describe("Pause / Unpause", function () {
    it("Should allow admin to pause", async function () {
      const { blockVerify, owner } = await loadFixture(deployBlockVerifyFixture);
      await blockVerify.connect(owner).pause();
      expect(await blockVerify.paused()).to.be.true;
    });

    it("Should block registration when paused", async function () {
      const { blockVerify, owner, user1 } = await loadFixture(deployBlockVerifyFixture);
      await blockVerify.connect(owner).pause();

      await expect(
        blockVerify.connect(user1).registerModel(ethers.id("paused"), "Paused", "meta")
      ).to.be.revertedWithCustomError(blockVerify, "EnforcedPause");
    });

    it("Should block verification when paused", async function () {
      const { blockVerify, owner, user1, user2 } = await loadFixture(deployBlockVerifyFixture);
      const modelHash = ethers.id("pause-verify");

      const { modelId } = await registerAndGetId(
        blockVerify, user1, modelHash, "PauseVerify", "meta"
      );

      await blockVerify.connect(owner).pause();

      await expect(
        blockVerify.connect(user2).verifyModel(modelId, modelHash)
      ).to.be.revertedWithCustomError(blockVerify, "EnforcedPause");
    });

    it("Should allow admin to unpause and resume operations", async function () {
      const { blockVerify, owner, user1 } = await loadFixture(deployBlockVerifyFixture);

      await blockVerify.connect(owner).pause();
      await blockVerify.connect(owner).unpause();

      // Should work again
      await expect(
        blockVerify.connect(user1).registerModel(ethers.id("unpaused"), "Unpaused", "meta")
      ).to.not.be.reverted;
    });

    it("Should revert if non-admin tries to pause", async function () {
      const { blockVerify, attacker } = await loadFixture(deployBlockVerifyFixture);

      await expect(
        blockVerify.connect(attacker).pause()
      ).to.be.reverted;
    });
  });

  // ──────────────────── View Functions Tests ────────────────────

  describe("View Functions", function () {
    it("Should return correct model via getModel", async function () {
      const { blockVerify, user1 } = await loadFixture(deployBlockVerifyFixture);
      const hash = ethers.id("view-model");

      const { modelId } = await registerAndGetId(
        blockVerify, user1, hash, "ViewModel", "view-meta"
      );

      const model = await blockVerify.getModel(modelId);
      expect(model.modelName).to.equal("ViewModel");
      expect(model.metadata).to.equal("view-meta");
    });

    it("Should check model existence correctly", async function () {
      const { blockVerify, user1 } = await loadFixture(deployBlockVerifyFixture);

      const { modelId } = await registerAndGetId(
        blockVerify, user1, ethers.id("exists"), "ExistsModel", "meta"
      );

      expect(await blockVerify.modelExists(modelId)).to.be.true;
      expect(await blockVerify.modelExists(ethers.id("nonexistent"))).to.be.false;
    });

    it("Should return correct current version", async function () {
      const { blockVerify, user1 } = await loadFixture(deployBlockVerifyFixture);
      const { modelId } = await registerAndGetId(
        blockVerify, user1, ethers.id("cv1"), "CurrentV", "meta"
      );

      expect(await blockVerify.getCurrentVersion(modelId)).to.equal(1);

      await blockVerify.connect(user1).addVersion(modelId, ethers.id("cv2"), "v2");
      expect(await blockVerify.getCurrentVersion(modelId)).to.equal(2);

      await blockVerify.connect(user1).addVersion(modelId, ethers.id("cv3"), "v3");
      expect(await blockVerify.getCurrentVersion(modelId)).to.equal(3);
    });

    it("Should return verification count correctly", async function () {
      const { blockVerify, user1, user2 } = await loadFixture(deployBlockVerifyFixture);
      const hash = ethers.id("vc-test");
      const { modelId } = await registerAndGetId(
        blockVerify, user1, hash, "VCTest", "meta"
      );

      expect(await blockVerify.getVerificationCount(modelId)).to.equal(0);

      await blockVerify.connect(user2).verifyModel(modelId, hash);
      expect(await blockVerify.getVerificationCount(modelId)).to.equal(1);

      await blockVerify.connect(user2).verifyModel(modelId, ethers.id("wrong"));
      expect(await blockVerify.getVerificationCount(modelId)).to.equal(2);
    });

    it("Should revert getModel for non-existent model", async function () {
      const { blockVerify } = await loadFixture(deployBlockVerifyFixture);

      await expect(
        blockVerify.getModel(ethers.id("ghost"))
      ).to.be.revertedWithCustomError(blockVerify, "ModelDoesNotExist");
    });

    it("Should revert getModelsByOwner for zero address", async function () {
      const { blockVerify } = await loadFixture(deployBlockVerifyFixture);

      await expect(
        blockVerify.getModelsByOwner(ethers.ZeroAddress)
      ).to.be.revertedWithCustomError(blockVerify, "InvalidAddress");
    });
  });

  // ──────────────────── Full Lifecycle Integration Test ────────────────────

  describe("Full Model Lifecycle", function () {
    it("Should handle complete lifecycle: register → verify → update → verify → deactivate → reactivate", async function () {
      const { blockVerify, user1, user2 } = await loadFixture(deployBlockVerifyFixture);

      // 1. Register
      const hashV1 = ethers.id("lifecycle-v1");
      const { modelId } = await registerAndGetId(
        blockVerify, user1, hashV1, "LifecycleModel", "ipfs://Qm123"
      );

      let model = await blockVerify.getModel(modelId);
      expect(model.currentVersion).to.equal(1);

      // 2. Verify (valid)
      await blockVerify.connect(user2).verifyModel(modelId, hashV1);
      let log = await blockVerify.getVerificationLog(modelId);
      expect(log[0].isValid).to.be.true;

      // 3. Add version
      const hashV2 = ethers.id("lifecycle-v2");
      await blockVerify.connect(user1).addVersion(modelId, hashV2, "Improved accuracy to 98%");

      model = await blockVerify.getModel(modelId);
      expect(model.currentVersion).to.equal(2);
      expect(model.modelHash).to.equal(hashV2);

      // 4. Verify old hash (should fail)
      await blockVerify.connect(user2).verifyModel(modelId, hashV1);
      log = await blockVerify.getVerificationLog(modelId);
      expect(log[1].isValid).to.be.false;

      // 5. Verify new hash (should pass)
      await blockVerify.connect(user2).verifyModel(modelId, hashV2);
      log = await blockVerify.getVerificationLog(modelId);
      expect(log[2].isValid).to.be.true;

      // 6. Deactivate
      await blockVerify.connect(user1).deactivateModel(modelId);
      model = await blockVerify.getModel(modelId);
      expect(model.isActive).to.be.false;

      // 7. Cannot verify when inactive
      await expect(
        blockVerify.connect(user2).verifyModel(modelId, hashV2)
      ).to.be.revertedWithCustomError(blockVerify, "ModelNotActive");

      // 8. Reactivate
      await blockVerify.connect(user1).reactivateModel(modelId);
      model = await blockVerify.getModel(modelId);
      expect(model.isActive).to.be.true;

      // 9. Can verify again
      await blockVerify.connect(user2).verifyModel(modelId, hashV2);
      log = await blockVerify.getVerificationLog(modelId);
      expect(log[3].isValid).to.be.true;

      // 10. Check version history is complete
      const history = await blockVerify.getVersionHistory(modelId);
      expect(history.length).to.equal(2);

      // 11. Check total stats
      expect(await blockVerify.totalModels()).to.equal(1);
      expect(await blockVerify.totalVerifications()).to.equal(4);
    });
  });

  // ──────────────────── Gas Optimization Tests ────────────────────

  describe("Gas Usage", function () {
    it("Should register model within reasonable gas limit", async function () {
      const { blockVerify, user1 } = await loadFixture(deployBlockVerifyFixture);

      const tx = await blockVerify
        .connect(user1)
        .registerModel(ethers.id("gas-test"), "GasTest", "metadata");
      const receipt = await tx.wait();

      // Registration should be under 450k gas (includes OZ AccessControl + Pausable + ReentrancyGuard overhead)
      expect(receipt.gasUsed).to.be.lessThan(450000n);
      console.log(`    ⛽ registerModel gas used: ${receipt.gasUsed.toString()}`);
    });

    it("Should verify model within reasonable gas limit", async function () {
      const { blockVerify, user1, user2 } = await loadFixture(deployBlockVerifyFixture);
      const hash = ethers.id("gas-verify");

      const { modelId } = await registerAndGetId(
        blockVerify, user1, hash, "GasVerify", "meta"
      );

      const tx = await blockVerify.connect(user2).verifyModel(modelId, hash);
      const receipt = await tx.wait();

      // Verification should be under 200k gas
      expect(receipt.gasUsed).to.be.lessThan(200000n);
      console.log(`    ⛽ verifyModel gas used: ${receipt.gasUsed.toString()}`);
    });

    it("Should add version within reasonable gas limit", async function () {
      const { blockVerify, user1 } = await loadFixture(deployBlockVerifyFixture);
      const { modelId } = await registerAndGetId(
        blockVerify, user1, ethers.id("gas-v1"), "GasVersion", "meta"
      );

      const tx = await blockVerify
        .connect(user1)
        .addVersion(modelId, ethers.id("gas-v2"), "Performance improvement");
      const receipt = await tx.wait();

      // Version addition should be under 150k gas
      expect(receipt.gasUsed).to.be.lessThan(150000n);
      console.log(`    ⛽ addVersion gas used: ${receipt.gasUsed.toString()}`);
    });
  });
});
