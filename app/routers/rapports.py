from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from sqlalchemy import func, desc
from datetime import datetime, timedelta
import io

from app.database import get_db
from app.models import Maladie, CasEpidemique, Region

# Importation de ReportLab pour le PDF
from reportlab.lib.pagesizes import A4 # type: ignore
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm

router = APIRouter(prefix="/api/rapports", tags=["Rapports"])

# --- FONCTIONS UTILITAIRES ---

def get_period_dates(periode_type: str, periode_value: str):
    """Calcule les dates de début et de fin selon la période choisie."""
    
    #7 derniers jours pour 'weekly' et 30 pour 'monthly'
    end_date = datetime.utcnow()
    if periode_type == "weekly":
        start_date = end_date - timedelta(days=7)
    else:
        start_date = end_date - timedelta(days=30)
    return start_date, end_date

def calculate_predictions(total_cas: int, horizon_semaines: list):
    """Calcule une projection simple basée sur une tendance (pour le rapport)."""
   
    predictions = {}
    current = total_cas
    for h in horizon_semaines:
        
        projected = int(current * (1.05 ** h))
        predictions[f"{h} semaine(s)"] = projected
    return predictions

#  ENDPOINTS 

@router.get("/preview")
def get_rapport_preview(
    maladie_id: int,
    periode_type: str = Query("weekly", enum=["weekly", "monthly"]),
    horizons: str = Query("1,2,4"),
    db: Session = Depends(get_db)
):
    """Récupère les données JSON pour l'aperçu HTML."""
    maladie = db.query(Maladie).filter(Maladie.id == maladie_id).first()
    if not maladie:
        raise HTTPException(status_code=404, detail="Maladie non trouvée")

    start_date, end_date = get_period_dates(periode_type, "now")
    
    # Statistiques Globales
    stats = db.query(
        func.sum(CasEpidemique.cas_nouveaux).label('total_cas'),
        func.sum(CasEpidemique.deces).label('total_deces'),
        func.count(func.distinct(CasEpidemique.region_id)).label('nb_regions')
    ).filter(
        CasEpidemique.maladie_id == maladie_id,
        CasEpidemique.date_observation >= start_date,
        CasEpidemique.date_observation <= end_date
    ).first()

    total_cas = stats.total_cas or 0
    total_deces = stats.total_deces or 0
    taux_letalite = (total_deces / total_cas * 100) if total_cas > 0 else 0

    # Top 5 Régions
    top_regions = db.query(
        Region.nom_region,
        func.sum(CasEpidemique.cas_nouveaux).label('total_cas')
    ).join(CasEpidemique, Region.id == CasEpidemique.region_id).filter(
        CasEpidemique.maladie_id == maladie_id,
        CasEpidemique.date_observation >= start_date,
        CasEpidemique.date_observation <= end_date
    ).group_by(Region.nom_region).order_by(desc('total_cas')).limit(5).all()

    # Prévisions
    horizon_list = [int(x) for x in horizons.split(",")]
    previsions = calculate_predictions(total_cas, horizon_list)

    return {
        "maladie": maladie.nom_officiel,
        "periode": f"7 derniers jours" if periode_type == "weekly" else "30 derniers jours",
        "stats": {
            "total_cas": total_cas,
            "total_deces": total_deces,
            "taux_letalite": f"{taux_letalite:.2f}%",
            "nb_regions": stats.nb_regions or 0
        },
        "top_regions": [{"region": r.nom_region, "cas": r.total_cas} for r in top_regions],
        "previsions": previsions
    }

