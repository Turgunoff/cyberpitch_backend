from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import List, Optional
from uuid import UUID

from app.core.database import get_db
from app.models.tournaments import Tournament, TournamentParticipant, TournamentStatus
from app.models.users import User
from app.schemas.tournament import (
    TournamentCreate, 
    TournamentResponse, 
    TournamentListResponse,
    JoinTournamentRequest
)
from app.core.auth import get_current_user  # Bu keyin yaratamiz

router = APIRouter()

@router.get("/", response_model=TournamentListResponse)
def get_tournaments(
    status: Optional[TournamentStatus] = None,
    page: int = Query(1, ge=1),
    per_page: int = Query(10, ge=1, le=50),
    db: Session = Depends(get_db)
):
    query = db.query(Tournament)
    
    if status:
        query = query.filter(Tournament.status == status)
    
    total = query.count()
    tournaments = query.offset((page - 1) * per_page).limit(per_page).all()
    
    # Participant count qo'shish
    result = []
    for t in tournaments:
        participant_count = db.query(TournamentParticipant).filter(
            TournamentParticipant.tournament_id == t.id
        ).count()
        
        result.append(TournamentResponse(
            id=t.id,
            name=t.name,
            description=t.description,
            format=t.format,
            max_participants=t.max_participants,
            entry_fee=t.entry_fee,
            prize_pool=t.prize_pool,
            status=t.status,
            is_featured=t.is_featured,
            start_time=t.start_time,
            participant_count=participant_count,
            created_at=t.created_at
        ))
    
    return TournamentListResponse(
        tournaments=result,
        total=total,
        page=page,
        per_page=per_page
    )

@router.get("/{tournament_id}", response_model=TournamentResponse)
def get_tournament(tournament_id: UUID, db: Session = Depends(get_db)):
    tournament = db.query(Tournament).filter(Tournament.id == tournament_id).first()
    if not tournament:
        raise HTTPException(status_code=404, detail="Turnir topilmadi")
    
    participant_count = db.query(TournamentParticipant).filter(
        TournamentParticipant.tournament_id == tournament_id
    ).count()
    
    return TournamentResponse(
        id=tournament.id,
        name=tournament.name,
        description=tournament.description,
        format=tournament.format,
        max_participants=tournament.max_participants,
        entry_fee=tournament.entry_fee,
        prize_pool=tournament.prize_pool,
        status=tournament.status,
        is_featured=tournament.is_featured,
        start_time=tournament.start_time,
        participant_count=participant_count,
        created_at=tournament.created_at
    )

@router.post("/", response_model=TournamentResponse)
def create_tournament(
    data: TournamentCreate,
    db: Session = Depends(get_db)
    # current_user: User = Depends(get_current_user)  # Admin check keyin
):
    tournament = Tournament(
        name=data.name,
        description=data.description,
        format=data.format,
        max_participants=data.max_participants,
        min_team_strength=data.min_team_strength,
        max_team_strength=data.max_team_strength,
        entry_fee=data.entry_fee,
        prize_pool=data.prize_pool,
        registration_start=data.registration_start,
        registration_end=data.registration_end,
        start_time=data.start_time,
        status=TournamentStatus.UPCOMING
    )
    
    db.add(tournament)
    db.commit()
    db.refresh(tournament)
    
    return TournamentResponse(
        id=tournament.id,
        name=tournament.name,
        description=tournament.description,
        format=tournament.format,
        max_participants=tournament.max_participants,
        entry_fee=tournament.entry_fee,
        prize_pool=tournament.prize_pool,
        status=tournament.status,
        is_featured=tournament.is_featured,
        start_time=tournament.start_time,
        participant_count=0,
        created_at=tournament.created_at
    )

@router.post("/{tournament_id}/join")
def join_tournament(
    tournament_id: UUID,
    db: Session = Depends(get_db),
    # current_user: User = Depends(get_current_user)
):
    # Hozircha test user
    test_user_id = "test-user-id"  # Bu keyin o'zgaradi
    
    tournament = db.query(Tournament).filter(Tournament.id == tournament_id).first()
    if not tournament:
        raise HTTPException(status_code=404, detail="Turnir topilmadi")
    
    if tournament.status != TournamentStatus.REGISTRATION:
        raise HTTPException(status_code=400, detail="Ro'yxatdan o'tish yopiq")
    
    # Allaqachon ro'yxatdan o'tganmi?
    existing = db.query(TournamentParticipant).filter(
        TournamentParticipant.tournament_id == tournament_id,
        # TournamentParticipant.user_id == current_user.id
    ).first()
    
    if existing:
        raise HTTPException(status_code=400, detail="Siz allaqachon ro'yxatdan o'tgansiz")
    
    # Participant count tekshirish
    count = db.query(TournamentParticipant).filter(
        TournamentParticipant.tournament_id == tournament_id
    ).count()
    
    if count >= tournament.max_participants:
        raise HTTPException(status_code=400, detail="Turnir to'lgan")
    
    # Entry fee tekshirish (keyin qo'shiladi)
    
    participant = TournamentParticipant(
        tournament_id=tournament_id,
        # user_id=current_user.id
    )
    
    db.add(participant)
    db.commit()
    
    return {"message": "Muvaffaqiyatli ro'yxatdan o'tdingiz"}