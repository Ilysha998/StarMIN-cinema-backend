import secrets
from collections import defaultdict
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from database import get_db
from models import Ticket, Session as SessionModel, Hall, User
from schemas import (
    TicketCreate, TicketResponse, TicketUpdate,
    MultiTicketCreate, SeatPosition, SeatMapResponse, SeatMapCell,
)
from auth import get_current_user, get_current_admin_user, get_optional_current_user
from config import settings

router = APIRouter(prefix="/tickets", tags=["Tickets"])


def _generate_qr_token() -> str:
    return secrets.token_urlsafe(32)


def _calc_price(base_price: float, seat_type: str) -> float:
    multiplier = settings.SEAT_TYPE_MULTIPLIERS.get(seat_type, 1.0)
    return round(base_price * multiplier, 2)


def _validate_seat_in_layout(layout: list[list[str]], row: int, col: int) -> str:
    if row < 0 or row >= len(layout):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Ряд {row} не существует (допустимо 0-{len(layout) - 1})"
        )
    row_data = layout[row]
    if col < 0 or col >= len(row_data):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Место {col} в ряду {row} не существует (допустимо 0-{len(row_data) - 1})"
        )
    seat_type = row_data[col]
    if seat_type == "empty":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Позиция ряд {row} место {col} — не является сиденьем"
        )
    return seat_type


def _check_anti_hoarding(
    db: Session,
    session_id: int,
    requested_count: int,
    current_user: Optional[User],
):
    if requested_count > settings.MAX_SEATS_PER_PURCHASE:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Максимум {settings.MAX_SEATS_PER_PURCHASE} мест за одну покупку"
        )

    if current_user:
        user_tickets_count = db.query(Ticket).filter(
            Ticket.session_id == session_id,
            Ticket.user_id == current_user.id,
        ).count()
        if user_tickets_count + requested_count > settings.MAX_SEATS_PER_USER_PER_SESSION:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    f"У вас уже {user_tickets_count} билетов на этот сеанс. "
                    f"Максимум {settings.MAX_SEATS_PER_USER_PER_SESSION} на пользователя"
                ),
            )


def _check_contiguous_in_row(
    selected_positions: list[SeatPosition],
    layout: list[list[str]],
):
    rows_map: dict[int, list[int]] = defaultdict(list)
    for pos in selected_positions:
        rows_map[pos.row].append(pos.col)

    for row_idx, cols in rows_map.items():
        if len(cols) <= 1:
            continue
        sorted_cols = sorted(cols)
        for i in range(1, len(sorted_cols)):
            gap_start = sorted_cols[i - 1] + 1
            gap_end = sorted_cols[i]
            for c in range(gap_start, gap_end):
                if 0 <= c < len(layout[row_idx]) and layout[row_idx][c] != "empty":
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=(
                            f"Нельзя купить места через одно: в ряду {row_idx} "
                            f"между местами {sorted_cols[i - 1]} и {sorted_cols[i]} "
                            f"есть свободное сиденье {c}"
                        ),
                    )


def _check_no_orphan_creation(
    selected_positions: list[SeatPosition],
    layout: list[list[str]],
    already_booked: set[tuple[int, int]],
):
    rows_map: dict[int, list[int]] = defaultdict(list)
    for pos in selected_positions:
        rows_map[pos.row].append(pos.col)

    for row_idx, new_cols in rows_map.items():
        row_data = layout[row_idx]
        occupied_in_row = {c for (r, c) in already_booked if r == row_idx}
        new_cols_set = set(new_cols)
        all_occupied = occupied_in_row | new_cols_set

        for col in range(len(row_data)):
            if row_data[col] == "empty":
                continue
            if col in all_occupied:
                continue

            left_occ = (
                col > 0
                and row_data[col - 1] != "empty"
                and (col - 1) in all_occupied
            )
            right_occ = (
                col < len(row_data) - 1
                and row_data[col + 1] != "empty"
                and (col + 1) in all_occupied
            )

            if left_occ and right_occ:
                was_left = (col - 1) in occupied_in_row
                was_right = (col + 1) in occupied_in_row
                if not (was_left and was_right):
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=(
                            f"Покупка оставит одиночное свободное место "
                            f"в ряду {row_idx}, позиция {col} — это запрещено"
                        ),
                    )


