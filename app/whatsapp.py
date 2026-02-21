from __future__ import annotations

import httpx

from app.config import settings


class WhatsAppClient:
    def __init__(self) -> None:
        self.base_url = "https://graph.facebook.com/v22.0"

    async def send_text(self, wa_id: str, text: str) -> str | None:
        if not settings.outbound_reply_enabled:
            return None
        url = f"{self.base_url}/{settings.whatsapp_phone_number_id}/messages"
        payload = {
            "messaging_product": "whatsapp",
            "to": wa_id,
            "type": "text",
            "text": {"body": text},
        }
        headers = {"Authorization": f"Bearer {settings.whatsapp_access_token}"}
        async with httpx.AsyncClient(timeout=10) as client:
            response = await client.post(url, json=payload, headers=headers)
            response.raise_for_status()
            data = response.json()
            messages = data.get("messages", [])
            return messages[0].get("id") if messages else None

    async def send_template(self, wa_id: str, template_name: str) -> str | None:
        if not settings.outbound_reply_enabled:
            return None
        url = f"{self.base_url}/{settings.whatsapp_phone_number_id}/messages"
        payload = {
            "messaging_product": "whatsapp",
            "to": wa_id,
            "type": "template",
            "template": {
                "name": template_name,
                "language": {"code": "en_US"},
            },
        }
        headers = {"Authorization": f"Bearer {settings.whatsapp_access_token}"}
        async with httpx.AsyncClient(timeout=10) as client:
            response = await client.post(url, json=payload, headers=headers)
            response.raise_for_status()
            data = response.json()
            messages = data.get("messages", [])
            return messages[0].get("id") if messages else None


wa_client = WhatsAppClient()
