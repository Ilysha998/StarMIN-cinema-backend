from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from database import get_db
from models import Hall, User
from schemas import HallCreate, HallResponse, HallUpdate
from auth import get_current_admin_user

router = APIRouter(prefix="/halls", tags=["Halls"])


def _hall_to_response(hall: Hall) -> HallResponse:
    layout = hall.layout if isinstance(hall.layout, list) else []
    return HallResponse(
        id=hall.id,
        name=hall.name,
        layout=[[str(s) for s in row] for row in layout],
        break_minutes=hall.break_minutes,
        base_price=hall.base_price,
        seat_count=hall.seat_count(),
    )


@router.get("", response_model=list[HallResponse])
def get_all_halls(
    skip: int = Query(0, ge=0),
    limit: int = Query(10, ge=1, le=100),
    db: Session = Depends(get_db),
):
    halls = db.query(Hall).offset(skip).limit(limit).all()
    return [_hall_to_response(h) for h in halls]


@router.get("/{hall_id}", response_model=HallResponse)
def get_hall(hall_id: int, db: Session = Depends(get_db)):
    hall = db.query(Hall).filter(Hall.id == hall_id).first()
    if not hall:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Зал с ID {hall_id} не найден"
        )
    return _hall_to_response(hall)


@router.post("", response_model=HallResponse, status_code=status.HTTP_201_CREATED)
def create_hall(
    hall: HallCreate,
    db: Session = Depends(get_db),
    _admin: User = Depends(get_current_admin_user),
):
    existing = db.query(Hall).filter(Hall.name == hall.name).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Зал с названием '{hall.name}' уже существует"
        )

    layout_data = [[s.value for s in row] for row in hall.layout]

    db_hall = Hall(
        name=hall.name,
        layout=layout_data,
        break_minutes=hall.break_minutes,
        base_price=hall.base_price,
    )
    db.add(db_hall)
    db.commit()
    db.refresh(db_hall)
    return _hall_to_response(db_hall)


@router.put("/{hall_id}", response_model=HallResponse)
def update_hall(
    hall_id: int,
    hall_update: HallUpdate,
    db: Session = Depends(get_db),
    _admin: User = Depends(get_current_admin_user),
):
    db_hall = db.query(Hall).filter(Hall.id == hall_id).first()
    if not db_hall:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Зал с ID {hall_id} не найден"
        )

    update_data = hall_update.model_dump(exclude_unset=True)

    if "name" in update_data:
        existing = db.query(Hall).filter(
            Hall.name == update_data["name"],
            Hall.id != hall_id,
        ).first()
        if existing:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Зал с названием '{update_data['name']}' уже существует"
            )

    if "layout" in update_data:
        update_data["layout"] = [[s.value for s in row] for row in update_data["layout"]]

    for field, value in update_data.items():
        setattr(db_hall, field, value)

    db.commit()
    db.refresh(db_hall)
    return _hall_to_response(db_hall)


@router.delete("/{hall_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_hall(
    hall_id: int,
    db: Session = Depends(get_db),
    _admin: User = Depends(get_current_admin_user),
):
    db_hall = db.query(Hall).filter(Hall.id == hall_id).first()
    if not db_hall:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Зал с ID {hall_id} не найден"
        )

    if db_hall.sessions:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Нельзя удалить зал, у которого есть сеансы"
        )

    db.delete(db_hall)
    db.commit()
