import asyncio
import httpx

from src.core.config import get_settings


async def main():
    settings = get_settings()

    base_url = settings.llm_base_url.rstrip("/")
    api_key = settings.llm_api_key.get_secret_value()
    model = settings.llm_model

    async with httpx.AsyncClient(timeout=30) as client:
        response = await client.post(
            f"{base_url}/chat/completions",
            headers={"Authorization": f"Bearer {api_key}"},
            json={
                "model": model,
                "messages": [
                    {"role": "user", "content": "Reply with OK."}
                ],
                "max_tokens": 10,
            },
        )

    print("HTTP status:", response.status_code)

    try:
        payload = response.json()
    except ValueError:
        print("Response was not JSON.")
        return

    if response.is_error:
        error = payload.get("error", {})
        if isinstance(error, dict):
            print("Error type:", error.get("type"))
            print("Error code:", error.get("code"))
            print("Error message:", error.get("message"))
        else:
            print("Error details:", str(error)[:500])
    else:
        print("Model:", payload.get("model"))
        print("Request succeeded.")


asyncio.run(main())
