"""
AEGIS UNIFIED DATA CORE - Emergency Services Directory
/api/v1/emergency-services
Canonical repository and directory for Indian Emergency Service helplines,
first responders, NDRF, SDMA, Police, Fire, Ambulance, Women and Child safety numbers.
"""
from typing import Optional, List, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, or_, and_, desc
from backend.app.database.session import get_db
from backend.app.database.models import EmergencyServiceEntity, User, utc_now
from backend.app.schemas.common import ApiResponse, FreshnessMetadata, ProvenanceMetadata
from backend.app.api.deps import rate_limit_check, get_current_user

router = APIRouter(prefix="/emergency-services", tags=["Emergency Services Directory"])


CANONICAL_NATIONAL_SERVICES: List[Dict[str, Any]] = [
    {
        "id": "srv-nat-112",
        "service_code": "IN_112_ERSS",
        "name": "National Emergency Response Support System (ERSS)",
        "category": "DISASTER_RESPONSE",
        "phone_numbers": ["112"],
        "primary_phone": "112",
        "alternate_phone": "112",
        "state": "All India",
        "district": "All Districts",
        "action_types": ["CALL", "SMS", "NAVIGATE", "CONTACT"],
        "description": "Unified single all-India 24x7 emergency response number for Police, Fire, Health and Disaster assistance.",
        "is_automated_dispatch_integrated": True,
        "dispatch_endpoint": "https://erss.gov.in/api/v1/dispatch",
        "display_priority": 1
    },
    {
        "id": "srv-nat-100",
        "service_code": "IN_100_POLICE",
        "name": "Police Control Room and Rapid Action",
        "category": "POLICE",
        "phone_numbers": ["100", "112"],
        "primary_phone": "100",
        "alternate_phone": "112",
        "state": "All India",
        "district": "All Districts",
        "action_types": ["CALL", "SMS"],
        "description": "Direct emergency dispatch for law enforcement, crime prevention, and citizen immediate protection.",
        "is_automated_dispatch_integrated": True,
        "dispatch_endpoint": "",
        "display_priority": 2
    },
    {
        "id": "srv-nat-108",
        "service_code": "IN_108_AMBULANCE",
        "name": "Emergency Medical and Trauma Ambulance (EMRI)",
        "category": "AMBULANCE",
        "phone_numbers": ["108", "102"],
        "primary_phone": "108",
        "alternate_phone": "102",
        "state": "All India",
        "district": "All Districts",
        "action_types": ["CALL", "NAVIGATE"],
        "description": "24x7 emergency medical transport, cardiac resuscitation, and trauma response across India.",
        "is_automated_dispatch_integrated": True,
        "dispatch_endpoint": "",
        "display_priority": 3
    },
    {
        "id": "srv-nat-101",
        "service_code": "IN_101_FIRE",
        "name": "Fire and Hazmat Rescue Control",
        "category": "FIRE",
        "phone_numbers": ["101", "112"],
        "primary_phone": "101",
        "alternate_phone": "112",
        "state": "All India",
        "district": "All Districts",
        "action_types": ["CALL"],
        "description": "Rapid response for building fires, industrial chemical leaks, and entrapment rescues.",
        "is_automated_dispatch_integrated": True,
        "dispatch_endpoint": "",
        "display_priority": 4
    },
    {
        "id": "srv-nat-1078",
        "service_code": "IN_1078_NDRF",
        "name": "National Disaster Response Force (NDRF) HQ",
        "category": "DISASTER_RESPONSE",
        "phone_numbers": ["1078", "011-24363260", "+91-9711077372"],
        "primary_phone": "1078",
        "alternate_phone": "011-24363260",
        "state": "All India",
        "district": "All Districts",
        "action_types": ["CALL", "CONTACT"],
        "description": "India's specialized force for responding to catastrophic natural disasters, floods, cyclones, landslides, and earthquakes.",
        "is_automated_dispatch_integrated": True,
        "dispatch_endpoint": "https://ndrf.gov.in/control-room/api",
        "display_priority": 5
    },
    {
        "id": "srv-nat-1070",
        "service_code": "IN_1070_SDMA",
        "name": "State Disaster Management Authority (SDMA) Control",
        "category": "STATE_DISASTER_MANAGEMENT",
        "phone_numbers": ["1070"],
        "primary_phone": "1070",
        "alternate_phone": "",
        "state": "All India",
        "district": "All Districts",
        "action_types": ["CALL"],
        "description": "State-level disaster coordination, evacuation relief shelters, and emergency resource mobilization.",
        "is_automated_dispatch_integrated": False,
        "dispatch_endpoint": "",
        "display_priority": 6
    },
    {
        "id": "srv-nat-1077",
        "service_code": "IN_1077_DEOC",
        "name": "District Emergency Operation Centre (DEOC)",
        "category": "DISASTER_RESPONSE",
        "phone_numbers": ["1077"],
        "primary_phone": "1077",
        "alternate_phone": "",
        "state": "All India",
        "district": "All Districts",
        "action_types": ["CALL"],
        "description": "District Collectorate emergency operation command for local disaster relief and flood/cyclone alerts.",
        "is_automated_dispatch_integrated": False,
        "dispatch_endpoint": "",
        "display_priority": 7
    },
    {
        "id": "srv-nat-1091",
        "service_code": "IN_1091_WOMEN",
        "name": "Women in Distress National Helpline",
        "category": "WOMEN_SAFETY",
        "phone_numbers": ["1091", "181"],
        "primary_phone": "1091",
        "alternate_phone": "181",
        "state": "All India",
        "district": "All Districts",
        "action_types": ["CALL", "SMS"],
        "description": "Confidential emergency assistance, psychological counseling, and police intervention for women.",
        "is_automated_dispatch_integrated": True,
        "dispatch_endpoint": "",
        "display_priority": 8
    },
    {
        "id": "srv-nat-1098",
        "service_code": "IN_1098_CHILD",
        "name": "Childline India Emergency Care",
        "category": "CHILD_SAFETY",
        "phone_numbers": ["1098"],
        "primary_phone": "1098",
        "alternate_phone": "",
        "state": "All India",
        "district": "All Districts",
        "action_types": ["CALL"],
        "description": "24-hour nationwide emergency phone outreach service for children in need of care and protection.",
        "is_automated_dispatch_integrated": True,
        "dispatch_endpoint": "",
        "display_priority": 9
    },
    {
        "id": "srv-nat-1930",
        "service_code": "IN_1930_CYBER",
        "name": "National Cyber Crime Reporting Helpline",
        "category": "CYBER_CRIME",
        "phone_numbers": ["1930"],
        "primary_phone": "1930",
        "alternate_phone": "",
        "state": "All India",
        "district": "All Districts",
        "action_types": ["CALL"],
        "description": "Instant financial fraud freeze and cyber incident emergency hotline managed by I4C (MHA).",
        "is_automated_dispatch_integrated": False,
        "dispatch_endpoint": "",
        "display_priority": 10
    },
    {
        "id": "srv-nat-1073",
        "service_code": "IN_1073_ROAD",
        "name": "National Highway Emergency and Accident Assistance (NHAI)",
        "category": "DISASTER_RESPONSE",
        "phone_numbers": ["1033", "1073"],
        "primary_phone": "1033",
        "alternate_phone": "1073",
        "state": "All India",
        "district": "All Districts",
        "action_types": ["CALL"],
        "description": "Round-the-clock emergency road patrol, ambulance dispatch, and crane/towing support on Indian National Highways.",
        "is_automated_dispatch_integrated": False,
        "dispatch_endpoint": "",
        "display_priority": 11
    }
]

