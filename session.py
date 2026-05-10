from flask import session


def set_login(is_login: bool):
    session["login"] = is_login


def is_login():
    return session.get("login", False)


def set_user_id(user_id):
    session["user_id"] = user_id


def get_user_id():
    return session.get("user_id", "")


def set_user_name(name):
    session["user_name"] = name


def get_user_name():
    return session.get("user_name", "")


def set_user_role(role):
    session["user_role"] = role


def get_user_role():
    return session.get("user_role", "")


def is_admin():
    return session.get("user_role") == "admin"


def is_patient():
    return session.get("user_role") == "patient"


def logout():
    session.clear()