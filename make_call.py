import os
from twilio.rest import Client
from dotenv import load_dotenv

load_dotenv()

account_sid = os.environ["TWILIO_ACCOUNT_SID"]
auth_token = os.environ["TWILIO_AUTH_TOKEN"]
twilio_number = os.environ["TWILIO_PHONE_NUMBER"]
my_number = os.environ["MY_PHONE_NUMBER"]
ws_url = os.environ["TWILIO_WS_URL"]

ngrok_base = ws_url.replace("wss://", "https://").replace("/twilio/media-stream", "")

client = Client(account_sid, auth_token)

call = client.calls.create(
    url="https://handler.twilio.com/twiml/EH5ba5302db6cf0428bda8b7235d3b66b8",
    to=my_number,
    from_=twilio_number,
)

print(f"Call initiated: {call.sid}")
