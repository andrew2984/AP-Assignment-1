# -*- coding: utf-8 -*-
"""
Tests for the Assignment and AssignmentApprover data models.
"""

from datetime import datetime

import pytest
from sqlalchemy import create_engine

from sqlalchemy.orm import sessionmaker

from app.db import Base
from app.models import User, Assignment, AssignmentApprover, AccessRequest
from app.security import hash_password


@pytest.fixture()
def db():
    """Provide an in-memory SQLite session for each test."""
    engine = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine, future=True)
    with Session() as session:
        yield session


@pytest.fixture()
def owner(db):
    u = User(
        name="Alice",
        email="alice@example.com",
        password_hash=hash_password("Password123!"),
        team="Engineering",
        role="user",
        status="active",
        manager_email="boss@example.com",
    )
    db.add(u)
    db.flush()
    return u


@pytest.fixture()
def approver_user(db):
    u = User(
        name="Bob",
        email="bob@example.com",
        password_hash=hash_password("Password123!"),
        team="QA Governance",
        role="approver",
        status="active",
        manager_email="director@example.com",
    )
    db.add(u)
    db.flush()
    return u


# ---------------------------------------------------------------------------
# Assignment model
# ---------------------------------------------------------------------------

def test_assignment_defaults(db, owner):
    a = Assignment(title="Payments Regression Suite", owner_id=owner.id)
    db.add(a)
    db.commit()

    fetched = db.get(Assignment, a.id)
    assert fetched.status == "active"
    assert fetched.description is None
    assert fetched.updated_at is None
    assert isinstance(fetched.created_at, datetime)


def test_assignment_with_description(db, owner):
    a = Assignment(
        title="Networking Load Tests",
        description="Full end-to-end network performance tests for Q2.",
        owner_id=owner.id,
    )
    db.add(a)
    db.commit()

    fetched = db.get(Assignment, a.id)
    assert fetched.title == "Networking Load Tests"
    assert "Q2" in fetched.description


def test_assignment_status_transitions(db, owner):
    a = Assignment(title="Core Platform Testing", owner_id=owner.id)
    db.add(a)
    db.flush()

    a.status = "completed"
    a.updated_at = datetime.utcnow()
    db.commit()

    fetched = db.get(Assignment, a.id)
    assert fetched.status == "completed"
    assert fetched.updated_at is not None


def test_assignment_owner_relationship(db, owner):
    a = Assignment(title="Data Pipeline Audit", owner_id=owner.id)
    db.add(a)
    db.commit()

    fetched = db.get(Assignment, a.id)
    assert fetched.owner.email == "alice@example.com"


# ---------------------------------------------------------------------------
# AssignmentApprover model
# ---------------------------------------------------------------------------

def test_assignment_approver_creation(db, owner, approver_user):
    a = Assignment(title="Devices Testing", owner_id=owner.id)
    db.add(a)
    db.flush()

    ap = AssignmentApprover(assignment_id=a.id, approver_id=approver_user.id)
    db.add(ap)
    db.commit()

    fetched = db.get(AssignmentApprover, ap.id)
    assert fetched.assignment_id == a.id
    assert fetched.approver_id == approver_user.id
    assert isinstance(fetched.assigned_at, datetime)


def test_assignment_has_multiple_approvers(db, owner, approver_user):
    second_approver = User(
        name="Carol",
        email="carol@example.com",
        password_hash=hash_password("Password123!"),
        team="Security",
        role="approver",
        status="active",
        manager_email="director@example.com",
    )
    db.add(second_approver)
    db.flush()

    a = Assignment(title="Security Audit", owner_id=owner.id)
    db.add(a)
    db.flush()

    db.add(AssignmentApprover(assignment_id=a.id, approver_id=approver_user.id))
    db.add(AssignmentApprover(assignment_id=a.id, approver_id=second_approver.id))
    db.commit()

    fetched = db.get(Assignment, a.id)
    assert len(fetched.approvers) == 2
    approver_emails = {ap.approver.email for ap in fetched.approvers}
    assert "bob@example.com" in approver_emails
    assert "carol@example.com" in approver_emails


def test_assignment_approver_relationship(db, owner, approver_user):
    a = Assignment(title="Integration Testing", owner_id=owner.id)
    db.add(a)
    db.flush()

    ap = AssignmentApprover(assignment_id=a.id, approver_id=approver_user.id)
    db.add(ap)
    db.commit()

    fetched = db.get(AssignmentApprover, ap.id)
    assert fetched.assignment.title == "Integration Testing"
    assert fetched.approver.email == "bob@example.com"


# ---------------------------------------------------------------------------
# Assignment ↔ AccessRequest relationship
# ---------------------------------------------------------------------------

def test_access_request_links_to_assignment(db, owner):
    a = Assignment(title="Regression Suite", owner_id=owner.id)
    db.add(a)
    db.flush()

    req = AccessRequest(
        requester_id=owner.id,
        assignment="Regression Suite",
        assignment_id=a.id,
    )
    db.add(req)
    db.commit()

    fetched_req = db.get(AccessRequest, req.id)
    assert fetched_req.assignment_id == a.id
    assert fetched_req.assignment_ref.title == "Regression Suite"


def test_assignment_access_requests_backref(db, owner):
    a = Assignment(title="Platform Testing", owner_id=owner.id)
    db.add(a)
    db.flush()

    req1 = AccessRequest(requester_id=owner.id, assignment="Platform Testing", assignment_id=a.id)
    req2 = AccessRequest(requester_id=owner.id, assignment="Platform Testing", assignment_id=a.id)
    db.add_all([req1, req2])
    db.commit()

    fetched = db.get(Assignment, a.id)
    assert len(fetched.access_requests) == 2


def test_access_request_assignment_id_is_optional(db, owner):
    """assignment_id is nullable for backward compatibility."""
    req = AccessRequest(requester_id=owner.id, assignment="Ad-hoc task")
    db.add(req)
    db.commit()

    fetched = db.get(AccessRequest, req.id)
    assert fetched.assignment_id is None
    assert fetched.assignment_ref is None


# ---------------------------------------------------------------------------
# User back-references
# ---------------------------------------------------------------------------

def test_user_owned_assignments_backref(db, owner):
    a1 = Assignment(title="Assignment A", owner_id=owner.id)
    a2 = Assignment(title="Assignment B", owner_id=owner.id)
    db.add_all([a1, a2])
    db.commit()

    db.refresh(owner)
    assert len(owner.owned_assignments) == 2


def test_user_assignment_approver_roles_backref(db, owner, approver_user):
    a1 = Assignment(title="Assignment C", owner_id=owner.id)
    a2 = Assignment(title="Assignment D", owner_id=owner.id)
    db.add_all([a1, a2])
    db.flush()

    db.add(AssignmentApprover(assignment_id=a1.id, approver_id=approver_user.id))
    db.add(AssignmentApprover(assignment_id=a2.id, approver_id=approver_user.id))
    db.commit()

    db.refresh(approver_user)
    assert len(approver_user.assignment_approver_roles) == 2
