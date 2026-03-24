# -*- coding: utf-8 -*-
"""Authentication and registration routes."""

from flask import Blueprint, render_template, redirect, url_for, flash, current_app
from flask_login import login_user, logout_user, login_required, current_user
from sqlalchemy import select
from ..forms import RegisterForm, LoginForm
from ..models import User, AuditLog
from ..security import hash_password, verify_password

bp = Blueprint("auth", __name__)

@bp.get("/")
def home():
    return render_template("home.html")

@bp.route("/register", methods=["GET", "POST"])
def register():
    form = RegisterForm()
    if form.validate_on_submit():
        with current_app.session_factory() as db:
            exists = db.execute(select(User).where(User.email == form.email.data.lower())).scalar_one_or_none()
            if exists:
                flash("An account with that email already exists.", "warning")
                return render_template("register.html", form=form)

            user = User(
                name=form.name.data.strip(),
                email=form.email.data.lower(),
                password_hash=hash_password(form.password.data),
                team=form.team.data.strip(),
                manager_email=form.manager_email.data.lower(),
                role="user",
                status="pending",
            )
            db.add(user)
            db.add(AuditLog(actor_email=user.email, action="register", detail="User registered; awaiting manager approval"))
            db.commit()

        flash("Account created. Your manager must approve your access before you can sign in.", "success")
        return redirect(url_for("auth.login"))

    return render_template("register.html", form=form)

@bp.route("/login", methods=["GET", "POST"])
def login():
    form = LoginForm()
    if form.validate_on_submit():
        with current_app.session_factory() as db:
            user = db.execute(select(User).where(User.email == form.email.data.lower())).scalar_one_or_none()
            if not user or not verify_password(user.password_hash, form.password.data):
                flash("Invalid email or password.", "danger")
                return render_template("login.html", form=form)

            if user.status != "active":
                flash("Your account is not active yet. Please wait for manager approval.", "warning")
                return render_template("login.html", form=form)

            login_user(user)
            db.add(AuditLog(actor_email=user.email, action="login", detail="User signed in"))
            db.commit()

        return redirect(url_for("bookings.my_bookings"))

    return render_template("login.html", form=form)

@bp.get("/logout")
@login_required
def logout():
    email = current_user.email
    logout_user()
    flash("Signed out.", "info")
    with current_app.session_factory() as db:
        db.add(AuditLog(actor_email=email, action="logout", detail="User signed out"))
        db.commit()
    return redirect(url_for("auth.home"))
