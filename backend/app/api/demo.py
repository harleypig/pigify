"""Demo-invite redeem endpoint.

Lives under `/api/demo/*` — a path meant to be reachable by un-proxied demo
visitors (see docs/DEPLOYMENT.md). Redeeming a valid invite establishes a
time-boxed session and redirects into the app; any failure redirects back
to the login screen with an error the frontend explains.
"""

import logging

from fastapi import APIRouter, Request
from fastapi.responses import RedirectResponse

from app.auth.invites import InviteError, redeem_invite
from app.config import settings

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get("/redeem")
async def redeem(request: Request, code: str):
    try:
        await redeem_invite(request, code)
    except InviteError:
        return RedirectResponse(url=f"{settings.FRONTEND_URL}/?error=demo_invalid")
    except Exception:
        logger.exception("demo invite redeem failed")
        return RedirectResponse(url=f"{settings.FRONTEND_URL}/?error=demo_failed")
    return RedirectResponse(url=f"{settings.FRONTEND_URL}/")
