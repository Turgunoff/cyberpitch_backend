# app/api/tournaments.py
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import func, and_
from typing import Optional
from uuid import UUID
from datetime import datetime, timezone

from app.core.database import get_db
from app.core.security import get_current_user, get_current_user_optional
from app.models.users import User, Profile
from app.models.tournaments import (
    Tournament, 
    TournamentParticipant, 
    Match,
    TournamentStatus,
    MatchStatus
)
from app.schemas.tournament import (
    TournamentCreate,
    TournamentUpdate,
    TournamentResponse,
    TournamentListResponse,
    TournamentDetailResponse,
    ParticipantResponse,
    MatchResultSubmit,
    MatchResponse,
    BracketResponse
)

router = APIRouter()


def get_participant_count(db: Session, tournament_id: UUID) -> int:
    """Ishtirokchilar sonini olish"""
    return db.query(TournamentParticipant).filter(
        TournamentParticipant.tournament_id == tournament_id
    ).count()


def tournament_to_response(tournament: Tournament, db: Session) -> TournamentResponse:
    """Tournament modeldan Response yaratish"""
    return TournamentResponse(
        id=tournament.id,
        name=tournament.name,
        description=tournament.description,
        format=tournament.format,
        max_participants=tournament.max_participants,
        min_team_strength=tournament.min_team_strength,
        max_team_strength=tournament.max_team_strength,
        entry_fee=tournament.entry_fee,
        prize_pool=tournament.prize_pool,
        status=tournament.status,
        is_featured=tournament.is_featured,
        registration_start=tournament.registration_start,
        registration_end=tournament.registration_end,
        start_time=tournament.start_time,
        participant_count=get_participant_count(db, tournament.id),
        created_at=tournament.created_at
    )


# ==================== LIST & GET ====================

@router.get("/", response_model=TournamentListResponse, summary="Turnirlar ro'yxati")
def get_tournaments(
    status: Optional[TournamentStatus] = None,
    is_featured: Optional[bool] = None,
    search: Optional[str] = None,
    page: int = Query(1, ge=1),
    per_page: int = Query(10, ge=1, le=50),
    db: Session = Depends(get_db)
):
    """
    Turnirlar ro'yxatini olish (filtrlash va sahifalash bilan)
    """
    query = db.query(Tournament)
    
    # Filtrlar
    if status:
        query = query.filter(Tournament.status == status)
    
    if is_featured is not None:
        query = query.filter(Tournament.is_featured == is_featured)
    
    if search:
        query = query.filter(Tournament.name.ilike(f"%{search}%"))
    
    # Saralash - yangi turnirlar birinchi
    query = query.order_by(Tournament.created_at.desc())
    
    # Hisoblash
    total = query.count()
    
    # Sahifalash
    tournaments = query.offset((page - 1) * per_page).limit(per_page).all()
    
    # Response yaratish
    result = [tournament_to_response(t, db) for t in tournaments]
    
    return TournamentListResponse(
        tournaments=result,
        total=total,
        page=page,
        per_page=per_page,
        has_next=page * per_page < total,
        has_prev=page > 1
    )


@router.get("/featured", response_model=list[TournamentResponse], summary="Featured turnirlar")
def get_featured_tournaments(
    limit: int = Query(5, ge=1, le=20),
    db: Session = Depends(get_db)
):
    """Bosh sahifa uchun featured turnirlar"""
    tournaments = db.query(Tournament).filter(
        Tournament.is_featured == True,
        Tournament.status.in_([TournamentStatus.UPCOMING, TournamentStatus.REGISTRATION, TournamentStatus.LIVE])
    ).order_by(Tournament.start_time.asc()).limit(limit).all()
    
    return [tournament_to_response(t, db) for t in tournaments]


@router.get("/{tournament_id}", response_model=TournamentDetailResponse, summary="Turnir tafsilotlari")
def get_tournament(
    tournament_id: UUID,
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_user_optional)
):
    """Turnir haqida to'liq ma'lumot"""
    tournament = db.query(Tournament).filter(Tournament.id == tournament_id).first()
    
    if not tournament:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Turnir topilmadi"
        )
    
    # Ishtirokchilar
    participants = db.query(TournamentParticipant).filter(
        TournamentParticipant.tournament_id == tournament_id
    ).options(joinedload(TournamentParticipant.user).joinedload(User.profile)).all()
    
    participant_responses = []
    for p in participants:
        profile = p.user.profile if p.user else None
        participant_responses.append(ParticipantResponse(
            id=p.id,
            user_id=p.user_id,
            nickname=profile.nickname if profile else None,
            avatar_url=profile.avatar_url if profile else None,
            team_strength=profile.team_strength if profile else None,
            seed=p.seed,
            is_checked_in=p.is_checked_in,
            is_eliminated=p.is_eliminated,
            final_position=p.final_position,
            registered_at=p.registered_at
        ))
    
    # Hozirgi user ro'yxatdan o'tganmi?
    is_registered = False
    if current_user:
        is_registered = db.query(TournamentParticipant).filter(
            TournamentParticipant.tournament_id == tournament_id,
            TournamentParticipant.user_id == current_user.id
        ).first() is not None
    
    return TournamentDetailResponse(
        id=tournament.id,
        name=tournament.name,
        description=tournament.description,
        format=tournament.format,
        max_participants=tournament.max_participants,
        min_team_strength=tournament.min_team_strength,
        max_team_strength=tournament.max_team_strength,
        entry_fee=tournament.entry_fee,
        prize_pool=tournament.prize_pool,
        status=tournament.status,
        is_featured=tournament.is_featured,
        registration_start=tournament.registration_start,
        registration_end=tournament.registration_end,
        start_time=tournament.start_time,
        participant_count=len(participants),
        created_at=tournament.created_at,
        participants=participant_responses,
        is_registered=is_registered
    )


