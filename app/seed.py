"""Seed the database with 1-2 demo patient records (idempotent)."""

import logging
from datetime import date

from app.database import SessionLocal
from app.models.patient import Patient

logger = logging.getLogger(__name__)

SEED_PATIENTS = [
    {
        "first_name": "Maria",
        "last_name": "Garcia",
        "date_of_birth": date(1985, 3, 15),
        "sex": "Female",
        "phone_number": "5551234567",
        "email": "maria.garcia@email.com",
        "address_line_1": "742 Evergreen Terrace",
        "address_line_2": "Apt 4B",
        "city": "Springfield",
        "state": "IL",
        "zip_code": "62704",
        "insurance_provider": "Blue Cross Blue Shield",
        "insurance_member_id": "BCBS-9876543210",
        "preferred_language": "Spanish",
        "emergency_contact_name": "Carlos Garcia",
        "emergency_contact_phone": "5559876543",
    },
    {
        "first_name": "James",
        "last_name": "O'Connor",
        "date_of_birth": date(1992, 11, 2),
        "sex": "Male",
        "phone_number": "5558675309",
        "email": None,
        "address_line_1": "1600 Pennsylvania Avenue NW",
        "address_line_2": None,
        "city": "Washington",
        "state": "DC",
        "zip_code": "20500",
        "insurance_provider": None,
        "insurance_member_id": None,
        "preferred_language": "English",
        "emergency_contact_name": "Sarah O'Connor",
        "emergency_contact_phone": "5552223333",
    },
]


def seed_patients():
    """Insert seed patients only if the table is currently empty."""
    db = SessionLocal()
    try:
        count = db.query(Patient).count()
        if count > 0:
            logger.info("Database already has %d patient(s) — skipping seed.", count)
            return

        for record in SEED_PATIENTS:
            patient = Patient(**record)
            db.add(patient)

        db.commit()
        logger.info("Seeded %d demo patient(s).", len(SEED_PATIENTS))
    except Exception:
        db.rollback()
        logger.exception("Failed to seed patients")
    finally:
        db.close()
