from datetime import datetime
from typing import Literal

from fastapi import FastAPI, Depends, HTTPException, Header, Query
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import create_engine, ForeignKey, String, Float, DateTime, func, select
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship, sessionmaker, Session

# Database Setup (SQLite file for practice. PostgreSQL only changes the URL)

DATABASE_URL = "sqlite:///./sales.db"
engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(bind=engine)


class Base(DeclarativeBase):
    pass


# DATABASE tables
class Store(Base):
    __tablename__ = "stores"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100))
    region: Mapped[str] = mapped_column(String(50))
    representatives: Mapped[list["Representative"]] = relationship("Representative", back_populates="store")


class Representative(Base):
    __tablename__ = "representatives"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100))
    store_id: Mapped[int] = mapped_column(ForeignKey("stores.id"))
    store: Mapped["Store"] = relationship("Store", back_populates="representatives")
    sales: Mapped[list["Sale"]] = relationship("Sale", back_populates="representative")


class Sale(Base):
    __tablename__ = "sales"
    id: Mapped[int] = mapped_column(primary_key=True)
    representative_id: Mapped[int] = mapped_column(ForeignKey("representatives.id"))
    product_type: Mapped[str] = mapped_column(String(20))
    amount: Mapped[float] = mapped_column(Float)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
    representative: Mapped["Representative"] = relationship("Representative", back_populates="sales")


Base.metadata.create_all(engine)

# Commission rate for each product type sold
COMMISSION_RATES = {"cell_phone": 0.20, "service_plan": 0.10, "phone_accessory": 0.05}


# PYDANTIC MODELS
class SaleCreate(BaseModel):
    representative_id: int
    product_type: Literal["cell_phone", "service_plan", "phone_accessory"]
    amount: float = Field(gt=0, description="Sale amount must be more than zero")


class SaleOutput(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    representative_id: int
    product_type: str
    amount: float
    created_at: datetime


class CommissionOutput(BaseModel):
    representative_id: int
    total_sales: float
    commission: float

class MonthlySalesOutput(BaseModel):
    month: str
    total_sales: float
    num_sales: int


# Dependencies
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


FAKE_USER = {
    "admin-token": {"name": "Corporate Admin", "role": "admin", "store_id": None},
    "mgr-1624-token": {"name": "Store 1624 Manager", "role": "manager", "store_id": 1624},
    "mgr-2000-token": {"name": "Store 2000 Manager", "role": "manager", "store_id": 2000},
}


def get_current_user(token: str | None = Header(default=None)):
    user = FAKE_USER.get(token)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid authentication credentials")
    return user


def check_store_access(user: dict, store_id: int):
    if user["role"] == "admin":
        return True
    if user["role"] == "manager" and user["store_id"] == store_id:
        return True
    raise HTTPException(status_code=403, detail="Access denied")


# API + Data
app = FastAPI(title="Store Sales API v2.0")


def seed_data():
    db = SessionLocal()
    if db.scalar(select(func.count(Store.id))) == 0:
        db.add_all([
            Store(name="At&t- Troy", id=1624, region="Michigan"),
            Store(name="Verizon- Detroit", id=2000, region="Michigan"),
            Representative(name="Mira", id=1, store_id=1624),
            Representative(name="Jowana", id=2, store_id=2000),
            Representative(name="Zayna", id=3, store_id=1624),
        ])
        db.commit()
    db.close()


seed_data()


# Endpoints
@app.get("/")
def root():
    return {"message": "Welcome to the Store Sales API"}


@app.post("/sales", response_model=SaleOutput, status_code=201)
def create_sale(sale: SaleCreate, db: Session = Depends(get_db), user: dict = Depends(get_current_user)):
    representative = db.get(Representative, sale.representative_id)
    if representative is None:
        raise HTTPException(status_code=404, detail="Representative not found")
    check_store_access(user, representative.store_id)

    new_sale = Sale(**sale.model_dump())
    db.add(new_sale)
    db.commit()
    db.refresh(new_sale)
    return new_sale


@app.get("/stores/{store_id}/sales", response_model=list[SaleOutput])
def list_store_sales(
    store_id: int,
    limit: int = Query(10, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    check_store_access(user, store_id)
    query = (
        select(Sale)
        .join(Representative)
        .where(Representative.store_id == store_id)
        .order_by(Sale.created_at.desc())
        .limit(limit)
        .offset(offset)
    )
    return db.scalars(query).all()


@app.get("/stores/{store_id}/commissions", response_model=list[CommissionOutput])
def store_commission(store_id: int, db: Session = Depends(get_db), user: dict = Depends(get_current_user)):
    check_store_access(user, store_id)
    # SQL: select rep, product type, SUM(amount) grouped by rep and product type
    query = (
        select(Representative.id, Sale.product_type, func.sum(Sale.amount))
        .join(Sale)
        .where(Representative.store_id == store_id)
        .group_by(Representative.id, Sale.product_type)
    )

    report: dict[int, CommissionOutput] = {}
    for representative_id, product_type, total_amount in db.execute(query):
        row = report.setdefault(
            representative_id,
            CommissionOutput(representative_id=representative_id, total_sales=0.0, commission=0.0),
        )
        row.total_sales += total_amount
        row.commission += total_amount * COMMISSION_RATES[product_type]

    for row in report.values():
        row.total_sales = round(row.total_sales, 2)
        row.commission = round(row.commission, 2)

    return sorted(report.values(), key=lambda x: x.commission, reverse=True)

@app.get("/stores/{store_id}/monthly-sales", response_model=list[MonthlySalesOutput])
def store_monthly_outputs(store_id: int, db: Session = Depends(get_db), user: dict = Depends(get_current_user)):
    check_store_access(user, store_id)
    month = func.strftime("%Y-%m", Sale.created_at)
    query = (
        select(month.label("month"), func.sum(Sale.amount).label("total_sales"), func.count(Sale.id).label("num_sales"))
        .join(Representative)
        .where(Representative.store_id == store_id)
        .group_by(month)
        .order_by(month)
    )

    return [MonthlySalesOutput(month=m, total_sales=ts, num_sales=ns) for m, ts, ns in db.execute(query)]