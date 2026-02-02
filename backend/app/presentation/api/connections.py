"""Endpoints para gerenciar conexões e scans."""
import logging
import time

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from sqlalchemy.orm import Session

from app.infrastructure.db import SessionLocal, get_db
from app.domain.models import Connection, Scan
from app.domain.schemas import ConnectionCreate, ConnectionOut, ConnectionUpdate, ScanOut
from app.infrastructure.security import EncryptionError, decrypt_secret, encrypt_secret
from app.application.services.scan import ConnectionInfo, run_scan, test_connection as test_connection_service

router = APIRouter(prefix="/connections", tags=["connections"])
logger = logging.getLogger("atlasrag.connections")


@router.post("", response_model=ConnectionOut)
def create_connection(payload: ConnectionCreate, db: Session = Depends(get_db)):
    # Cria conexão com senha criptografada.
    logger.info(
        "connection_create_requested",
        extra={"name": payload.name, "host": payload.host, "database": payload.database},
    )
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
    logger.info("connection_created", extra={"connection_id": connection.id})
    return connection


@router.get("", response_model=list[ConnectionOut])
def list_connections(db: Session = Depends(get_db)):
    # Lista conexões disponíveis.
    logger.info("connection_list_requested")
    return db.query(Connection).order_by(Connection.id).all()


@router.put("/{connection_id}", response_model=ConnectionOut)
def update_connection(connection_id: int, payload: ConnectionUpdate, db: Session = Depends(get_db)):
    # Atualiza campos de conexão com tratamento de senha.
    logger.info("connection_update_requested", extra={"connection_id": connection_id})
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
    logger.info("connection_updated", extra={"connection_id": connection_id})
    return connection


@router.delete("/{connection_id}")
def delete_connection(connection_id: int, db: Session = Depends(get_db)):
    # Remove conexão e dados associados.
    logger.info("connection_delete_requested", extra={"connection_id": connection_id})
    connection = db.get(Connection, connection_id)
    if not connection:
        raise HTTPException(status_code=404, detail="Connection not found")
    db.delete(connection)
    db.commit()
    logger.info("connection_deleted", extra={"connection_id": connection_id})
    return {"status": "deleted"}


@router.post("/{connection_id}/test")
def test_connection_endpoint(connection_id: int, db: Session = Depends(get_db)):
    # Testa conectividade usando credenciais descriptografadas.
    logger.info("connection_test_requested", extra={"connection_id": connection_id})
    connection = db.get(Connection, connection_id)
    if not connection:
        raise HTTPException(status_code=404, detail="Connection not found")

    try:
        password = decrypt_secret(connection.password_encrypted)
    except (EncryptionError, UnicodeDecodeError, TypeError, ValueError) as exc:
        logger.warning("connection_decrypt_failed", extra={"connection_id": connection_id})
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    info = ConnectionInfo(
        host=connection.host,
        port=connection.port,
        database=connection.database,
        username=connection.username,
        password=password,
        ssl_mode=connection.ssl_mode or "prefer",
    )

    try:
        test_connection_service(info)
    except Exception as exc:
        logger.exception("connection_test_failed", extra={"connection_id": connection_id})
        raise HTTPException(status_code=400, detail=_classify_connection_error(exc)) from exc

    logger.info("connection_test_succeeded", extra={"connection_id": connection_id})
    return {"status": "ok"}


@router.post("/{connection_id}/scan", response_model=ScanOut)
def scan_connection(connection_id: int, background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    # Enfileira scan assíncrono da conexão.
    logger.info("scan_request_received", extra={"connection_id": connection_id})
    connection = db.get(Connection, connection_id)
    if not connection:
        raise HTTPException(status_code=404, detail="Connection not found")

    try:
        password = decrypt_secret(connection.password_encrypted)
    except (EncryptionError, UnicodeDecodeError, TypeError, ValueError) as exc:
        logger.warning("connection_decrypt_failed", extra={"connection_id": connection_id})
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
        ssl_mode=connection.ssl_mode or "prefer",
    )

    logger.info(
        "scan_enqueued",
        extra={
            "connection_id": connection_id,
            "scan_id": scan.id,
            "host": connection.host,
            "port": connection.port,
            "database": connection.database,
            "ssl_mode": connection.ssl_mode,
        },
    )

    background_tasks.add_task(_run_scan_background, info, scan.id)
    return scan


def _run_scan_background(info: ConnectionInfo, scan_id: int) -> None:
    """Executa scan em background com sessão dedicada."""
    session = SessionLocal()
    start = time.perf_counter()
    logger.info("scan_background_started", extra={"scan_id": scan_id})
    try:
        run_scan(session, info, scan_id=scan_id)
    except Exception:
        logger.exception("scan_background_failed", extra={"scan_id": scan_id})
        raise
    finally:
        duration_ms = (time.perf_counter() - start) * 1000
        logger.info("scan_background_finished", extra={"scan_id": scan_id, "duration_ms": round(duration_ms, 2)})
        session.close()


def _classify_connection_error(exc: Exception) -> str:
    """Categoriza erros comuns de conexão para resposta amigável."""
    message = str(exc).lower()
    if "timeout" in message:
        return "Connection failed: timeout"
    if "authentication" in message or "password" in message:
        return "Connection failed: authentication error"
    return "Connection failed"


@router.get("/{connection_id}/scans", response_model=list[ScanOut])
def list_scans(connection_id: int, db: Session = Depends(get_db)):
    # Retorna histórico de scans da conexão.
    logger.info("scan_list_requested", extra={"connection_id": connection_id})
    return db.query(Scan).filter(Scan.connection_id == connection_id).order_by(Scan.id.desc()).all()
