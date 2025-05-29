import os
import time
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
        "version": "a07f252abbbd832009640b27f063ea52d87d7a23a185ca165bec23b5adc8deaf",
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

    # 🟡 الانتظار الأقصى: 90 ثانية
    for _ in range(45):  # 45 محاولة × 2 ثانية = 90 ثانية
        r = requests.get(f"{endpoint}/{prediction_id}", headers=headers)
        result = r.json()

        if result["status"] == "succeeded":
            output = result["output"]
            print("✅ النتيجة من Replicate:", output)
            return output

        if result["status"] == "failed":
            print("❌ فشل المعالجة:", result)
            return None

        time.sleep(2)  # ✅ تأخير مهم لتفادي الضغط والمهلة

    print("❌ تجاوز وقت الانتظار 90 ثانية.")
    return None
