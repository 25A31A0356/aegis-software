"""
AEGIS UNIFIED DATA CORE - Data Source & Field Mapping Schemas
"""
from typing import Optional, List, Dict, Any
from datetime import datetime
from pydantic import BaseModel, Field


class FieldMappingCreate(BaseModel):
    external_field_path: str = Field(..., examples=["main.temp"])
    aegis_field_name: str = Field(..., examples=["temperature"])
    source_unit: Optional[str] = Field(default="standard", examples=["°C"])
    target_unit: Optional[str] = Field(default="°C", examples=["°C"])
    transformation_rule: str = Field(default="direct", examples=["direct"])
    confidence: str = Field(default="HIGH", examples=["HIGH"])
    is_active: bool = True


class FieldMappingRead(FieldMappingCreate):
    id: str
    data_source_id: str


class DataSourceCreate(BaseModel):
    name: str = Field(..., min_length=2, max_length=255, examples=["IMD National Weather Telemetry"])
    provider_code: str = Field(default="custom_http", examples=["imd"])
    category: str = Field(default="WEATHER", examples=["WEATHER"])
    base_url: str = Field(..., examples=["https://api.open-meteo.com/v1"])
    endpoint: str = Field(default="/forecast", examples=["/forecast"])
    http_method: str = Field(default="GET", examples=["GET"])
    auth_type: str = Field(default="NONE", examples=["NONE"])  # NONE, API_KEY_QUERY, API_KEY_HEADER, BEARER_TOKEN, BASIC_AUTH
    api_key_or_token: Optional[str] = Field(default=None, description="Plaintext secret supplied by admin during create/update; encrypted at rest")
    auth_header_name: Optional[str] = Field(default="Authorization")
    auth_query_param: Optional[str] = Field(default="api_key")
    request_params: Dict[str, Any] = Field(default_factory=dict)
    request_headers: Dict[str, Any] = Field(default_factory=dict)
    response_format: str = Field(default="JSON", examples=["JSON"])
    update_frequency_minutes: int = Field(default=5, ge=1, le=1440)
    cache_duration_seconds: int = Field(default=300, ge=10, le=86400)
    timeout_seconds: float = Field(default=15.0, ge=1.0, le=60.0)
    max_retries: int = Field(default=3, ge=0, le=5)
    is_enabled: bool = True
    field_mappings: Optional[List[FieldMappingCreate]] = None


class DataSourceUpdate(BaseModel):
    name: Optional[str] = None
    provider_code: Optional[str] = None
    category: Optional[str] = None
    base_url: Optional[str] = None
    endpoint: Optional[str] = None
    http_method: Optional[str] = None
    auth_type: Optional[str] = None
    api_key_or_token: Optional[str] = None
    auth_header_name: Optional[str] = None
    auth_query_param: Optional[str] = None
    request_params: Optional[Dict[str, Any]] = None
    request_headers: Optional[Dict[str, Any]] = None
    response_format: Optional[str] = None
    update_frequency_minutes: Optional[int] = None
    cache_duration_seconds: Optional[int] = None
    timeout_seconds: Optional[float] = None
    max_retries: Optional[int] = None
    is_enabled: Optional[bool] = None


class DataSourceRead(BaseModel):
    id: str
    name: str
    provider_code: str
    category: str
    base_url: str
    endpoint: str
    http_method: str
    auth_type: str
    masked_api_key: Optional[str] = None  # Never exposes full secret (e.g. '****************AB92')
    auth_header_name: Optional[str] = None
    auth_query_param: Optional[str] = None
    request_params: Dict[str, Any]
    request_headers: Dict[str, Any]
    response_format: str
    update_frequency_minutes: int
    cache_duration_seconds: int
    timeout_seconds: float
    max_retries: int
    is_enabled: bool
    health_status: str
    consecutive_failures: int
    last_success_at: Optional[datetime] = None
    last_failure_at: Optional[datetime] = None
    last_response_time_ms: float
    last_http_status: Optional[int] = None
    last_error_message: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    field_mappings: List[FieldMappingRead] = []


class DetectedField(BaseModel):
    external_path: str
    sample_value: Any
    detected_aegis_field: str
    confidence: str  # HIGH, MEDIUM, LOW
    suggested_unit: str
    suggested_rule: str


class ApiTestRequest(BaseModel):
    base_url: str
    endpoint: str = ""
    http_method: str = "GET"
    auth_type: str = "NONE"
    api_key_or_token: Optional[str] = None
    auth_header_name: Optional[str] = "Authorization"
    auth_query_param: Optional[str] = "api_key"
    request_params: Dict[str, Any] = Field(default_factory=dict)
    request_headers: Dict[str, Any] = Field(default_factory=dict)
    response_format: str = "JSON"
    timeout_seconds: float = 10.0


class ApiTestResponse(BaseModel):
    connection_status: str  # SUCCESS, FAILED
    http_status: Optional[int] = None
    response_time_ms: float = 0.0
    response_format: str = "JSON"
    raw_response_snippet: Any = None
    detected_fields: List[DetectedField] = []
    validation_status: str = "VALID"
    normalized_preview: Optional[Dict[str, Any]] = None
    error_message: Optional[str] = None
