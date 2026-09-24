import sqlite3
from datetime import date

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from dashboard.backend.deps import get_db
from summarizer.chat import ask as ask_chat

router = APIRouter()


class ChatIn(BaseModel):
    question: str


@router.post("")
def ask(chat_in: ChatIn, conn: sqlite3.Connection = Depends(get_db)):
    if not chat_in.question.strip():
        raise HTTPException(400, "question cannot be empty")
    try:
        result = ask_chat(conn, chat_in.question.strip(), today=date.today())
    except Exception as e:
        raise HTTPException(502, f"chat failed: {e}")
    return result