class EmergencyServiceResponseSchema(BaseModel):
    id: str
    service_code: str
    name: str
    category: str
    phone_numbers: List[str]
    primary_phone: str
    alternate_phone: Optional[str] = ""
    state: str
    district: str
    action_types: List[str] = ["CALL", "SMS", "NAVIGATE", "CONTACT"]
    description: str
    is_automated_dispatch_integrated: bool = False
    dispatch_endpoint: Optional[str] = ""
    display_priority: int = 10
    created_at: Optional[str] = None

class EmergencyServiceCreateRequest(BaseModel):
    service_code: str = Field(..., min_length=3, max_length=50)
    name: str = Field(..., min_length=2, max_length=255)
    category: str = Field(..., description="POLICE, AMBULANCE, FIRE, DISASTER_RESPONSE, WOMEN_SAFETY, CHILD_SAFETY, CYBER_CRIME, STATE_DISASTER_MANAGEMENT, NATIONAL_HELPLINE")
    phone_numbers: List[str] = Field(..., min_length=1)
    alternate_phone: Optional[str] = Field(default="")

    state: Optional[str] = Field(default="All India")
    district: Optional[str] = Field(default="All Districts")
    action_types: Optional[List[str]] = Field(default=["CALL", "SMS", "CONTACT"])
    description: Optional[str] = Field(default="")
    is_automated_dispatch_integrated: Optional[bool] = Field(default=False)
    dispatch_endpoint: Optional[str] = Field(default="")
    display_priority: Optional[int] = Field(default=10)

