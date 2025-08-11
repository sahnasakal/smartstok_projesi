# -*- coding: utf-8 -*-
from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, BooleanField, SubmitField
from wtforms.validators import DataRequired, Length

class LoginForm(FlaskForm):
    username = StringField("Kullanıcı Adı", validators=[DataRequired(), Length(min=3, max=80)])
    password = PasswordField("Şifre", validators=[DataRequired(), Length(min=3, max=128)])
    remember = BooleanField("Beni Hatırla")
    submit = SubmitField("Giriş")

class RegisterForm(FlaskForm):
    username = StringField("Kullanıcı Adı", validators=[DataRequired(), Length(min=3, max=80)])
    password = PasswordField("Şifre", validators=[DataRequired(), Length(min=3, max=128)])
    submit = SubmitField("Kaydol")