# ==================== CREATE & UPDATE ====================

@router.post("/", response_model=TournamentResponse, status_code=status.HTTP_201_CREATED, summary="Turnir yaratish")
def create_tournament(
    data: TournamentCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Yangi turnir yaratish (faqat admin)
    """
    # Admin tekshirish
    if not current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Faqat adminlar turnir yarataoladi"
        )
    
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
        status=TournamentStatus.UPCOMING,
        created_by=current_user.id
    )
    
    db.add(tournament)
    db.commit()
    db.refresh(tournament)
    
    return tournament_to_response(tournament, db)


@router.patch("/{tournament_id}", response_model=TournamentResponse, summary="Turnirni yangilash")
def update_tournament(
    tournament_id: UUID,
    data: TournamentUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Turnir ma'lumotlarini yangilash (faqat admin)"""
    if not current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Faqat adminlar turnirni o'zgartiraoladi"
        )
    
    tournament = db.query(Tournament).filter(Tournament.id == tournament_id).first()
    if not tournament:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Turnir topilmadi"
        )
    
    # Faqat berilgan fieldlarni yangilash
    update_data = data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(tournament, field, value)
    
    db.commit()
    db.refresh(tournament)
    
    return tournament_to_response(tournament, db)


@router.delete("/{tournament_id}", status_code=status.HTTP_204_NO_CONTENT, summary="Turnirni o'chirish")
def delete_tournament(
    tournament_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Turnirni o'chirish (faqat admin, faqat UPCOMING status)"""
    if not current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Faqat adminlar o'chira oladi"
        )
    
    tournament = db.query(Tournament).filter(Tournament.id == tournament_id).first()
    if not tournament:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Turnir topilmadi"
        )
    
    if tournament.status != TournamentStatus.UPCOMING:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Faqat UPCOMING turnirlarni o'chirish mumkin"
        )
    
    db.delete(tournament)
    db.commit()


# ==================== JOIN & LEAVE ====================

@router.post("/{tournament_id}/join", summary="Turnirga qo'shilish")
def join_tournament(
    tournament_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Turnirga ro'yxatdan o'tish"""
    tournament = db.query(Tournament).filter(Tournament.id == tournament_id).first()
    
    if not tournament:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Turnir topilmadi"
        )
    
    # Status tekshirish
    if tournament.status != TournamentStatus.REGISTRATION:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Ro'yxatdan o'tish yopiq"
        )
    
    # Vaqt tekshirish
    now = datetime.now(timezone.utc)
    if tournament.registration_end and now > tournament.registration_end:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Ro'yxatdan o'tish muddati tugagan"
        )
    
    # Allaqachon ro'yxatdan o'tganmi?
    existing = db.query(TournamentParticipant).filter(
        TournamentParticipant.tournament_id == tournament_id,
        TournamentParticipant.user_id == current_user.id
    ).first()
    
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Siz allaqachon ro'yxatdan o'tgansiz"
        )
    
    # Joy tekshirish
    count = get_participant_count(db, tournament_id)
    if count >= tournament.max_participants:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Turnir to'lgan"
        )
    
    # Team strength tekshirish
    profile = current_user.profile
    if profile and profile.team_strength:
        if profile.team_strength < tournament.min_team_strength:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Team strength kamida {tournament.min_team_strength} bo'lishi kerak"
            )
        if profile.team_strength > tournament.max_team_strength:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Team strength ko'pi bilan {tournament.max_team_strength} bo'lishi kerak"
            )
    
    # Entry fee tekshirish va yechish
    if tournament.entry_fee > 0:
        if not profile or profile.coins < tournament.entry_fee:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Yetarli coin yo'q. Kerak: {tournament.entry_fee}"
            )
        profile.coins -= tournament.entry_fee
    
    # Ro'yxatdan o'tkazish
    participant = TournamentParticipant(
        tournament_id=tournament_id,
        user_id=current_user.id
    )
    
    db.add(participant)
    db.commit()
    
    return {
        "message": "Muvaffaqiyatli ro'yxatdan o'tdingiz",
        "participant_count": count + 1
    }


@router.delete("/{tournament_id}/leave", summary="Turnirdan chiqish")
def leave_tournament(
    tournament_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Turnirdan chiqish (faqat REGISTRATION statusda)"""
    tournament = db.query(Tournament).filter(Tournament.id == tournament_id).first()
    
    if not tournament:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Turnir topilmadi"
        )
    
    if tournament.status != TournamentStatus.REGISTRATION:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Turnir boshlangan, chiqish mumkin emas"
        )
    
    participant = db.query(TournamentParticipant).filter(
        TournamentParticipant.tournament_id == tournament_id,
        TournamentParticipant.user_id == current_user.id
    ).first()
    
    if not participant:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Siz bu turnirda ro'yxatdan o'tmagansiz"
        )
    
    # Entry fee qaytarish
    if tournament.entry_fee > 0:
        profile = current_user.profile
        if profile:
            profile.coins += tournament.entry_fee
    
    db.delete(participant)
    db.commit()
    
    return {"message": "Turnirdan muvaffaqiyatli chiqdingiz"}


