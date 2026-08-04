"""TOTP helpers for authenticator apps (Google Authenticator, Authy, etc.)."""
import base64
import io


def _require_pyotp():
    try:
        import pyotp
        return pyotp
    except ImportError as e:
        raise ImportError(
            "Missing package 'pyotp'. Run: pip install pyotp qrcode"
        ) from e


def new_secret():
    pyotp = _require_pyotp()
    return pyotp.random_base32()


def provisioning_uri(secret, username, issuer="Taskmill"):
    pyotp = _require_pyotp()
    return pyotp.TOTP(secret).provisioning_uri(name=username, issuer_name=issuer)


def verify_code(secret, code, valid_window=1):
    if not secret or not code:
        return False
    code = str(code).strip().replace(" ", "")
    try:
        pyotp = _require_pyotp()
        return pyotp.TOTP(secret).verify(code, valid_window=valid_window)
    except Exception:
        return False


def qr_data_url(uri):
    """PNG data URL without requiring Pillow (uses qrcode pure PNG factory)."""
    try:
        import qrcode
    except ImportError as e:
        raise ImportError(
            "Missing package 'qrcode'. Run: pip install pyotp qrcode"
        ) from e

    qr = qrcode.QRCode(version=None, box_size=6, border=2)
    qr.add_data(uri)
    qr.make(fit=True)

    # Prefer pure PNG (no PIL). Fall back to PIL if available.
    img = None
    try:
        from qrcode.image.pure import PyPNGImage
        img = qr.make_image(image_factory=PyPNGImage)
    except Exception:
        try:
            img = qr.make_image(fill_color="black", back_color="white")
        except Exception as e:
            raise ImportError(
                "QR generation failed. Run: pip install pillow  (or use the manual key)"
            ) from e

    buf = io.BytesIO()
    # PyPNGImage.save may take stream; PIL Image.save too
    try:
        img.save(buf, format="PNG")
    except TypeError:
        img.save(buf)
    b64 = base64.b64encode(buf.getvalue()).decode("ascii")
    return f"data:image/png;base64,{b64}"
