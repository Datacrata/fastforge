"""Tenant Management Schemas."""
from pydantic import BaseModel, ConfigDict
from typing import Optional, List
from datetime import datetime


class TenantCreate(BaseModel):
    name: str
    display_name: Optional[str] = None
    admin_email: Optional[str] = None
    edition: Optional[str] = None


class TenantUpdate(BaseModel):
    display_name: Optional[str] = None
    is_active: Optional[bool] = None
    edition: Optional[str] = None
    admin_email: Optional[str] = None


class TenantResponse(BaseModel):
    id: int
    name: str
    display_name: Optional[str]
    is_active: bool
    edition: Optional[str]
    admin_email: Optional[str]
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)


class TenantListResponse(BaseModel):
    items: List[TenantResponse]
    total: int
    page: int
    page_size: int


class TenantFeatureUpdate(BaseModel):
    features: dict[str, str]  # {"MaxUsers": "50", "EnableExport": "true"}
