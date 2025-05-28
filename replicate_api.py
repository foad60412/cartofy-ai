import os
import requests
from dotenv import load_dotenv

load_dotenv()

REPLICATE_API_TOKEN = os.getenv("REPLICATE_API_TOKEN")

def cartoonify_image(image_url):
    endpoint = "https://api.replicate.com/v1/predictions"
    headers = {
        "Authorization": f"Token {REPLICATE_API_TOKEN}",
        "Content-Type": "application/json"
    }

    payload = {
        "version": "f109015d60170dfb20460f17da8cb863155823c85ece1115e1e9e4ec7ef51d3b",
        "input": {
            "image": image_url
        }
    }

    response = requests.post(endpoint, json=payload, headers=headers)
    result = response.json()

    if "id" not in result:
        print("❌ لم يتم الحصول على ID من Replicate")
        return None

    prediction_id = result["id"]

    while result["status"] not in ["succeeded", "failed"]:
        r = requests.get(f"{endpoint}/{prediction_id}", headers=headers)
        result = r.json()

    if result["status"] == "succeeded":
        output = result["output"]
        print("✅ النتيجة من Replicate:", output)
        return output  # ✅ رابط نصي مباشر
    else:
        print("❌ فشل المعالجة:", result)
        return None
