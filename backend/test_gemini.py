import requests, os
key = "AIzaSyBi8DB_lw6N6tsITUOfKmAk8Ec01RHKLSY"
for model in ["gemini-1.5-flash", "gemini-1.5-flash-latest", "gemini-pro", "gemini-1.0-pro"]:
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={key}"
    resp = requests.post(url, json={"contents": [{"role": "user", "parts": [{"text": "hi"}]}]}, headers={"Content-Type": "application/json"})
    print(model, resp.status_code)
