
"""TOTP helpers for authenticator apps (Google Authenticator, Authy, etc.)."""
import pyotp
import qrcode
import io
import base64


def new_secret():
    return pyotp.random_base32()


def provisioning_uri(secret, username, issuer="Taskmill"):
    return pyotp.TOTP(secret).provisioning_uri(name=username, issuer_name=issuer)


def verify_code(secret, code, valid_window=1):
    if not secret or not code:
        return False
    code = str(code).strip().replace(" ", "")
    try:
        return pyotp.TOTP(secret).verify(code, valid_window=valid_window)
    except Exception:
        return False


def qr_data_url(uri):
    img = qrcode.make(uri)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    b64 = base64.b64encode(buf.getvalue()).decode("ascii")
    return f"data:image/png;base64,{b64}"
