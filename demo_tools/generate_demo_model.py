import json, random, os

def generate():
    print("Generating Academic Demo Models for BlockVerify...")
    
    # 1. Generate base architecture
    base_model = {
        "metadata": {
            "name": "ResNet-50-Medical",
            "framework": "TensorFlow.js",
            "precision": "float32",
            "params": 25600000
        },
        "layers": {
            "conv2d_1": [round(random.uniform(-1, 1), 6) for _ in range(500)],
            "batch_normalization_1": [round(random.uniform(0, 1), 6) for _ in range(100)],
            "activation_relu_1": [],
            "max_pooling2d_1": [],
            "conv2d_2": [round(random.uniform(-1, 1), 6) for _ in range(500)],
            "dense_1": [round(random.uniform(-1, 1), 6) for _ in range(256)],
            "dense_output": [round(random.uniform(-1, 1), 6) for _ in range(10)]
        }
    }

    # Write original model
    with open("demo_original.json", "w") as f:
        json.dump(base_model, f)
    print("✅ Created demo_original.json")

    # 2. Tamper the model (simulate a backdoor in dense_1)
    tampered_model = json.loads(json.dumps(base_model))
    tampered_model["layers"]["dense_1"][42] = 999.999999
    
    # Write tampered model
    with open("demo_tampered_weights.json", "w") as f:
        json.dump(tampered_model, f)
    print("🚨 Created demo_tampered_weights.json (Backdoor injected in 'dense_1')")

    # 3. Structural Anomaly (Rogue Layer)
    rogue_model = json.loads(json.dumps(base_model))
    
    # We rebuild the layers dict to insert a rogue layer right before 'dense_1'
    new_layers = {}
    for k, v in rogue_model["layers"].items():
        if k == "dense_1":
            new_layers["backdoor_bypass_layer"] = [round(random.uniform(-1, 1), 6) for _ in range(128)]
        new_layers[k] = v
        
    rogue_model["layers"] = new_layers
    rogue_model["metadata"]["params"] += 128
    
    with open("demo_rogue_layer.json", "w") as f:
        json.dump(rogue_model, f)
    print("🧨 Created demo_rogue_layer.json (Topology compromised: 'backdoor_bypass_layer' inserted)")

if __name__ == "__main__":
    generate()
    print("Done! You can use these files to demonstrate both Weight Tampering & Structural Anomalies.")
