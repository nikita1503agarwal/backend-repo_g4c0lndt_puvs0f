"""
Database Schemas

Define your MongoDB collection schemas here using Pydantic models.
These schemas are used for data validation in your application.

Each Pydantic model represents a collection in your database.
Model name is converted to lowercase for the collection name:
- User -> "user" collection
- Product -> "product" collection
- BlogPost -> "blogs" collection
"""

from pydantic import BaseModel, Field, HttpUrl
from typing import Optional, List

# Core business schemas for the Product Catalog app

class Category(BaseModel):
    """
    Product categories
    Collection name: "category"
    """
    name: str = Field(..., description="Category name (e.g., Pakaian, Elektronik)")
    slug: str = Field(..., description="URL-friendly identifier")
    description: Optional[str] = Field(None, description="Optional description for the category")

class Product(BaseModel):
    """
    Products collection schema
    Collection name: "product"
    """
    name: str = Field(..., description="Product name")
    description: Optional[str] = Field(None, description="Detailed product description")
    price: float = Field(..., ge=0, description="Price in local currency (e.g., IDR)")
    category: str = Field(..., description="Category slug this product belongs to")
    images: List[str] = Field(default_factory=list, description="List of image URLs")
    in_stock: bool = Field(True, description="Whether product is in stock")
    stock: Optional[int] = Field(None, ge=0, description="Stock count (optional)")
    featured: bool = Field(False, description="Mark product as featured for homepage")

class ContactMessage(BaseModel):
    """Simple contact form submissions"""
    name: str
    email: str
    message: str

class AdminCredentials(BaseModel):
    """Credentials payload for admin login"""
    username: str
    password: str
