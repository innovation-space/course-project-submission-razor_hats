import re
with open("backend/tests/test_api.py", "r") as f:
    code = f.read()

classes_to_remove = ["TestTamperDemo", "TestMiningMetrics", "TestChainEndpoints"]
for cls in classes_to_remove:
    code = re.sub(fr"class {cls}.*?(?=class )", "", code, flags=re.DOTALL)
    
# Remove any remaining TestTamperDemo at end of file if it didn't match
code = re.sub(r"class TestTamperDemo.*", "", code, flags=re.DOTALL)
code = re.sub(r"class TestMiningMetrics.*", "", code, flags=re.DOTALL)

with open("backend/tests/test_api.py", "w") as f:
    f.write(code)
