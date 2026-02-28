# -*- coding: utf-8 -*-
"""
Tests validating normalization constraints and inter-model relationships
introduced in the refactored data model:

- BookingItem: unique constraint on (booking_id, machine_id)
- AssignmentApprover: unique constraint on (assignment_id, approver_id)
- Machine → Location: optional FK and bidirectional relationship
- Location children: cascade delete-orphan behaviour
"""

import pytest
from sqlalchemy import create_engine
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker

from app.db import Base
from app.models import (
    Site, Location, Machine, User, BookingRequest, BookingItem,
    Assignment, AssignmentApprover,
)
from app.security import hash_password
from datetime import datetime, timedelta


@pytest.fixture()
def db():
    """In-memory SQLite session for each test."""
    engine = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine, future=True)
    with Session() as session:
        yield session


@pytest.fixture()
def site(db):
    s = Site(name="Test Hub", city="Manchester", lat=53.48, lon=-2.24)
    db.add(s)
    db.flush()
    return s


@pytest.fixture()
def user(db):
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
        team="QA",
        role="approver",
        status="active",
        manager_email="director@example.com",
    )
    db.add(u)
    db.flush()
    return u


@pytest.fixture()
def machine(db, site):
    m = Machine(
        name="TM-001",
        machine_type="lab",
        category="Core",
        status="available",
        site_id=site.id,
    )
    db.add(m)
    db.flush()
    return m


@pytest.fixture()
def booking(db, user, machine):
    start = datetime.utcnow() + timedelta(hours=1)
    end = start + timedelta(hours=2)
    b = BookingRequest(
        requester_id=user.id,
        start_at=start,
        end_at=end,
        purpose="test",
        status="pending",
    )
    db.add(b)
    db.flush()
    return b


# ---------------------------------------------------------------------------
# BookingItem – unique constraint (booking_id, machine_id)
# ---------------------------------------------------------------------------

def test_booking_item_duplicate_raises(db, booking, machine):
    """The same machine cannot appear twice in one booking."""
    db.add(BookingItem(booking_id=booking.id, machine_id=machine.id))
    db.flush()
    db.add(BookingItem(booking_id=booking.id, machine_id=machine.id))
    with pytest.raises(IntegrityError):
        db.flush()


def test_booking_item_same_machine_different_bookings_allowed(db, user, machine):
    """The same machine can be booked in two separate (non-overlapping) bookings."""
    start1 = datetime.utcnow() + timedelta(hours=1)
    b1 = BookingRequest(requester_id=user.id, start_at=start1,
                        end_at=start1 + timedelta(hours=1), purpose="a", status="pending")
    start2 = datetime.utcnow() + timedelta(hours=5)
    b2 = BookingRequest(requester_id=user.id, start_at=start2,
                        end_at=start2 + timedelta(hours=1), purpose="b", status="pending")
    db.add_all([b1, b2])
    db.flush()

    db.add(BookingItem(booking_id=b1.id, machine_id=machine.id))
    db.add(BookingItem(booking_id=b2.id, machine_id=machine.id))
    db.commit()  # must not raise


# ---------------------------------------------------------------------------
# AssignmentApprover – unique constraint (assignment_id, approver_id)
# ---------------------------------------------------------------------------

def test_assignment_approver_duplicate_raises(db, user, approver_user):
    """The same user cannot be added as approver twice for the same assignment."""
    a = Assignment(title="Test Assignment", owner_id=user.id)
    db.add(a)
    db.flush()

    db.add(AssignmentApprover(assignment_id=a.id, approver_id=approver_user.id))
    db.flush()
    db.add(AssignmentApprover(assignment_id=a.id, approver_id=approver_user.id))
    with pytest.raises(IntegrityError):
        db.flush()


def test_assignment_approver_same_user_different_assignments_allowed(db, user, approver_user):
    """The same user can be approver for two different assignments."""
    a1 = Assignment(title="Assignment Alpha", owner_id=user.id)
    a2 = Assignment(title="Assignment Beta", owner_id=user.id)
    db.add_all([a1, a2])
    db.flush()

    db.add(AssignmentApprover(assignment_id=a1.id, approver_id=approver_user.id))
    db.add(AssignmentApprover(assignment_id=a2.id, approver_id=approver_user.id))
    db.commit()  # must not raise


# ---------------------------------------------------------------------------
# Machine → Location: optional FK and relationship
# ---------------------------------------------------------------------------

def test_machine_without_location(db, site):
    """A machine does not require a location (location_id is nullable)."""
    m = Machine(name="VM-001", machine_type="virtual", category="GPU",
                status="available", site_id=site.id)
    db.add(m)
    db.commit()

    fetched = db.get(Machine, m.id)
    assert fetched.location_id is None
    assert fetched.location is None


def test_machine_with_location(db, site):
    """A machine can be placed in a specific location within its site."""
    loc = Location(name="Lab Room 1", code="LAB-R1", site_id=site.id)
    db.add(loc)
    db.flush()

    m = Machine(name="LAB-001", machine_type="lab", category="Core",
                status="available", site_id=site.id, location_id=loc.id)
    db.add(m)
    db.commit()

    fetched = db.get(Machine, m.id)
    assert fetched.location_id == loc.id
    assert fetched.location.name == "Lab Room 1"


def test_location_machines_backref(db, site):
    """Location.machines back-reference lists all machines in that location."""
    loc = Location(name="Server Room", site_id=site.id)
    db.add(loc)
    db.flush()

    m1 = Machine(name="SR-001", machine_type="lab", category="Core",
                 status="available", site_id=site.id, location_id=loc.id)
    m2 = Machine(name="SR-002", machine_type="lab", category="Core",
                 status="available", site_id=site.id, location_id=loc.id)
    db.add_all([m1, m2])
    db.commit()

    db.refresh(loc)
    assert len(loc.machines) == 2
    machine_names = {m.name for m in loc.machines}
    assert "SR-001" in machine_names
    assert "SR-002" in machine_names


# ---------------------------------------------------------------------------
# Location.children – cascade delete-orphan
# ---------------------------------------------------------------------------

def test_location_children_cascade_delete(db, site):
    """Deleting a parent Location also deletes all nested child locations."""
    parent = Location(name="Building A", site_id=site.id)
    db.add(parent)
    db.flush()

    child = Location(name="Floor 1", site_id=site.id, parent_id=parent.id)
    grandchild = Location(name="Room 101", site_id=site.id)
    db.add(child)
    db.flush()
    grandchild.parent_id = child.id
    db.add(grandchild)
    db.commit()

    child_id = child.id
    grandchild_id = grandchild.id

    # Delete the parent — children and grandchildren should be removed too
    db.delete(parent)
    db.commit()

    assert db.get(Location, child_id) is None
    assert db.get(Location, grandchild_id) is None
