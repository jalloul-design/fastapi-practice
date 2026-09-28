# Store Sales API (FastAPI)

A practice REST API modeled on retail store sales, built with FastAPI, SQLAlchemy and SQLite.

## Features
- Stores, sales reps and sales in a relational database (SQLAlchemy)
- Token-based access: admins see all stores; managers only see their own (deny by default)
- Pydantic validation (bad input returns 422)
- Pagination with `limit` and `offset`
- Commission report per rep using SQL GROUP BY, with different rates per product type

## Run it
```
pip install fastapi uvicorn sqlalchemy
python -m uvicorn salesapi:app --reload
```
Then open http://127.0.0.1:8000/docs

Test tokens: `admin-token`, `mgr-1624-token`, `mgr-2000-token` (sent in the `token` header)