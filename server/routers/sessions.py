from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from datetime import datetime, timedelta
from database import get_db
from models import Session as SessionModel, Movie, Hall, User
from schemas import SessionCreate, SessionResponse, SessionUpdate, SessionWithTickets
from auth import get_current_admin_user

router = APIRouter(prefix="/sessions", tags=["Sessions"])


@router.get("", response_model=list[SessionResponse])
def get_all_sessions(
    skip: int = Query(0, ge=0),
    limit: int = Query(10, ge=1, le=100),
    db: Session = Depends(get_db)
):
    sessions = db.query(SessionModel).offset(skip).limit(limit).all()
    return sessions


@router.get("/movie/{movie_id}", response_model=list[SessionResponse])
def get_sessions_by_movie(
    movie_id: int,
    skip: int = Query(0, ge=0),
    limit: int = Query(10, ge=1, le=100),
    db: Session = Depends(get_db)
):
    movie = db.query(Movie).filter(Movie.id == movie_id).first()
    if not movie:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Фильм с ID {movie_id} не найден"
        )

    sessions = db.query(SessionModel).filter(
        SessionModel.movie_id == movie_id
    ).offset(skip).limit(limit).all()

    return sessions


@router.get("/hall/{hall_id}", response_model=list[SessionResponse])
def get_sessions_by_hall(
    hall_id: int,
    skip: int = Query(0, ge=0),
    limit: int = Query(10, ge=1, le=100),
    db: Session = Depends(get_db)
):
    hall = db.query(Hall).filter(Hall.id == hall_id).first()
    if not hall:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Зал с ID {hall_id} не найден"
        )

    sessions = db.query(SessionModel).filter(
        SessionModel.hall_id == hall_id
    ).order_by(SessionModel.datetime).offset(skip).limit(limit).all()
    return sessions


@router.get("/{session_id}", response_model=SessionWithTickets)
def get_session(session_id: int, db: Session = Depends(get_db)):
    session = db.query(SessionModel).filter(SessionModel.id == session_id).first()
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Сеанс с ID {session_id} не найден"
        )
    return session


@router.post("", response_model=SessionResponse, status_code=status.HTTP_201_CREATED)
def create_session(
    session: SessionCreate,
    db: Session = Depends(get_db),
    _admin: User = Depends(get_current_admin_user),
):
    movie = db.query(Movie).filter(Movie.id == session.movie_id).first()
    if not movie:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Фильм с ID {session.movie_id} не найден"
        )

    hall = db.query(Hall).filter(Hall.id == session.hall_id).first()
    if not hall:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Зал с ID {session.hall_id} не найден"
        )

    if session.datetime < datetime.now():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Дата и время сеанса должны быть в будущем"
        )

    conflict = db.query(SessionModel).filter(
        SessionModel.hall_id == session.hall_id,
        SessionModel.datetime < session.datetime,
    ).all()
    for existing in conflict:
        if existing.datetime + timedelta(minutes=movie.duration + hall.break_minutes) > session.datetime:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Зал '{hall.name}' занят в это время"
            )

    db_session = SessionModel(
        movie_id=session.movie_id,
        hall_id=session.hall_id,
        datetime=session.datetime,
        price=session.price,
    )
    db.add(db_session)
    db.commit()
    db.refresh(db_session)
    return db_session


@router.put("/{session_id}", response_model=SessionResponse)
def update_session(
    session_id: int,
    session_update: SessionUpdate,
    db: Session = Depends(get_db),
    _admin: User = Depends(get_current_admin_user),
):
    db_session = db.query(SessionModel).filter(SessionModel.id == session_id).first()
    if not db_session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Сеанс с ID {session_id} не найден"
        )

    update_data = session_update.model_dump(exclude_unset=True)

    if "movie_id" in update_data:
        movie = db.query(Movie).filter(Movie.id == update_data["movie_id"]).first()
        if not movie:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Фильм с ID {update_data['movie_id']} не найден"
            )

    if "hall_id" in update_data:
        hall = db.query(Hall).filter(Hall.id == update_data["hall_id"]).first()
        if not hall:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Зал с ID {update_data['hall_id']} не найден"
            )

    if "datetime" in update_data and update_data["datetime"] < datetime.now():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Дата и время сеанса должны быть в будущем"
        )

    for field, value in update_data.items():
        setattr(db_session, field, value)

    db.commit()
    db.refresh(db_session)
    return db_session


@router.delete("/{session_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_session(
    session_id: int,
    db: Session = Depends(get_db),
    _admin: User = Depends(get_current_admin_user),
):
    db_session = db.query(SessionModel).filter(SessionModel.id == session_id).first()
    if not db_session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Сеанс с ID {session_id} не найден"
        )

    db.delete(db_session)
    db.commit()