@router.get("/generate-pdf")
def generate_rapport_pdf(
    maladie_id: int,
    periode_type: str = Query("weekly", enum=["weekly", "monthly"]),
    horizons: str = Query("1,2,4"),
    db: Session = Depends(get_db)
):
    """Génère et télécharge le PDF du rapport."""
   
    maladie = db.query(Maladie).filter(Maladie.id == maladie_id).first()
    if not maladie:
        raise HTTPException(status_code=404, detail="Maladie non trouvée")

    start_date, end_date = get_period_dates(periode_type, "now")
    
    stats = db.query(
        func.sum(CasEpidemique.cas_nouveaux).label('total_cas'),
        func.sum(CasEpidemique.deces).label('total_deces'),
        func.count(func.distinct(CasEpidemique.region_id)).label('nb_regions')
    ).filter(
        CasEpidemique.maladie_id == maladie_id,
        CasEpidemique.date_observation >= start_date,
        CasEpidemique.date_observation <= end_date
    ).first()

    total_cas = stats.total_cas or 0
    total_deces = stats.total_deces or 0
    taux_letalite = (total_deces / total_cas * 100) if total_cas > 0 else 0

    top_regions = db.query(
        Region.nom_region,
        func.sum(CasEpidemique.cas_nouveaux).label('total_cas')
    ).join(CasEpidemique, Region.id == CasEpidemique.region_id).filter(
        CasEpidemique.maladie_id == maladie_id,
        CasEpidemique.date_observation >= start_date,
        CasEpidemique.date_observation <= end_date
    ).group_by(Region.nom_region).order_by(desc('total_cas')).limit(5).all()

    horizon_list = [int(x) for x in horizons.split(",")]
    previsions = calculate_predictions(total_cas, horizon_list)

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, topMargin=2*cm, bottomMargin=2*cm)
    elements = []
    styles = getSampleStyleSheet()
    
    # Couleurs EpiMad
    primary_color = colors.HexColor("#059669") 
    secondary_color = colors.HexColor("#F3F4F6")

    # En-tête
    title_style = ParagraphStyle('CustomTitle', parent=styles['Heading1'], fontSize=20, textColor=primary_color, alignment=1)
    elements.append(Paragraph("BULLETIN ÉPIDÉMIOLOGIQUE", title_style))
    elements.append(Paragraph(f"EpiMad - Surveillance Sanitaire", styles['Normal']))
    elements.append(Spacer(1, 0.5*cm))
    
    # Info Box
    info_style = ParagraphStyle('Info', parent=styles['Normal'], fontSize=10, textColor=colors.grey)
    elements.append(Paragraph(f"<b>Maladie :</b> {maladie.nom_officiel} | <b>Période :</b> {periode_type.upper()} | <b>Date :</b> {datetime.now().strftime('%d/%m/%Y')}", info_style))
    elements.append(Spacer(1, 1*cm))

    # Tableau Résumé
    elements.append(Paragraph("1. RÉSUMÉ GÉNÉRAL", styles['Heading2']))
    data_resume = [
        ["Indicateur", "Valeur"],
        ["Total Cas Notifiés", str(total_cas)],
        ["Total Décès", str(total_deces)],
        ["Taux de Létalité", f"{taux_letalite:.2f}%"],
        ["Régions Touchées", str(stats.nb_regions or 0)]
    ]
    t_resume = Table(data_resume, colWidths=[10*cm, 6*cm])
    t_resume.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), primary_color),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 12),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        ('BACKGROUND', (0, 1), (-1, -1), secondary_color),
        ('GRID', (0, 0), (-1, -1), 1, colors.grey),
    ]))
    elements.append(t_resume)
    elements.append(Spacer(1, 1*cm))

    #  Top 5 Régions
    elements.append(Paragraph("2. TOP 5 RÉGIONS LES PLUS TOUCHÉES", styles['Heading2']))
    data_top = [["Rang", "Région", "Nombre de Cas"]]
    for i, r in enumerate(top_regions):
        data_top.append([str(i+1), r.nom_region, str(r.total_cas)])
    
    if len(top_regions) == 0:
        data_top.append(["-", "Aucune donnée", "-"])

    t_top = Table(data_top, colWidths=[2*cm, 8*cm, 6*cm])
    t_top.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), primary_color),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 12),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        ('BACKGROUND', (0, 1), (-1, -1), secondary_color),
        ('GRID', (0, 0), (-1, -1), 1, colors.grey),
    ]))
    elements.append(t_top)
    elements.append(Spacer(1, 1*cm))

    # Prévisions
    elements.append(Paragraph("3. PRÉVISIONS (PROJECTION)", styles['Heading2']))
    data_prev = [["Horizon", "Cas Prévus (Estimation)"]]
    for h, val in previsions.items():
        data_prev.append([h, str(val)])

    t_prev = Table(data_prev, colWidths=[8*cm, 8*cm])
    t_prev.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), primary_color),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 12),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        ('BACKGROUND', (0, 1), (-1, -1), secondary_color),
        ('GRID', (0, 0), (-1, -1), 1, colors.grey),
    ]))
    elements.append(t_prev)

    # Pied de page
    elements.append(Spacer(1, 2*cm))
    footer_style = ParagraphStyle('Footer', parent=styles['Normal'], fontSize=8, textColor=colors.grey, alignment=1)
    elements.append(Paragraph("Document généré automatiquement par la plateforme EpiMad.", footer_style))

    # Build PDF
    doc.build(elements)
    buffer.seek(0)

    return StreamingResponse(
        buffer,
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename=rapport_{maladie.nom_officiel}_{datetime.now().strftime('%Y%m%d')}.pdf"}
    )