@router.get("/my", response_model=list[TicketResponse])
def get_my_tickets(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    tickets = db.query(Ticket).filter(Ticket.user_id == current_user.id).all()
    return tickets


@router.get("/{ticket_id}", response_model=TicketResponse)
def get_ticket(
    ticket_id: int,
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_optional_current_user),
):
    ticket = db.query(Ticket).filter(Ticket.id == ticket_id).first()
    if not ticket:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Билет с ID {ticket_id} не найден"
        )

    if current_user:
        if ticket.user_id != current_user.id and not current_user.is_admin:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Можно просматривать только свои билеты"
            )
    else:
        if not ticket.qr_token:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Требуется авторизация для просмотра билета без QR-токена"
            )

    return ticket


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


@router.get("/session/{session_id}/seat-map", response_model=SeatMapResponse)
def get_seat_map(
    session_id: int,
    db: Session = Depends(get_db),
):
    session = db.query(SessionModel).filter(SessionModel.id == session_id).first()
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Сеанс с ID {session_id} не найден"
        )

    hall = db.query(Hall).filter(Hall.id == session.hall_id).first()
    if not hall:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Зал не найден для данного сеанса"
        )

    layout = hall.layout if isinstance(hall.layout, list) else []

    booked = db.query(Ticket.seat_row, Ticket.seat_col).filter(
        Ticket.session_id == session_id
    ).all()
    booked_set = {(r, c) for r, c in booked}

    seat_map: list[list[SeatMapCell]] = []
    available_count = 0
    booked_count = 0
    total_seats = 0

    for row_idx, row_data in enumerate(layout):
        map_row: list[SeatMapCell] = []
        for col_idx, seat_type in enumerate(row_data):
            if seat_type == "empty":
                map_row.append(SeatMapCell(type="empty", status="none"))
            elif (row_idx, col_idx) in booked_set:
                map_row.append(SeatMapCell(type=str(seat_type), status="booked"))
                booked_count += 1
                total_seats += 1
            else:
                map_row.append(SeatMapCell(type=str(seat_type), status="available"))
                available_count += 1
                total_seats += 1
        seat_map.append(map_row)

    return SeatMapResponse(
        session_id=session_id,
        hall_id=hall.id,
        hall_name=hall.name,
        seat_map=seat_map,
        available_count=available_count,
        booked_count=booked_count,
        total_seats=total_seats,
    )


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


@router.post("/buy", response_model=list[TicketResponse], status_code=status.HTTP_201_CREATED)
def buy_tickets(
    payload: MultiTicketCreate,
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_optional_current_user),
):
    session = db.query(SessionModel).filter(
        SessionModel.id == payload.session_id
    ).first()
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Сеанс с ID {payload.session_id} не найден"
        )

    hall = db.query(Hall).filter(Hall.id == session.hall_id).first()
    if not hall:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Зал не найден"
        )

    layout = hall.layout if isinstance(hall.layout, list) else []
    seat_count = len(payload.seats)

    _check_anti_hoarding(db, payload.session_id, seat_count, current_user)

    seat_types: dict[tuple[int, int], str] = {}
    for pos in payload.seats:
        st = _validate_seat_in_layout(layout, pos.row, pos.col)
        seat_types[(pos.row, pos.col)] = st

    existing = db.query(Ticket.seat_row, Ticket.seat_col).filter(
        Ticket.session_id == payload.session_id,
    ).all()
    booked_set = {(r, c) for r, c in existing}

    for pos in payload.seats:
        if (pos.row, pos.col) in booked_set:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Место ряд {pos.row}, позиция {pos.col} уже занято"
            )

    _check_contiguous_in_row(payload.seats, layout)
    _check_no_orphan_creation(payload.seats, layout, booked_set)

    tickets: list[Ticket] = []
    for pos in payload.seats:
        st = seat_types[(pos.row, pos.col)]
        price = _calc_price(session.price, st)
        db_ticket = Ticket(
            session_id=payload.session_id,
            user_id=current_user.id if current_user else None,
            seat_row=pos.row,
            seat_col=pos.col,
            seat_type=st,
            price=price,
            is_paid=False,
            phone=payload.phone,
            email=payload.email,
            qr_token=_generate_qr_token(),
        )
        db.add(db_ticket)
        tickets.append(db_ticket)

    db.commit()
    for t in tickets:
        db.refresh(t)

    return tickets


@router.post("", response_model=TicketResponse, status_code=status.HTTP_201_CREATED)
def buy_single_ticket(
    ticket: TicketCreate,
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_optional_current_user),
):
    multi = MultiTicketCreate(
        session_id=ticket.session_id,
        seats=[SeatPosition(row=ticket.seat_row, col=ticket.seat_col)],
        phone=ticket.phone,
        email=ticket.email,
    )
    results = buy_tickets(multi, db, current_user)
    return results[0]


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
