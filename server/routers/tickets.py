import secrets
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from database import get_db
from models import Ticket, Session as SessionModel, User
from schemas import TicketCreate, TicketResponse, TicketUpdate
from config import HALL_CONFIG
from auth import get_current_user, get_current_admin_user, get_optional_current_user

router = APIRouter(prefix="/tickets", tags=["Tickets"])


def _generate_qr_token() -> str:
    return secrets.token_urlsafe(32)


@router.get("/my", response_model=list[TicketResponse])
def get_my_tickets(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    tickets = db.query(Ticket).filter(Ticket.user_id == current_user.id).all()
    return tickets


@router.get("", response_model=list[TicketResponse])
def get_all_tickets(
    session_id: int = Query(None, description="Фильтр по ID сеанса"),
    is_paid: bool = Query(None, description="Фильтр по статусу оплаты"),
    skip: int = Query(0, ge=0),
    limit: int = Query(10, ge=1, le=100),
    db: Session = Depends(get_db),
    _admin: User = Depends(get_current_admin_user),
):
    query = db.query(Ticket)

    if session_id is not None:
        query = query.filter(Ticket.session_id == session_id)

    if is_paid is not None:
        query = query.filter(Ticket.is_paid == is_paid)

    tickets = query.offset(skip).limit(limit).all()
    return tickets


@router.get("/session/{session_id}", response_model=list[TicketResponse])
def get_tickets_by_session(
    session_id: int,
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    db: Session = Depends(get_db),
):
    session = db.query(SessionModel).filter(SessionModel.id == session_id).first()
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Сеанс с ID {session_id} не найден"
        )

    tickets = db.query(Ticket).filter(
        Ticket.session_id == session_id
    ).offset(skip).limit(limit).all()

    return tickets


@router.get("/session/{session_id}/available-seats")
def get_available_seats(
    session_id: int,
    db: Session = Depends(get_db),
):
    session = db.query(SessionModel).filter(SessionModel.id == session_id).first()
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Сеанс с ID {session_id} не найден"
        )

    hall_cfg = HALL_CONFIG.get(session.hall, {"seats": 100})
    max_seats = hall_cfg["seats"]

    booked_seats = db.query(Ticket.seat_number).filter(
        Ticket.session_id == session_id
    ).all()

    booked_numbers = {seat[0] for seat in booked_seats}
    available_seats = [i for i in range(1, max_seats + 1) if i not in booked_numbers]

    return {
        "session_id": session_id,
        "hall": session.hall,
        "total_seats": max_seats,
        "booked_count": len(booked_numbers),
        "available_count": len(available_seats),
        "available_seats": available_seats
    }


@router.get("/statistics/sales")
def get_sales_statistics(
    db: Session = Depends(get_db),
    _admin: User = Depends(get_current_admin_user),
):
    total_tickets = db.query(Ticket).count()
    paid_tickets = db.query(Ticket).filter(Ticket.is_paid == True).count()
    unpaid_tickets = db.query(Ticket).filter(Ticket.is_paid == False).count()

    sessions_count = db.query(SessionModel).count()

    return {
        "total_tickets_sold": total_tickets,
        "paid_tickets": paid_tickets,
        "unpaid_tickets": unpaid_tickets,
        "payment_percentage": round((paid_tickets / total_tickets * 100), 2) if total_tickets > 0 else 0,
        "total_sessions": sessions_count,
        "average_tickets_per_session": round(total_tickets / sessions_count, 2) if sessions_count > 0 else 0
    }


@router.post("", response_model=TicketResponse, status_code=status.HTTP_201_CREATED)
def buy_ticket(
    ticket: TicketCreate,
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_optional_current_user),
):
    session = db.query(SessionModel).filter(
        SessionModel.id == ticket.session_id
    ).first()
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Сеанс с ID {ticket.session_id} не найден"
        )

    hall_cfg = HALL_CONFIG.get(session.hall, {"seats": 100})
    max_seats = hall_cfg["seats"]

    if ticket.seat_number < 1 or ticket.seat_number > max_seats:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Номер места должен быть от 1 до {max_seats} (зал {session.hall})"
        )

    existing_ticket = db.query(Ticket).filter(
        Ticket.session_id == ticket.session_id,
        Ticket.seat_number == ticket.seat_number
    ).first()

    if existing_ticket:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Место #{ticket.seat_number} на этом сеансе уже занято"
        )

    db_ticket = Ticket(
        session_id=ticket.session_id,
        user_id=current_user.id if current_user else None,
        seat_number=ticket.seat_number,
        is_paid=False,
        phone=ticket.phone,
        email=ticket.email,
        qr_token=_generate_qr_token(),
    )

    db.add(db_ticket)
    db.commit()
    db.refresh(db_ticket)

    return db_ticket


@router.put("/{ticket_id}", response_model=TicketResponse)
def update_ticket(
    ticket_id: int,
    ticket_update: TicketUpdate,
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_optional_current_user),
):
    db_ticket = db.query(Ticket).filter(Ticket.id == ticket_id).first()
    if not db_ticket:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Билет с ID {ticket_id} не найден"
        )

    update_data = ticket_update.model_dump(exclude_unset=True)
    is_paying = update_data.get("is_paid") is True and len(update_data) == 1

    if is_paying:
        pass
    elif current_user:
        if db_ticket.user_id != current_user.id and not current_user.is_admin:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Можно обновлять только свои билеты"
            )
    else:
        if not ticket_update.qr_token or db_ticket.qr_token != ticket_update.qr_token:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Требуется авторизация или валидный qr_token"
            )

    update_data.pop("qr_token", None)
    for field, value in update_data.items():
        setattr(db_ticket, field, value)

    db.commit()
    db.refresh(db_ticket)
    return db_ticket


@router.delete("/{ticket_id}", status_code=status.HTTP_204_NO_CONTENT)
def cancel_ticket(
    ticket_id: int,
    qr_token: Optional[str] = Query(None, description="QR-токен билета (для неавторизованных)"),
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_optional_current_user),
):
    db_ticket = db.query(Ticket).filter(Ticket.id == ticket_id).first()
    if not db_ticket:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Билет с ID {ticket_id} не найден"
        )

    if current_user:
        if db_ticket.user_id != current_user.id and not current_user.is_admin:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Можно отменять только свои билеты"
            )
    else:
        if not qr_token or db_ticket.qr_token != qr_token:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Требуется авторизация или валидный qr_token"
            )

    db.delete(db_ticket)
    db.commit()
