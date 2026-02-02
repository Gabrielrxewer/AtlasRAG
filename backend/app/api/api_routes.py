import logging

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import ApiRoute, ApiRouteField
from app.schemas import ApiRouteCreate, ApiRouteOut, ApiRouteAnnotationUpdate

router = APIRouter(prefix="/api-routes", tags=["api-routes"])
logger = logging.getLogger("atlasrag.api_routes")


@router.post("", response_model=ApiRouteOut)
def create_route(payload: ApiRouteCreate, db: Session = Depends(get_db)):
    logger.info("api_route_create_requested", extra={"path": payload.path, "method": payload.method})
    route = ApiRoute(**payload.model_dump())
    db.add(route)
    db.commit()
    db.refresh(route)
    logger.info("api_route_created", extra={"route_id": route.id})
    return route


@router.get("", response_model=list[ApiRouteOut])
def list_routes(db: Session = Depends(get_db)):
    logger.info("api_route_list_requested")
    routes = db.query(ApiRoute).order_by(ApiRoute.id).all()
    logger.info("api_route_list_loaded", extra={"route_count": len(routes)})
    return routes


@router.get("/{route_id}", response_model=ApiRouteOut)
def get_route(route_id: int, db: Session = Depends(get_db)):
    logger.info("api_route_get_requested", extra={"route_id": route_id})
    route = db.get(ApiRoute, route_id)
    if not route:
        raise HTTPException(status_code=404, detail="Route not found")
    return route


@router.put("/{route_id}", response_model=ApiRouteOut)
def update_route(route_id: int, payload: ApiRouteCreate, db: Session = Depends(get_db)):
    logger.info("api_route_update_requested", extra={"route_id": route_id})
    route = db.get(ApiRoute, route_id)
    if not route:
        raise HTTPException(status_code=404, detail="Route not found")
    for key, value in payload.model_dump().items():
        setattr(route, key, value)
    db.commit()
    db.refresh(route)
    logger.info("api_route_updated", extra={"route_id": route_id})
    return route


@router.delete("/{route_id}")
def delete_route(route_id: int, db: Session = Depends(get_db)):
    logger.info("api_route_delete_requested", extra={"route_id": route_id})
    route = db.get(ApiRoute, route_id)
    if not route:
        raise HTTPException(status_code=404, detail="Route not found")
    db.delete(route)
    db.commit()
    logger.info("api_route_deleted", extra={"route_id": route_id})
    return {"status": "deleted"}


@router.put("/{route_id}/annotations")
def update_route_annotations(route_id: int, payload: ApiRouteAnnotationUpdate, db: Session = Depends(get_db)):
    logger.info("api_route_annotations_update_requested", extra={"route_id": route_id})
    route = db.get(ApiRoute, route_id)
    if not route:
        raise HTTPException(status_code=404, detail="Route not found")
    if payload.description is not None:
        route.description = payload.description
    if payload.tags is not None:
        route.tags = payload.tags
    if payload.updated_by is not None:
        route.updated_by = payload.updated_by
    if payload.fields is not None:
        db.query(ApiRouteField).filter(ApiRouteField.route_id == route_id).delete()
        for field in payload.fields:
            db.add(ApiRouteField(route_id=route_id, **field.model_dump()))
    db.commit()
    db.refresh(route)
    logger.info("api_route_annotations_updated", extra={"route_id": route_id})
    return {"status": "updated"}
