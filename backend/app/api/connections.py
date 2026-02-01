from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db import get_db, SessionLocal
from app.models import Connection, Scan
from app.schemas import ConnectionCreate, ConnectionUpdate, ConnectionOut, ScanOut
from app.security import encrypt_secret, decrypt_secret, EncryptionError
from app.services.scan import ConnectionInfo, run_scan, test_connection

router = APIRouter(prefix="/connections", tags=["connections"])


@router.post("", response_model=ConnectionOut)
def create_connection(payload: ConnectionCreate, db: Session = Depends(get_db)):
    try:
        encrypted = encrypt_secret(payload.password)
    except EncryptionError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    connection = Connection(
        name=payload.name,
        host=payload.host,
        port=payload.port,
        database=payload.database,
        username=payload.username,
        password_encrypted=encrypted,
        ssl_mode=payload.ssl_mode,
    )
    db.add(connection)
    db.commit()
    db.refresh(connection)
    return connection


@router.get("", response_model=list[ConnectionOut])
def list_connections(db: Session = Depends(get_db)):
    return db.query(Connection).order_by(Connection.id).all()


@router.put("/{connection_id}", response_model=ConnectionOut)
def update_connection(connection_id: int, payload: ConnectionUpdate, db: Session = Depends(get_db)):
    connection = db.get(Connection, connection_id)
    if not connection:
        raise HTTPException(status_code=404, detail="Connection not found")
    for field, value in payload.model_dump(exclude_unset=True).items():
        if field == "password":
            try:
                connection.password_encrypted = encrypt_secret(value)
            except EncryptionError as exc:
                raise HTTPException(status_code=400, detail=str(exc)) from exc
        else:
            setattr(connection, field, value)
    db.commit()
    db.refresh(connection)
    return connection


@router.delete("/{connection_id}")
def delete_connection(connection_id: int, db: Session = Depends(get_db)):
    connection = db.get(Connection, connection_id)
    if not connection:
        raise HTTPException(status_code=404, detail="Connection not found")
    db.delete(connection)
    db.commit()
    return {"status": "deleted"}


@router.post("/{connection_id}/test")
def test_connection(connection_id: int, db: Session = Depends(get_db)):
    connection = db.get(Connection, connection_id)
    if not connection:
        raise HTTPException(status_code=404, detail="Connection not found")
    try:
        password = decrypt_secret(connection.password_encrypted)
    except EncryptionError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    info = ConnectionInfo(
        host=connection.host,
        port=connection.port,
        database=connection.database,
        username=connection.username,
        password=password,
        ssl_mode=connection.ssl_mode,
    )
    try:
        test_connection(info)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=_classify_connection_error(exc)) from exc
    return {"status": "ok"}


@router.post("/{connection_id}/scan", response_model=ScanOut)
def scan_connection(connection_id: int, background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    connection = db.get(Connection, connection_id)
    if not connection:
        raise HTTPException(status_code=404, detail="Connection not found")
    try:
        password = decrypt_secret(connection.password_encrypted)
    except EncryptionError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    scan = Scan(connection_id=connection.id, status="running")
    db.add(scan)
    db.commit()
    db.refresh(scan)

    info = ConnectionInfo(
        host=connection.host,
        port=connection.port,
        database=connection.database,
        username=connection.username,
        password=password,
        ssl_mode=connection.ssl_mode,
    )
    background_tasks.add_task(_run_scan_background, info, scan.id)
    return scan


def _run_scan_background(info: ConnectionInfo, scan_id: int) -> None:
    session = SessionLocal()
    try:
        run_scan(session, info, scan_id=scan_id)
    finally:
        session.close()


def _classify_connection_error(exc: Exception) -> str:
    message = str(exc).lower()
    if "timeout" in message:
        return "Connection failed: timeout"
    if "authentication" in message or "password" in message:
        return "Connection failed: authentication error"
    return "Connection failed"


@router.get("/{connection_id}/scans", response_model=list[ScanOut])
def list_scans(connection_id: int, db: Session = Depends(get_db)):
    return db.query(Scan).filter(Scan.connection_id == connection_id).order_by(Scan.id.desc()).all()
