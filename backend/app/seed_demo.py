from sqlalchemy.orm import Session

from app.db import SessionLocal
from app.models import ApiRoute, ApiRouteField


def seed_demo(db: Session) -> None:
    if db.query(ApiRoute).first():
        return
    route = ApiRoute(
        name="Create Order",
        base_url="https://api.demo.local",
        path="/v1/orders",
        method="POST",
        headers_template={"Authorization": "Bearer <token>"},
        auth_type="bearer",
        body_template={"customer_id": "uuid", "items": [{"sku": "string", "qty": 1}]},
        description="Cria um pedido de venda.",
        tags=["orders", "sales"],
    )
    db.add(route)
    db.flush()
    db.add(
        ApiRouteField(
            route_id=route.id,
            location="body",
            name="customer_id",
            data_type="uuid",
            description="Identificador do cliente.",
            annotations={"semantic_type": "IDENTIFIER"},
        )
    )
    db.commit()


if __name__ == "__main__":
    session = SessionLocal()
    try:
        seed_demo(session)
    finally:
        session.close()
