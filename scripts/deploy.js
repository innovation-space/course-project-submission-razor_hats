const hre = require("hardhat");

async function main() {
  console.log("═══════════════════════════════════════════════");
  console.log("  BlockVerify - Deployment Script");
  console.log("═══════════════════════════════════════════════\n");

  const [deployer] = await hre.ethers.getSigners();
  const balance = await hre.ethers.provider.getBalance(deployer.address);

  console.log(`  Network:  ${hre.network.name}`);
  console.log(`  Deployer: ${deployer.address}`);
  console.log(`  Balance:  ${hre.ethers.formatEther(balance)} ETH/MATIC\n`);

  // Deploy BlockVerify
  console.log("  Deploying BlockVerify contract...\n");
  const BlockVerify = await hre.ethers.getContractFactory("BlockVerify");
  const blockVerify = await BlockVerify.deploy();
  await blockVerify.waitForDeployment();

  const contractAddress = await blockVerify.getAddress();
  const deployTx = blockVerify.deploymentTransaction();

  console.log(`  ✅ BlockVerify deployed successfully!`);
  console.log(`  📍 Contract Address: ${contractAddress}`);
  console.log(`  📝 Transaction Hash: ${deployTx.hash}`);
  console.log(`  ⛽ Gas Used: ${deployTx.gasLimit.toString()}\n`);

  // Verify basic functionality
  console.log("  Verifying deployment...");
  const version = await blockVerify.VERSION();
  console.log(`  📌 Contract Version: ${version}`);

  const totalModels = await blockVerify.totalModels();
  console.log(`  📊 Total Models: ${totalModels.toString()}`);

  const ADMIN_ROLE = await blockVerify.ADMIN_ROLE();
  const isAdmin = await blockVerify.hasRole(ADMIN_ROLE, deployer.address);
  console.log(`  🔐 Deployer is Admin: ${isAdmin}\n`);

  // Summary
  console.log("═══════════════════════════════════════════════");
  console.log("  Deployment Summary");
  console.log("═══════════════════════════════════════════════");
  console.log(`  Contract:  BlockVerify v${version}`);
  console.log(`  Address:   ${contractAddress}`);
  console.log(`  Network:   ${hre.network.name}`);
  console.log(`  Deployer:  ${deployer.address}`);
  console.log("═══════════════════════════════════════════════\n");

  // Save deployment info
  const fs = require("fs");
  const deploymentInfo = {
    network: hre.network.name,
    contractAddress: contractAddress,
    deployer: deployer.address,
    transactionHash: deployTx.hash,
    blockNumber: deployTx.blockNumber,
    timestamp: new Date().toISOString(),
    version: version,
  };

  const deploymentsDir = "./deployments";
  if (!fs.existsSync(deploymentsDir)) {
    fs.mkdirSync(deploymentsDir, { recursive: true });
  }

  const filename = `${deploymentsDir}/${hre.network.name}-deployment.json`;
  fs.writeFileSync(filename, JSON.stringify(deploymentInfo, null, 2));
  console.log(`  💾 Deployment info saved to ${filename}\n`);

  // Verification instructions for Polygon Amoy
  if (hre.network.name === "polygonAmoy") {
    console.log("  To verify on PolygonScan:");
    console.log(`  npx hardhat verify --network polygonAmoy ${contractAddress}\n`);
  }
}

main()
  .then(() => process.exit(0))
  .catch((error) => {
    console.error("\n  ❌ Deployment failed:", error);
    process.exit(1);
  });
