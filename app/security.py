# -*- coding: utf-8 -*-
"""Security helpers: password hashing and role-based access control."""

from werkzeug.security import generate_password_hash, check_password_hash

def hash_password(password: str) -> str:
    return generate_password_hash(password)

def verify_password(password_hash: str, password: str) -> bool:
    return check_password_hash(password_hash, password)

def require_role(user_role: str, allowed: set[str]) -> bool:
    return user_role in allowed
