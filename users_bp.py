# -*- coding: utf-8 -*-
from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_user, logout_user, login_required, current_user
from app import db
from models import User
from forms import LoginForm, RegisterForm

users_bp = Blueprint("users_bp", __name__)

@users_bp.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("main.dashboard"))
    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(username=form.username.data).first()
        if user and user.check_password(form.password.data):
            login_user(user, remember=form.remember.data)
            flash("Giriş başarılı!", "success")
            next_page = request.args.get("next")
            return redirect(next_page or url_for("main.dashboard"))
        else:
            flash("Kullanıcı adı veya şifre hatalı.", "danger")
    return render_template("login.html", title="Giriş", form=form)

@users_bp.route("/register", methods=["GET", "POST"])
def register():
    if current_user.is_authenticated:
        return redirect(url_for("main.dashboard"))
    form = RegisterForm()
    if form.validate_on_submit():
        if User.query.filter_by(username=form.username.data).first():
            flash("Bu kullanıcı adı zaten alınmış.", "danger")
            return redirect(url_for("users_bp.register"))
        u = User(username=form.username.data)
        u.set_password(form.password.data)
        db.session.add(u)
        db.session.commit()
        flash("Kayıt başarılı! Giriş yapabilirsiniz.", "success")
        return redirect(url_for("users_bp.login"))
    return render_template("register.html", title="Kayıt", form=form)

@users_bp.route("/logout")
@login_required
def logout():
    logout_user()
    flash("Başarıyla çıkış yapıldı.", "success")
    return redirect(url_for("users_bp.login"))