@router.get("", response_model=ApiResponse[List[EmergencyServiceResponseSchema]])
async def list_emergency_services(
    state: Optional[str] = Query(default=None, description="Filter by Indian State"),
    district: Optional[str] = Query(default=None, description="Filter by District"),
    category: Optional[str] = Query(default=None, description="POLICE, AMBULANCE, FIRE, DISASTER_RESPONSE, WOMEN_SAFETY, CHILD_SAFETY, CYBER_CRIME, STATE_DISASTER_MANAGEMENT"),
    search: Optional[str] = Query(default=None, description="Search query for name, description or phone"),
    db: AsyncSession = Depends(get_db)
):
    """
    EMERGENCY SERVICES DIRECTORY:
    Retrieves official emergency service contacts, toll-free hotlines, and first-responder dispatch endpoints.
    Combines canonical All-India national helplines with database-registered state and district specific services.
    """
    results: List[EmergencyServiceResponseSchema] = []

    db_query = select(EmergencyServiceEntity).where(EmergencyServiceEntity.is_active == True)
    if state and state.lower() != "all india":
        db_query = db_query.where(
            or_(
                EmergencyServiceEntity.state.ilike(f"%{state}%"),
                EmergencyServiceEntity.state == "All India"
            )
        )
    if district and district.lower() != "all districts":
        db_query = db_query.where(
            or_(
                EmergencyServiceEntity.district.ilike(f"%{district}%"),
                EmergencyServiceEntity.district == "All Districts"
            )
        )
    if category:
        db_query = db_query.where(EmergencyServiceEntity.category == category.upper())

    db_res = await db.execute(db_query)
    db_services = db_res.scalars().all()
    seen_codes = set()

    for s in db_services:
        seen_codes.add(s.service_code)
        primary = s.phone_numbers[0] if s.phone_numbers else "112"
        results.append(EmergencyServiceResponseSchema(
            id=s.id,
            service_code=s.service_code,
            name=s.name,
            category=s.category,
            phone_numbers=s.phone_numbers,
            primary_phone=primary,
            alternate_phone=s.alternate_phone,
            state=s.state or "All India",
            district=s.district or "All Districts",
            action_types=s.action_types or ["CALL", "SMS"],
            description=s.description or "",
            is_automated_dispatch_integrated=s.is_automated_dispatch_integrated,
            dispatch_endpoint=s.dispatch_endpoint,
            display_priority=s.display_priority,
            created_at=s.created_at.isoformat() if s.created_at else None
        ))

    for c in CANONICAL_NATIONAL_SERVICES:
        if c["service_code"] in seen_codes:
            continue

        if category and c["category"].upper() != category.upper():
            continue

        results.append(EmergencyServiceResponseSchema(
            id=c["id"],
            service_code=c["service_code"],
            name=c["name"],
            category=c["category"],
            phone_numbers=c["phone_numbers"],
            primary_phone=c["primary_phone"],
            alternate_phone=c["alternate_phone"],
            state=c["state"],
            district=c["district"],
            action_types=c["action_types"],
            description=c["description"],
            is_automated_dispatch_integrated=c["is_automated_dispatch_integrated"],
            dispatch_endpoint=c["dispatch_endpoint"],
            display_priority=c["display_priority"],
            created_at=utc_now().isoformat()
        ))

    if search:
        s_lower = search.lower()
        results = [
            r for r in results
            if s_lower in r.name.lower()
            or s_lower in r.description.lower()
            or any(s_lower in p for p in r.phone_numbers)
            or s_lower in r.category.lower()
        ]

    results.sort(key=lambda x: x.display_priority)

    return ApiResponse(
        success=True,
        data=results,
        freshness=FreshnessMetadata(status="fresh", age_seconds=0),
        provenance=ProvenanceMetadata(
            data_type="official_observation",
            source_authority="AEGIS National Emergency Services Registry",
            processing_version="1.0.0"
        )
    )

@router.get("/national", response_model=ApiResponse[List[EmergencyServiceResponseSchema]])
async def get_national_hotlines():
    """
    CANONICAL ALL-INDIA HOTLINES:
    Returns the core top-priority 24x7 emergency helplines for India.
    """
    items = [
        EmergencyServiceResponseSchema(
            id=c["id"],
            service_code=c["service_code"],
            name=c["name"],
            category=c["category"],
            phone_numbers=c["phone_numbers"],
            primary_phone=c["primary_phone"],
            alternate_phone=c["alternate_phone"],
            state=c["state"],
            district=c["district"],
            action_types=c["action_types"],
            description=c["description"],
            is_automated_dispatch_integrated=c["is_automated_dispatch_integrated"],
            dispatch_endpoint=c["dispatch_endpoint"],
            display_priority=c["display_priority"],
            created_at=utc_now().isoformat()
        )
        for c in CANONICAL_NATIONAL_SERVICES
    ]
    return ApiResponse(
        success=True,
        data=items,
        freshness=FreshnessMetadata(status="fresh", age_seconds=0),
        provenance=ProvenanceMetadata(
            data_type="official_observation",
            source_authority="Ministry of Home Affairs and National Emergency Support Systems",
            processing_version="1.0.0"
        )
    )

