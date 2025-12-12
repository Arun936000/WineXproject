import requests
import json

WHATSAPP_API_URL = "https://graph.facebook.com/v22.0/956334050886377/messages"
WHATSAPP_ACCESS_TOKEN = "EAATx8KxZCmU0BQAflE2Hv7eVTr4XZBd5ORPE8Kn97neaGF984T4VP5aKjDKV27exbLeS49nyrf8jnJOTCNZB49GjcDIfMx1sjrhDxZBtCoZBgwT4aYbS3kMtZBvaKMzlKjqMrmhQR891782OWwM4Ygcd4aOiPMAqc6ZAWRec3HrI5jXgZAsGSo7GU0tsOKss6Jo0SZCCJo5DMiAOwuzNABclgzePp2rRqeohzIYbvjX0CLhn1kx6rOrwOqJEFo7t9d6DcMuNZB4OhZAZAtZBWJD66Io3rxd2N1AZDZD"   # Replace with new generated token

def send_whatsapp_message(to_number, template_name="hello_world"):
    """
    Sends a template message using WhatsApp Cloud API
    """

    headers = {
        "Authorization": f"Bearer {WHATSAPP_ACCESS_TOKEN}",
        "Content-Type": "application/json",
    }

    data = {
        "messaging_product": "whatsapp",
        "to": to_number,
        "type": "template",
        "template": {
            "name": template_name,
            "language": {"code": "en_US"}
        }
    }

    response = requests.post(WHATSAPP_API_URL, headers=headers, json=data)
    return response.json()
