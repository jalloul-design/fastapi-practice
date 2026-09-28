from fastapi import FastAPI, Depends, HTTPException, Header
from pydantic import BaseModel

app = FastAPI(title="Store Sales API")

class Sale(BaseModel):
    id: int | None = None
    store_id: int
    rep_id: int
    store_amount: float

sales_db: list[Sale] = []

def get_user(x_user: str = Header(default="user")):
    return x_user

def require_manager(user: str = Depends(get_user)):
    if user != "manager":
        raise HTTPException(status_code=403, detail="Access denied")
    return user

code 
@app.get("/sales")
def get_list_of_sales(store_id: int | None = None):
    if store_id is None:
        return sales_db
    return [sale for sale in sales_db if sale.store_id == store_id]

@app.post("/sales", status_code=201)
def create_sale(sale: Sale, user: str = Depends(require_manager)):
    sale.id = len(sales_db) + 1
    sales_db.append(sale)
    return sale

@app.get("/sales/{store_id}/total")
def store_total(store_id: int):
    total = sum(sale.store_amount for sale in sales_db if sale.store_id == store_id)
    return {"store_id": store_id, "total": total}