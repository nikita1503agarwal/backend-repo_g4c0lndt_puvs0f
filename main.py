import os
from typing import List, Optional, Any, Dict
from fastapi import FastAPI, HTTPException, Depends, Header
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from bson import ObjectId

from database import db, create_document, get_documents
from schemas import Product, Category, ContactMessage, AdminCredentials

app = FastAPI(title="Product Catalog API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Helpers
class ObjectIdStr(str):
    @classmethod
    def __get_validators__(cls):
        yield cls.validate

    @classmethod
    def validate(cls, v):
        try:
            return str(ObjectId(str(v)))
        except Exception:
            raise ValueError("Invalid ObjectId")


def serialize_doc(doc: Dict[str, Any]):
    if not doc:
        return doc
    doc["id"] = str(doc.get("_id"))
    doc.pop("_id", None)
    return doc


def admin_token() -> str:
    return os.getenv("ADMIN_TOKEN", "admin-token")


def require_auth(authorization: Optional[str] = Header(None)):
    token = admin_token()
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Unauthorized")
    provided = authorization.split(" ", 1)[1]
    if provided != token:
        raise HTTPException(status_code=401, detail="Invalid token")


@app.get("/")
def read_root():
    return {"message": "Product Catalog Backend is running"}


@app.get("/test")
def test_database():
    response = {
        "backend": "✅ Running",
        "database": "❌ Not Available",
        "database_url": None,
        "database_name": None,
        "connection_status": "Not Connected",
        "collections": []
    }
    try:
        if db is not None:
            response["database"] = "✅ Available"
            response["database_url"] = "✅ Set" if os.getenv("DATABASE_URL") else "❌ Not Set"
            response["database_name"] = getattr(db, "name", None) or ""
            response["connection_status"] = "Connected"
            try:
                collections = db.list_collection_names()
                response["collections"] = collections[:10]
                response["database"] = "✅ Connected & Working"
            except Exception as e:
                response["database"] = f"⚠️ Connected but Error: {str(e)[:50]}"
        else:
            response["database"] = "⚠️ Available but not initialized"
    except Exception as e:
        response["database"] = f"❌ Error: {str(e)[:50]}"
    return response


# Auth
@app.post("/api/auth/login")
def login(payload: AdminCredentials):
    # Simple env-based auth for demo
    env_user = os.getenv("ADMIN_USER", "admin")
    env_pass = os.getenv("ADMIN_PASS", "admin123")
    if payload.username == env_user and payload.password == env_pass:
        return {"token": admin_token(), "user": {"name": env_user}}
    raise HTTPException(status_code=401, detail="Invalid credentials")


# Categories CRUD
@app.get("/api/categories")
def list_categories() -> List[dict]:
    items = list(db["category"].find({}).sort("name", 1)) if db else []
    return [serialize_doc(i) for i in items]


@app.post("/api/categories")
def create_category(cat: Category, _: Any = Depends(require_auth)):
    # ensure unique slug
    if db["category"].find_one({"slug": cat.slug}):
        raise HTTPException(400, detail="Slug already exists")
    new_id = create_document("category", cat)
    created = db["category"].find_one({"_id": ObjectId(new_id)})
    return serialize_doc(created)


@app.put("/api/categories/{category_id}")
def update_category(category_id: ObjectIdStr, cat: Category, _: Any = Depends(require_auth)):
    res = db["category"].update_one({"_id": ObjectId(category_id)}, {"$set": cat.model_dump()})
    if res.matched_count == 0:
        raise HTTPException(404, detail="Category not found")
    doc = db["category"].find_one({"_id": ObjectId(category_id)})
    return serialize_doc(doc)


@app.delete("/api/categories/{category_id}")
def delete_category(category_id: ObjectIdStr, _: Any = Depends(require_auth)):
    res = db["category"].delete_one({"_id": ObjectId(category_id)})
    if res.deleted_count == 0:
        raise HTTPException(404, detail="Category not found")
    return {"status": "deleted"}


# Products CRUD + listing
@app.get("/api/products")
def list_products(
    search: Optional[str] = None,
    category: Optional[str] = None,
    minPrice: Optional[float] = None,
    maxPrice: Optional[float] = None,
    sort: Optional[str] = None,  # price_asc, price_desc, name_asc
    page: int = 1,
    limit: int = 12,
):
    if page < 1:
        page = 1
    if limit < 1 or limit > 100:
        limit = 12

    q: Dict[str, Any] = {}
    if search:
        q["name"] = {"$regex": search, "$options": "i"}
    if category:
        q["category"] = category
    if minPrice is not None or maxPrice is not None:
        price_filter: Dict[str, Any] = {}
        if minPrice is not None:
            price_filter["$gte"] = float(minPrice)
        if maxPrice is not None:
            price_filter["$lte"] = float(maxPrice)
        q["price"] = price_filter

    sort_field = None
    sort_dir = 1
    if sort == "price_asc":
        sort_field, sort_dir = "price", 1
    elif sort == "price_desc":
        sort_field, sort_dir = "price", -1
    elif sort == "name_asc":
        sort_field, sort_dir = "name", 1

    cursor = db["product"].find(q)
    total = db["product"].count_documents(q)
    if sort_field:
        cursor = cursor.sort(sort_field, sort_dir)
    cursor = cursor.skip((page - 1) * limit).limit(limit)
    items = [serialize_doc(i) for i in cursor]
    return {"items": items, "total": total, "page": page, "limit": limit}


@app.get("/api/products/featured")
def featured_products(limit: int = 8):
    cursor = db["product"].find({"featured": True}).sort("name", 1).limit(limit)
    return [serialize_doc(i) for i in cursor]


@app.get("/api/products/{product_id}")
def get_product(product_id: ObjectIdStr):
    doc = db["product"].find_one({"_id": ObjectId(product_id)})
    if not doc:
        raise HTTPException(404, detail="Product not found")
    return serialize_doc(doc)


@app.post("/api/products")
def create_product(prod: Product, _: Any = Depends(require_auth)):
    new_id = create_document("product", prod)
    created = db["product"].find_one({"_id": ObjectId(new_id)})
    return serialize_doc(created)


@app.put("/api/products/{product_id}")
def update_product(product_id: ObjectIdStr, prod: Product, _: Any = Depends(require_auth)):
    res = db["product"].update_one({"_id": ObjectId(product_id)}, {"$set": prod.model_dump()})
    if res.matched_count == 0:
        raise HTTPException(404, detail="Product not found")
    doc = db["product"].find_one({"_id": ObjectId(product_id)})
    return serialize_doc(doc)


@app.delete("/api/products/{product_id}")
def delete_product(product_id: ObjectIdStr, _: Any = Depends(require_auth)):
    res = db["product"].delete_one({"_id": ObjectId(product_id)})
    if res.deleted_count == 0:
        raise HTTPException(404, detail="Product not found")
    return {"status": "deleted"}


# Admin summary
@app.get("/api/admin/summary")
def admin_summary(_: Any = Depends(require_auth)):
    prod_count = db["product"].count_documents({})
    cat_count = db["category"].count_documents({})
    return {"products": prod_count, "categories": cat_count}


# Contact form
@app.post("/api/contact")
def submit_contact(payload: ContactMessage):
    _ = create_document("contactmessage", payload)
    return {"status": "received"}


if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
