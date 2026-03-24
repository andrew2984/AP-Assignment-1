# -*- coding: utf-8 -*-
"""Map blueprint: multi-site machine location view."""

from flask import Blueprint, render_template, current_app
from flask_login import login_required
from sqlalchemy import select, func
from ..models import Site, Machine

bp = Blueprint("map", __name__, url_prefix="/map")

@bp.get("/")
@login_required
def view_map():
    with current_app.session_factory() as db:
        sites = db.execute(select(Site).order_by(Site.city.asc())).scalars().all()

        stats = {}
        sites_payload = []

        for s in sites:
            total_machines = db.execute(
                select(func.count()).select_from(Machine).where(Machine.site_id == s.id)
            ).scalar_one()

            oos = db.execute(
                select(func.count()).select_from(Machine).where(
                    Machine.site_id == s.id, Machine.status == "out_of_service"
                )
            ).scalar_one()

            stats[s.id] = {"total_machines": total_machines, "out_of_service": oos}

            # ✅ JSON-serialisable dict
            sites_payload.append({
                "id": s.id,
                "name": s.name,
                "city": s.city,
                "lat": s.lat,
                "lon": s.lon,
            })

    return render_template("map.html", sites=sites_payload, stats=stats)