# ==================== BRACKET & MATCHES ====================

@router.get("/{tournament_id}/bracket", response_model=BracketResponse, summary="Turnir bracket")
def get_bracket(tournament_id: UUID, db: Session = Depends(get_db)):
    """Turnir bracketini olish"""
    tournament = db.query(Tournament).filter(Tournament.id == tournament_id).first()
    
    if not tournament:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Turnir topilmadi"
        )
    
    matches = db.query(Match).filter(
        Match.tournament_id == tournament_id
    ).order_by(Match.round_number, Match.match_number).all()
    
    match_responses = []
    for m in matches:
        # Player nicknames olish
        p1_nickname = None
        p2_nickname = None
        
        if m.player1:
            p1_profile = db.query(Profile).filter(Profile.user_id == m.player1_id).first()
            p1_nickname = p1_profile.nickname if p1_profile else None
        
        if m.player2:
            p2_profile = db.query(Profile).filter(Profile.user_id == m.player2_id).first()
            p2_nickname = p2_profile.nickname if p2_profile else None
        
        match_responses.append(MatchResponse(
            id=m.id,
            tournament_id=m.tournament_id,
            player1_id=m.player1_id,
            player2_id=m.player2_id,
            player1_nickname=p1_nickname,
            player2_nickname=p2_nickname,
            winner_id=m.winner_id,
            player1_score=m.player1_score,
            player2_score=m.player2_score,
            round_number=m.round_number,
            match_number=m.match_number,
            status=m.status,
            scheduled_time=m.scheduled_time,
            started_at=m.started_at,
            completed_at=m.completed_at
        ))
    
    # Total rounds hisoblash
    import math
    participant_count = get_participant_count(db, tournament_id)
    total_rounds = int(math.log2(participant_count)) if participant_count > 0 else 0
    
    return BracketResponse(
        tournament_id=tournament_id,
        format=tournament.format,
        total_rounds=total_rounds,
        matches=match_responses
    )


@router.post("/{tournament_id}/matches/{match_id}/result", summary="Match natijasini yuborish")
def submit_match_result(
    tournament_id: UUID,
    match_id: UUID,
    data: MatchResultSubmit,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Match natijasini yuborish"""
    match = db.query(Match).filter(
        Match.id == match_id,
        Match.tournament_id == tournament_id
    ).first()
    
    if not match:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Match topilmadi"
        )
    
    # Faqat o'yinchilar yuborishi mumkin
    if current_user.id not in [match.player1_id, match.player2_id]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Siz bu matchda o'ynamayapsiz"
        )
    
    if match.status not in [MatchStatus.READY, MatchStatus.PLAYING]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Match natija qabul qilmayapti"
        )
    
    # Natijani saqlash
    is_player1 = current_user.id == match.player1_id
    
    if is_player1:
        match.player1_score = data.my_score
        if data.screenshot_url:
            match.player1_screenshot = data.screenshot_url
    else:
        match.player2_score = data.my_score
        if data.screenshot_url:
            match.player2_screenshot = data.screenshot_url
    
    # Ikkala o'yinchi ham yuborgan bo'lsa
    if match.player1_score is not None and match.player2_score is not None:
        # Natijalar mos kelsa
        # Player1 o'z scoreni my_score ga, opponent scoreni opponent_score ga yozadi
        # Shuning uchun tekshirish murakkab - hozircha oddiy qilamiz
        match.status = MatchStatus.COMPLETED
        match.completed_at = datetime.now(timezone.utc)
        
        # Winner aniqlash
        if match.player1_score > match.player2_score:
            match.winner_id = match.player1_id
        elif match.player2_score > match.player1_score:
            match.winner_id = match.player2_id
        # Durrang bo'lsa winner_id None qoladi
    else:
        match.status = MatchStatus.PLAYING
    
    db.commit()
    
    return {"message": "Natija qabul qilindi", "status": match.status.value}
