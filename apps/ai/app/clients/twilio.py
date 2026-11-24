"""
Twilio Voice over its REST API (no SDK): place a call, hang it up, and check that a callback really comes from Twilio.

    create_call(to, twiml, status_callback)  POST /2010-04-01/Accounts/{sid}/Calls.json   → the call SID
    hang_up(call_sid)                         POST …/Calls/{call_sid}.json Status=canceled|completed
    stream_twiml(ws_url, params)              <Connect><Stream>: Twilio opens a WebSocket to us with the call's audio
    signature(auth_token, url, params)        X-Twilio-Signature = base64(HMAC-SHA1(token, url + sorted key+value))

The call's audio then flows over the media-stream WebSocket (services/phone.py): μ-law 8 kHz mono both ways.
"""

import base64
import hashlib
import hmac
from xml.sax.saxutils import quoteattr

from urllib.parse import urlencode

import httpx

from .http import http_client, provider_error

API = "https://api.twilio.com/2010-04-01"


class TwilioClient:
    def __init__(self, account_sid: str, auth_token: str, from_number: str, http: httpx.AsyncClient | None = None):
        self.account_sid, self.auth_token, self.from_number, self.http = account_sid, auth_token, from_number, http

    @property
    def auth(self) -> tuple[str, str]:
        return (self.account_sid, self.auth_token)

    async def create_call(
        self, to: str, twiml: str, status_callback: str, timeout: int = 30, machine_detection: str | None = None, amd_callback: str | None = None
    ) -> str:
        data: list[tuple[str, str]] = [
            ("To", to), ("From", self.from_number), ("Twiml", twiml), ("Timeout", str(timeout)),
            ("StatusCallback", status_callback), ("StatusCallbackMethod", "POST"),
            *(("StatusCallbackEvent", e) for e in ("initiated", "ringing", "answered", "completed")),
        ]  # fmt: skip
        if machine_detection:
            data += [("MachineDetection", machine_detection), ("AsyncAmd", "true")]
            if amd_callback:
                data += [("AsyncAmdStatusCallback", amd_callback), ("AsyncAmdStatusCallbackMethod", "POST")]
        res = await (self.http or http_client()).post(
            f"{API}/Accounts/{self.account_sid}/Calls.json", content=urlencode(data), headers={"content-type": "application/x-www-form-urlencoded"}, auth=self.auth, timeout=15
        )
        if not res.is_success:
            raise provider_error("twilio", res.status_code, res.text)
        return res.json()["sid"]

    async def hang_up(self, call_sid: str) -> None:
        """canceled stops a call that still rings; completed ends one in progress (each is a no-op on the other state)."""
        for status in ("canceled", "completed"):
            try:
                await (self.http or http_client()).post(
                    f"{API}/Accounts/{self.account_sid}/Calls/{call_sid}.json", data={"Status": status}, auth=self.auth, timeout=10
                )
            except httpx.HTTPError:
                pass

    async def check(self) -> str | None:
        """None if the credentials work, else the reason (for the pre-flight check)."""
        try:
            res = await (self.http or http_client()).get(f"{API}/Accounts/{self.account_sid}.json", auth=self.auth, timeout=10)
        except httpx.HTTPError as e:
            return f"Twilio injoignable : {e or type(e).__name__}"
        if res.status_code in (401, 403):
            return "Twilio refuse les identifiants (TWILIO_ACCOUNT_SID / TWILIO_AUTH_TOKEN)"
        if not res.is_success:
            return f"Twilio HTTP {res.status_code}"
        account = res.json()
        if account.get("type") == "Trial":
            return "Compte Twilio d'essai : il n'appelle que des numéros vérifiés et joue un message d'essai avant l'appel (passez-le en compte payant)"
        if account.get("status") != "active":
            return f"Compte Twilio {account.get('status')}"
        return None


def stream_twiml(ws_url: str, params: dict[str, str]) -> str:
    """TwiML that connects the answered call to our WebSocket (bidirectional media stream). Query strings are not allowed in
    the Stream URL: values travel as <Parameter> and come back in the stream's "start" event (customParameters)."""
    inner = "".join(f"<Parameter name={quoteattr(k)} value={quoteattr(v)}/>" for k, v in params.items())
    return f"<Response><Connect><Stream url={quoteattr(ws_url)}>{inner}</Stream></Connect></Response>"


def signature(auth_token: str, url: str, params: dict[str, str]) -> str:
    """What Twilio puts in X-Twilio-Signature for a POST to `url` with form `params`."""
    payload = url + "".join(f"{k}{params[k]}" for k in sorted(params))
    return base64.b64encode(hmac.new(auth_token.encode(), payload.encode(), hashlib.sha1).digest()).decode()


def valid_signature(auth_token: str, url: str, params: dict[str, str], header: str | None) -> bool:
    return bool(header) and hmac.compare_digest(signature(auth_token, url, params), header or "")
