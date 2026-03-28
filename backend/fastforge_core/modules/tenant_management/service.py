"""
FastForge Tenant Management Service & Router
==================================================
Provides tenant CRUD + feature management.

Mount in your app:
    from fastforge_core.modules.tenant_management import create_tenant_router
    app.include_router(create_tenant_router(get_db), prefix="/api/v1/tenants")
"""
from __future__ import annotations
from typing import Optional
from fastapi import APIRouter, Depends, Query, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import or_

from fastforge_core.middleware.exceptions import BusinessException
from .models import Tenant, TenantFeature
from .schemas import (
    TenantCreate, TenantUpdate, TenantResponse,
    TenantListResponse, TenantFeatureUpdate,
)


class TenantService:
    def __init__(self, db: Session):
        self.db = db

    def get(self, id: int) -> TenantResponse:
        t = self.db.query(Tenant).filter(Tenant.id == id).first()
        if not t:
            raise HTTPException(status_code=404, detail="Tenant not found")
        return TenantResponse.model_validate(t)

    def get_by_name(self, name: str) -> Optional[TenantResponse]:
        t = self.db.query(Tenant).filter(Tenant.name == name).first()
        return TenantResponse.model_validate(t) if t else None

    def get_list(self, page=1, page_size=20, search=None) -> TenantListResponse:
        query = self.db.query(Tenant)
        if search:
            query = query.filter(or_(
                Tenant.name.ilike(f"%{search}%"),
                Tenant.display_name.ilike(f"%{search}%"),
            ))
        total = query.count()
        items = query.order_by(Tenant.id.desc()).offset((page - 1) * page_size).limit(page_size).all()
        return TenantListResponse(
            items=[TenantResponse.model_validate(t) for t in items],
            total=total, page=page, page_size=page_size,
        )

    def create(self, data: TenantCreate) -> TenantResponse:
        if self.db.query(Tenant).filter(Tenant.name == data.name).first():
            raise BusinessException(f"Tenant '{data.name}' already exists", code="DuplicateTenant")
        tenant = Tenant(**data.model_dump())
        self.db.add(tenant)
        self.db.commit()
        self.db.refresh(tenant)
        return TenantResponse.model_validate(tenant)

    def update(self, id: int, data: TenantUpdate) -> TenantResponse:
        tenant = self.db.query(Tenant).filter(Tenant.id == id).first()
        if not tenant:
            raise HTTPException(status_code=404, detail="Tenant not found")
        for field, value in data.model_dump(exclude_unset=True).items():
            setattr(tenant, field, value)
        self.db.commit()
        self.db.refresh(tenant)
        return TenantResponse.model_validate(tenant)

    def delete(self, id: int) -> dict:
        tenant = self.db.query(Tenant).filter(Tenant.id == id).first()
        if not tenant:
            raise HTTPException(status_code=404, detail="Tenant not found")
        self.db.delete(tenant)
        self.db.commit()
        return {"message": f"Tenant '{tenant.name}' deleted"}

    def get_features(self, tenant_id: int) -> dict[str, str]:
        rows = self.db.query(TenantFeature).filter(TenantFeature.tenant_id == tenant_id).all()
        return {r.feature_name: r.value for r in rows}

    def set_features(self, tenant_id: int, features: dict[str, str]) -> dict[str, str]:
        # Verify tenant exists
        if not self.db.query(Tenant).filter(Tenant.id == tenant_id).first():
            raise HTTPException(status_code=404, detail="Tenant not found")

        for name, value in features.items():
            existing = self.db.query(TenantFeature).filter(
                TenantFeature.tenant_id == tenant_id,
                TenantFeature.feature_name == name,
            ).first()
            if existing:
                existing.value = value
            else:
                self.db.add(TenantFeature(tenant_id=tenant_id, feature_name=name, value=value))
        self.db.commit()
        return self.get_features(tenant_id)


def create_tenant_router(get_db) -> APIRouter:
    """Factory to create the tenant management router."""
    router = APIRouter(tags=["Tenant Management"])

    def _svc(db: Session = Depends(get_db)) -> TenantService:
        return TenantService(db)

    @router.get("/", response_model=TenantListResponse)
    def list_tenants(page: int = Query(1), page_size: int = Query(20), search: Optional[str] = None, svc: TenantService = Depends(_svc)):
        return svc.get_list(page, page_size, search)

    @router.get("/{id}", response_model=TenantResponse)
    def get_tenant(id: int, svc: TenantService = Depends(_svc)):
        return svc.get(id)

    @router.post("/", response_model=TenantResponse, status_code=201)
    def create_tenant(data: TenantCreate, svc: TenantService = Depends(_svc)):
        return svc.create(data)

    @router.put("/{id}", response_model=TenantResponse)
    def update_tenant(id: int, data: TenantUpdate, svc: TenantService = Depends(_svc)):
        return svc.update(id, data)

    @router.delete("/{id}")
    def delete_tenant(id: int, svc: TenantService = Depends(_svc)):
        return svc.delete(id)

    @router.get("/{tenant_id}/features")
    def get_features(tenant_id: int, svc: TenantService = Depends(_svc)):
        return svc.get_features(tenant_id)

    @router.put("/{tenant_id}/features")
    def set_features(tenant_id: int, data: TenantFeatureUpdate, svc: TenantService = Depends(_svc)):
        return svc.set_features(tenant_id, data.features)

    return router