@router.get("/categories", response_model=ApiResponse[List[Dict[str, str]]])
async def list_service_categories():
    """
    Lists all supported emergency service categories.
    """
    categories = [
        {"code": "DISASTER_RESPONSE", "name": "Disaster Response (NDRF / ERSS / DEOC)"},
        {"code": "POLICE", "name": "Police and Law Enforcement (100 / 112)"},
        {"code": "AMBULANCE", "name": "Ambulance and Trauma Medical (108 / 102)"},
        {"code": "FIRE", "name": "Fire and Rescue Services (101)"},
        {"code": "STATE_DISASTER_MANAGEMENT", "name": "State Disaster Management Authority (1070)"},
        {"code": "WOMEN_SAFETY", "name": "Women in Distress (1091 / 181)"},
        {"code": "CHILD_SAFETY", "name": "Childline Emergency (1098)"},
        {"code": "CYBER_CRIME", "name": "Cyber Crime Hotline (1930)"},
        {"code": "NATIONAL_HELPLINE", "name": "National All-India Helplines"}
    ]
    return ApiResponse(success=True, data=categories, freshness=FreshnessMetadata(status="fresh", age_seconds=0))

@router.post("", response_model=ApiResponse[EmergencyServiceResponseSchema], dependencies=[Depends(rate_limit_check)])
async def register_emergency_service(
    payload: EmergencyServiceCreateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_user)
):
    """
    ADMIN/OFFICIAL: Registers or updates an official emergency service or helpline.
    """
    if not current_user or current_user.role not in ("admin", "official", "sdrf_officer"):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Administrator or Emergency Official credentials required.")

    res = await db.execute(select(EmergencyServiceEntity).where(EmergencyServiceEntity.service_code == payload.service_code))
    entity = res.scalars().first()
    now = utc_now()

    if not entity:
        entity = EmergencyServiceEntity(
            service_code=payload.service_code,
            name=payload.name,
            category=payload.category.upper(),
            phone_numbers=payload.phone_numbers,
            alternate_phone=payload.alternate_phone or "",
            state=payload.state or "All India",
            district=payload.district or "All Districts",
            action_types=payload.action_types or ["CALL", "SMS"],
            description=payload.description or "",
            is_automated_dispatch_integrated=payload.is_automated_dispatch_integrated or False,
            dispatch_endpoint=payload.dispatch_endpoint or "",
            display_priority=payload.display_priority or 10,
            is_active=True,
            created_at=now
        )
        db.add(entity)
    else:
        entity.name = payload.name
        entity.category = payload.category.upper()
        entity.phone_numbers = payload.phone_numbers
        entity.alternate_phone = payload.alternate_phone or ""
        entity.state = payload.state or "All India"
        entity.district = payload.district or "All Districts"
        entity.action_types = payload.action_types or ["CALL", "SMS"]
        entity.description = payload.description or ""
        entity.is_automated_dispatch_integrated = payload.is_automated_dispatch_integrated or False
        entity.dispatch_endpoint = payload.dispatch_endpoint or ""
        entity.display_priority = payload.display_priority or 10

    await db.commit()
    await db.refresh(entity)

    return ApiResponse(
        success=True,
        data=EmergencyServiceResponseSchema(
            id=entity.id,
            service_code=entity.service_code,
            name=entity.name,
            category=entity.category,
            phone_numbers=entity.phone_numbers,
            primary_phone=entity.phone_numbers[0] if entity.phone_numbers else "112",
            alternate_phone=entity.alternate_phone,
            state=entity.state,
            district=entity.district,
            action_types=entity.action_types,
            description=entity.description,
            is_automated_dispatch_integrated=entity.is_automated_dispatch_integrated,
            dispatch_endpoint=entity.dispatch_endpoint,
            display_priority=entity.display_priority,
            created_at=entity.created_at.isoformat() if entity.created_at else None
        ),
        freshness=FreshnessMetadata(status="fresh", age_seconds=0)
    )
