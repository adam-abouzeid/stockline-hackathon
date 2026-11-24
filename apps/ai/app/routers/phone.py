"""
Real phone calls (PHONE_MODE=twilio), logic in app/services/phone.py.

    POST /phone/calls                  the ERP placed a call: ring the demo phone (backend → here)
    POST /phone/calls/{id}/hangup      the ERP cancelled it (pause) or it expired
    WS   /phone/stream                 Twilio's media stream (the call's audio, both ways)
    POST /phone/twilio/status          Twilio status callback (no-answer, busy, completed…), signature checked
    POST /phone/twilio/amd             Twilio answering-machine verdict (PHONE_MACHINE_DETECTION=1), signature checked
    GET  /phone/config                 is everything set? (?check=1 also asks Twilio and tries the tunnel)
    GET  /phone/live                   SSE: the events of the call in progress, for the « Appel en cours » panel
"""

from urllib.parse import parse_qsl

from fastapi import APIRouter, Request, WebSocket
from fastapi.responses import JSONResponse, StreamingResponse

from app.clients.twilio import valid_signature
from app.config import settings
from app.schemas import ErrorResponse
from app.schemas.base import WireModel
from app.services import phone
from app.services.phone_live import live

router = APIRouter(prefix="/phone", tags=["phone"])


class PlaceCall(WireModel):
    call_id: str
    opportunity_id: str


def error(status: int, message: str) -> JSONResponse:
    return JSONResponse(ErrorResponse.of("phone", message), status_code=status)


@router.post("/calls")
async def place_call(body: PlaceCall):
    """Ring the demo phone (DEMO_PHONE_TO, never a client's number) for a call the ERP placed and that is still ringing."""
    try:
        return await phone.place_call(body.call_id, body.opportunity_id)
    except phone.PhoneError as e:
        return error(e.status, str(e))


@router.post("/calls/{call_id}/hangup")
async def hang_up(call_id: str):
    return await phone.hang_up(call_id)


@router.websocket("/stream")
async def stream(ws: WebSocket):
    await phone.accept_stream(ws)


async def twilio_form(request: Request) -> dict[str, str] | None:
    """The callback's form, or None when the X-Twilio-Signature does not match (not Twilio, or a wrong PUBLIC_URL)."""
    params = dict(parse_qsl((await request.body()).decode("utf-8", "replace"), keep_blank_values=True))  # x-www-form-urlencoded
    if not settings.phone.validate_signature:
        return params
    url = settings.phone.public_url + request.url.path + (f"?{request.url.query}" if request.url.query else "")
    if not valid_signature(settings.phone.auth_token, url, params, request.headers.get("x-twilio-signature")):
        print(f"[phone] refused a Twilio callback with a bad signature ({url})", flush=True)
        return None
    return params


@router.post("/twilio/status")
async def twilio_status(request: Request, callId: str = ""):  # noqa: N803  (Twilio's query parameter, our name)
    params = await twilio_form(request)
    if params is None:
        return error(403, "signature Twilio invalide")
    await phone.on_twilio_status(callId, params)
    return {"ok": True}


@router.post("/twilio/amd")
async def twilio_amd(request: Request, callId: str = ""):  # noqa: N803
    params = await twilio_form(request)
    if params is None:
        return error(403, "signature Twilio invalide")
    await phone.on_amd(callId, params)
    return {"ok": True}


@router.get("/config")
async def config(check: bool = False):
    """{mode, ready, problems[], demoNumber (masked), activeCallId}. With check=1: also asks Twilio whether the account works
    and whether the tunnel (PUBLIC_URL) really reaches this service: run it before each rehearsal."""
    problems = phone.problems()
    if check and settings.phone.mode == "twilio":
        if settings.phone.account_sid and settings.phone.auth_token and (why := await phone.twilio().check()):
            problems.append(why)
        if settings.phone.public_url.startswith("https://"):
            problems += await tunnel_problems()
    current = phone.active_call()
    return {
        "mode": settings.phone.mode if settings.phone.mode in ("twilio", "simulator") else "simulator",
        "ready": not problems,
        "problems": problems,
        "demoNumber": phone.masked(settings.phone.to_number),
        "publicUrl": settings.phone.public_url,
        "activeCallId": current.call_id if current else None,
    }


async def tunnel_problems() -> list[str]:
    from app.clients.http import http_client

    try:
        res = await http_client().get(f"{settings.phone.public_url}/health", timeout=8, headers={"ngrok-skip-browser-warning": "1"})
        return [] if res.is_success else [f"PUBLIC_URL répond HTTP {res.status_code} : le tunnel ne mène pas à ce service (port 4100) ?"]
    except Exception as e:  # noqa: BLE001
        return [f"PUBLIC_URL injoignable ({type(e).__name__}) : le tunnel est-il lancé ?"]


@router.get("/live")
async def live_events():
    """Server-Sent Events: each event of the current call (status, caller transcript, agent text, tools, latency)."""
    return StreamingResponse(live.stream(), media_type="text/event-stream", headers={"cache-control": "no-cache", "x-accel-buffering": "no"})
