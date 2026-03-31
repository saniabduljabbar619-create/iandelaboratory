# -*- coding: utf-8 -*-
import os
import requests


class SMSService:
    """
    Central SMS Gateway (Termii)
    """

    BASE_URL = "https://api.ng.termii.com/api/sms/send"

    @staticmethod
    def send_sms(phone: str, message: str) -> dict:
        """
        Send SMS using Termii API
        """

        api_key = os.getenv("TERMII_API_KEY")

        if not api_key:
            raise Exception("TERMII_API_KEY not set in environment")

        payload = {
            "to": phone,
            "from": "I&E Diagnostics Labs",  # ✅ Sender Name
            "sms": message,
            "type": "plain",
            "channel": "generic",
            "api_key": api_key
        }

        try:
            response = requests.post(SMSService.BASE_URL, json=payload, timeout=10)

            data = response.json()

            if response.status_code != 200:
                print("❌ SMS FAILED:", data)

            return data

        except Exception as e:
            print("❌ SMS ERROR:", str(e))
            return {"error": str(e)}