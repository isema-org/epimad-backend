from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import List, Optional

from app.database import get_db

# 🆕 IMPORTS CORRIGÉS : On importe directement depuis les fichiers .py
from app.models import Notification, User
from app.schemas import (
    NotificationCreate,
    NotificationResponse,
    NotificationUpdate,
    NotificationCountResponse,
    NotificationListResponse
)
from app.routers.auth import get_current_user

router = APIRouter(prefix="/api/notifications", tags=["Notifications"])


# =====================================================
# CRÉER UNE NOTIFICATION
# =====================================================
@router.post("/", response_model=NotificationResponse, status_code=status.HTTP_201_CREATED)
def creer_notification(
    notification: NotificationCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    destinataire = db.query(User).filter(User.id == notification.destinataire_id).first()
    if not destinataire:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Destinataire non trouvé")
    
    db_notification = Notification(
        destinataire_id=notification.destinataire_id,
        expediteur_id=notification.expediteur_id or current_user.id,
        type=notification.type,
        titre=notification.titre,
        message=notification.message,
        lien=notification.lien,
        priorite=notification.priorite
    )
    
    db.add(db_notification)
    db.commit()
    db.refresh(db_notification)
    
    return db_notification


# =====================================================
# LISTER LES NOTIFICATIONS
# =====================================================
@router.get("/", response_model=NotificationListResponse)
def lister_notifications(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    non_lues_seulement: bool = Query(False),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    query = db.query(Notification).filter(Notification.destinataire_id == current_user.id)
    
    if non_lues_seulement:
        query = query.filter(Notification.lu == False)
    
    total = query.count()
    non_lues = db.query(Notification).filter(
        Notification.destinataire_id == current_user.id,
        Notification.lu == False
    ).count()
    
    notifications = query.order_by(Notification.date_creation.desc()).offset(skip).limit(limit).all()
    
    return NotificationListResponse(
        notifications=notifications,
        total=total,
        non_lues=non_lues
    )


# =====================================================
# COMPTER LES NOTIFICATIONS NON LUES (BADGE)
# =====================================================
@router.get("/non-lues/count", response_model=NotificationCountResponse)
def compter_notifications_non_lues(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    count = db.query(Notification).filter(
        Notification.destinataire_id == current_user.id,
        Notification.lu == False
    ).count()
    
    return NotificationCountResponse(non_lues=count)


# =====================================================
# MARQUER COMME LUE
# =====================================================
@router.put("/{notification_id}/lu", response_model=NotificationResponse)
def marquer_comme_lue(
    notification_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    notification = db.query(Notification).filter(
        Notification.id == notification_id,
        Notification.destinataire_id == current_user.id
    ).first()
    
    if not notification:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Notification non trouvée")
    
    if not notification.lu:
        notification.lu = True
        notification.date_lecture = func.now()
        db.commit()
        db.refresh(notification)
    
    return notification


# =====================================================
# MARQUER TOUTES COMME LUES
# =====================================================
@router.put("/marquer-toutes-lues")
def marquer_toutes_comme_lues(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    result = db.query(Notification).filter(
        Notification.destinataire_id == current_user.id,
        Notification.lu == False
    ).update({"lu": True, "date_lecture": func.now()})
    
    db.commit()
    
    return {"message": f"{result} notification(s) marquée(s) comme lue(s)", "non_lues": 0}


# =====================================================
# SUPPRIMER UNE NOTIFICATION
# =====================================================
@router.delete("/{notification_id}", status_code=status.HTTP_204_NO_CONTENT)
def supprimer_notification(
    notification_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    notification = db.query(Notification).filter(
        Notification.id == notification_id,
        Notification.destinataire_id == current_user.id
    ).first()
    
    if not notification:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Notification non trouvée")
    
    db.delete(notification)
    db.commit()
    return None