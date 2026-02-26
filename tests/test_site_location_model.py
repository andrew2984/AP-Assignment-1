# -*- coding: utf-8 -*-
"""
Tests for the enhanced Site model and the new Location model.
"""

import json
from datetime import datetime

import pytest
from sqlalchemy import create_engine
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker

from app.db import Base
from app.models import Site, Location


@pytest.fixture()
def db():
    """Provide an in-memory SQLite session for each test."""
    engine = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine, future=True)
    with Session() as session:
        yield session


@pytest.fixture()
def site(db):
    s = Site(
        name="Test Hub North",
        code="MAN",
        city="Manchester",
        country="England",
        address="1 Piccadilly Gardens, Manchester, M1 1RG",
        lat=53.4808,
        lon=-2.2426,
        description="Northern test hub.",
    )
    db.add(s)
    db.flush()
    return s


# ---------------------------------------------------------------------------
# Site – new optional fields
# ---------------------------------------------------------------------------

def test_site_new_fields_persisted(db, site):
    fetched = db.get(Site, site.id)
    assert fetched.code == "MAN"
    assert fetched.country == "England"
    assert fetched.address == "1 Piccadilly Gardens, Manchester, M1 1RG"
    assert fetched.description == "Northern test hub."


def test_site_new_fields_optional(db):
    """Existing fields still work without the new optional columns."""
    s = Site(name="Minimal Site", city="Bristol", lat=51.45, lon=-2.59)
    db.add(s)
    db.commit()

    fetched = db.get(Site, s.id)
    assert fetched.code is None
    assert fetched.country is None
    assert fetched.address is None
    assert fetched.description is None


def test_site_code_is_unique(db, site):
    duplicate = Site(name="Another Site", code="MAN", city="Leeds", lat=53.8, lon=-1.55)
    db.add(duplicate)
    with pytest.raises(IntegrityError):
        db.flush()


def test_site_name_is_unique(db, site):
    duplicate = Site(name="Test Hub North", city="Leeds", lat=53.8, lon=-1.55)
    db.add(duplicate)
    with pytest.raises(IntegrityError):
        db.flush()


# ---------------------------------------------------------------------------
# Location – basic CRUD
# ---------------------------------------------------------------------------

def test_location_creation(db, site):
    loc = Location(
        name="Lab Area",
        code="LAB",
        site_id=site.id,
        floor="1",
        description="Physical lab.",
    )
    db.add(loc)
    db.commit()

    fetched = db.get(Location, loc.id)
    assert fetched.name == "Lab Area"
    assert fetched.code == "LAB"
    assert fetched.floor == "1"
    assert fetched.description == "Physical lab."
    assert fetched.parent_id is None
    assert isinstance(fetched.created_at, datetime)
    assert fetched.updated_at is None


def test_location_site_relationship(db, site):
    loc = Location(name="Server Room", site_id=site.id)
    db.add(loc)
    db.commit()

    fetched = db.get(Location, loc.id)
    assert fetched.site.name == "Test Hub North"
    assert fetched.site.code == "MAN"


def test_site_locations_backref(db, site):
    db.add(Location(name="Lab", site_id=site.id))
    db.add(Location(name="Virtual Lab", site_id=site.id))
    db.commit()

    db.refresh(site)
    assert len(site.locations) == 2
    location_names = {loc.name for loc in site.locations}
    assert "Lab" in location_names
    assert "Virtual Lab" in location_names


# ---------------------------------------------------------------------------
# Location – hierarchy (parent / children)
# ---------------------------------------------------------------------------

def test_location_parent_child(db, site):
    parent = Location(name="Building A", code="BLDA", site_id=site.id)
    db.add(parent)
    db.flush()

    child = Location(name="Floor 1", code="BLDA-F1", site_id=site.id, parent_id=parent.id)
    db.add(child)
    db.commit()

    fetched_child = db.get(Location, child.id)
    assert fetched_child.parent_id == parent.id
    assert fetched_child.parent.name == "Building A"

    fetched_parent = db.get(Location, parent.id)
    assert len(fetched_parent.children) == 1
    assert fetched_parent.children[0].name == "Floor 1"


def test_location_three_level_hierarchy(db, site):
    building = Location(name="Building B", site_id=site.id)
    db.add(building)
    db.flush()

    floor = Location(name="Floor 2", site_id=site.id, parent_id=building.id)
    db.add(floor)
    db.flush()

    room = Location(name="Room 201", site_id=site.id, parent_id=floor.id)
    db.add(room)
    db.commit()

    fetched_room = db.get(Location, room.id)
    assert fetched_room.parent.name == "Floor 2"
    assert fetched_room.parent.parent.name == "Building B"


def test_location_parent_is_optional(db, site):
    loc = Location(name="Top-level Lab", site_id=site.id)
    db.add(loc)
    db.commit()

    fetched = db.get(Location, loc.id)
    assert fetched.parent_id is None
    assert fetched.parent is None
    assert fetched.children == []


# ---------------------------------------------------------------------------
# Location – metadata_json
# ---------------------------------------------------------------------------

def test_location_metadata_json(db, site):
    meta = {"capacity": 10, "accessible": True, "tags": ["lab", "secure"]}
    loc = Location(name="Secure Lab", site_id=site.id, metadata_json=json.dumps(meta))
    db.add(loc)
    db.commit()

    fetched = db.get(Location, loc.id)
    loaded = json.loads(fetched.metadata_json)
    assert loaded["capacity"] == 10
    assert loaded["accessible"] is True
    assert "secure" in loaded["tags"]


def test_location_metadata_json_optional(db, site):
    loc = Location(name="Plain Room", site_id=site.id)
    db.add(loc)
    db.commit()

    fetched = db.get(Location, loc.id)
    assert fetched.metadata_json is None


# ---------------------------------------------------------------------------
# Location – unique constraint (site_id, code)
# ---------------------------------------------------------------------------

def test_location_code_unique_within_site(db, site):
    db.add(Location(name="Lab A", code="LAB", site_id=site.id))
    db.flush()
    db.add(Location(name="Lab B", code="LAB", site_id=site.id))
    with pytest.raises(IntegrityError):
        db.flush()


def test_location_same_code_different_sites(db, site):
    """The same code is allowed across different sites."""
    other_site = Site(name="Test Hub South", code="LON", city="London", lat=51.5, lon=-0.1)
    db.add(other_site)
    db.flush()

    db.add(Location(name="Lab", code="LAB", site_id=site.id))
    db.add(Location(name="Lab", code="LAB", site_id=other_site.id))
    db.commit()  # should not raise
