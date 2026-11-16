import asyncio
from app.services.ai_service import _call_gemini
async def main():
    result = await _call_gemini(
        "Return only JSON with status equal to ok",
        "connection-test"
    )
    print(result)
asyncio.run(main())
