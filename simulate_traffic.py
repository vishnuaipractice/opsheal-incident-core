import httpx
import time
import sys

BASE_URL = "http://127.0.0.1:8000"

def main():
    print("\n--- Simulating Live Production Traffic ---")

    # Step 0: Connectivity Check
    try:
        health_resp = httpx.get(f"{BASE_URL}/health", timeout=3.0)
    except Exception:
        print(f"[ERROR] Cannot connect to {BASE_URL}.")
        print("Please start Uvicorn first:")
        print("  uvicorn api.main:app --reload --port 8000\n")
        sys.exit(1)

    # Step 1: Normal transaction
    try:
        r1 = httpx.post(f"{BASE_URL}/v1/settlements", json={
            "transaction_id": "TX-1001",
            "base_amount": 120.0,
            "applied_tax": 12.0,
            "discount_amount": 5.0
        }, timeout=5.0)
        print(f"[Normal Traffic] Status: {r1.status_code} -> {r1.json()}")
    except Exception as e:
        print(f"[Normal Traffic] Error: {e}")

    time.sleep(1)

    # Step 2: Incoming malformed payload (Sev-1 Trigger)
    print("\n--- INCOMING MALFORMED PAYLOAD (Sev-1 Trigger) ---")
    try:
        r2 = httpx.post(f"{BASE_URL}/v1/settlements", json={
            "transaction_id": "TX-99482",
            "base_amount": 250.0,
            "applied_tax": None,
            "discount_amount": None
        }, timeout=5.0)

        if r2.status_code == 500:
            print(f"[CRASH] Status: {r2.status_code} -> {r2.text}")
            print(">> Error logged to logs/production_error.log!")
        elif r2.status_code == 200:
            print(f"[HEALED] Status: {r2.status_code} -> {r2.json()}")
            print(">> Autonomous healing confirmed: Service running with zero crashes!")
        else:
            print(f"[Response] Status: {r2.status_code} -> {r2.text}")
    except Exception as e:
        print(f"[Error]: {e}")

    print()

if __name__ == "__main__":
    main()
