from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from database import get_db
from models import User, Ticket
from schemas import UserCreate, UserResponse, UserUpdate, TokenResponse
from auth import (
    hash_password, verify_password, create_access_token,
    get_current_user, get_current_admin_user,
)

router = APIRouter(prefix="/users", tags=["Users"])


def _link_tickets_to_user(db: Session, user: User):
    orphan_tickets = db.query(Ticket).filter(Ticket.user_id.is_(None))
    linked = 0
    if user.email:
        matches = orphan_tickets.filter(Ticket.email == user.email).all()
        for t in matches:
            t.user_id = user.id
            linked += 1
    if user.phone:
        matches = db.query(Ticket).filter(
            Ticket.user_id.is_(None),
            Ticket.phone == user.phone,
        ).all()
        for t in matches:
            t.user_id = user.id
            linked += 1
    if linked:
        db.commit()


@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
def register(user: UserCreate, db: Session = Depends(get_db)):
    existing_user = db.query(User).filter(User.login == user.login).first()
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Пользователь с таким логином уже существует"
        )

    if user.email:
        existing_email = db.query(User).filter(User.email == user.email).first()
        if existing_email:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Пользователь с таким email уже существует"
            )

    if user.phone:
        existing_phone = db.query(User).filter(User.phone == user.phone).first()
        if existing_phone:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Пользователь с таким телефоном уже существует"
            )

    db_user = User(
        login=user.login,
        password=hash_password(user.password),
        is_admin=user.is_admin,
        phone=user.phone,
        email=user.email,
    )
    db.add(db_user)
    db.commit()
    db.refresh(db_user)

    _link_tickets_to_user(db, db_user)

    return db_user


@router.post("/login", response_model=TokenResponse)
def login(form: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    user = db.query(User).filter(User.login == form.username).first()

    if not user or not verify_password(form.password, user.password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Неверный логин или пароль",
            headers={"WWW-Authenticate": "Bearer"}
        )

    access_token = create_access_token(data={"sub": str(user.id)})

    _link_tickets_to_user(db, user)

    return TokenResponse(
        access_token=access_token,
        user_id=user.id,
        login=user.login,
        is_admin=user.is_admin,
    )


@router.get("/me", response_model=UserResponse)
def get_current_user_info(current_user: User = Depends(get_current_user)):
    return current_user


@router.get("/me/tickets")
def get_my_tickets(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    from models import Ticket, Session as SessionModel, Movie
    tickets = db.query(Ticket).filter(Ticket.user_id == current_user.id).all()
    result = []
    for t in tickets:
        session = db.query(SessionModel).filter(SessionModel.id == t.session_id).first()
        movie = db.query(Movie).filter(Movie.id == session.movie_id).first() if session else None
        result.append({
            "id": t.id,
            "seat_number": t.seat_number,
            "is_paid": t.is_paid,
            "qr_token": t.qr_token,
            "session_id": t.session_id,
            "session_datetime": session.datetime.isoformat() if session else None,
            "hall": session.hall if session else None,
            "price": session.price if session else None,
            "movie_title": movie.title if movie else None,
        })
    return result


@router.get("", response_model=list[UserResponse])
def get_all_users(
    skip: int = 0,
    limit: int = 10,
    db: Session = Depends(get_db),
    _admin: User = Depends(get_current_admin_user),
):
    users = db.query(User).offset(skip).limit(limit).all()
    return users


@router.get("/{user_id}", response_model=UserResponse)
def get_user(
    user_id: int,
    db: Session = Depends(get_db),
    _current: User = Depends(get_current_user),
):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Пользователь с ID {user_id} не найден"
        )
    return user


@router.put("/{user_id}", response_model=UserResponse)
def update_user(
    user_id: int,
    user_update: UserUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if current_user.id != user_id and not current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Можно обновлять только свой профиль"
        )

    db_user = db.query(User).filter(User.id == user_id).first()
    if not db_user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Пользователь с ID {user_id} не найден"
        )

    update_data = user_update.model_dump(exclude_unset=True)

    if "is_admin" in update_data and not current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Только администратор может менять роль"
        )

    if "password" in update_data and update_data["password"]:
        update_data["password"] = hash_password(update_data["password"])

    for field, value in update_data.items():
        setattr(db_user, field, value)

    db.commit()
    db.refresh(db_user)

    if "phone" in update_data or "email" in update_data:
        _link_tickets_to_user(db, db_user)

    return db_user


@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_user(
    user_id: int,
    db: Session = Depends(get_db),
    _admin: User = Depends(get_current_admin_user),
):
    db_user = db.query(User).filter(User.id == user_id).first()
    if not db_user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Пользователь с ID {user_id} не найден"
        )

    db.delete(db_user)
    db.commit()


@router.post("/change-password/{user_id}", status_code=status.HTTP_200_OK)
def change_password(
    user_id: int,
    old_password: str,
    new_password: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if current_user.id != user_id and not current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Можно менять только свой пароль"
        )

    db_user = db.query(User).filter(User.id == user_id).first()
    if not db_user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Пользователь с ID {user_id} не найден"
        )

    if not current_user.is_admin and not verify_password(old_password, db_user.password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Неверный текущий пароль"
        )

    db_user.password = hash_password(new_password)
    db.commit()

    return {"message": "Пароль успешно изменён"}
