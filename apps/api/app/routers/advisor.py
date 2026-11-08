"""Advisor chat API (web, WhatsApp and voice all use the same engine)."""

from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.ratelimit import limit
from app.core.security import scoped_token, verify_scoped_token
from app.db import get_db
from app.models import AdvisorSession
from app.services.advisor import engine

router = APIRouter(prefix="/advisor", tags=["advisor"])
Db = Annotated[Session, Depends(get_db)]


class StartIn(BaseModel):
    channel: Literal["web", "voice"] = "web"
    language: Literal["en", "hi", "hinglish"] | None = None


class MessageIn(BaseModel):
    text: str = Field(min_length=1, max_length=1000)


@router.post("/sessions", status_code=201, dependencies=[Depends(limit(20, 60))])
def start_session(body: StartIn, db: Db):
    session, first = engine.start(db, body.channel, body.language)
    db.commit()
    return {"session_id": session.id, "token": scoped_token("advisor", session.id), **first}


@router.post("/sessions/{session_id}/messages", dependencies=[Depends(limit(40, 60))])
def send_message(
    session_id: int,
    body: MessageIn,
    db: Db,
    x_session_token: Annotated[str | None, Header()] = None,
):
    session = db.get(AdvisorSession, session_id)
    if session is None or not verify_scoped_token("advisor", session_id, x_session_token):
        raise HTTPException(404, "Not found")
    out = engine.handle(db, session, body.text)
    db.commit()
    return out
