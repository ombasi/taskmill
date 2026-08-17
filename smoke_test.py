#!/usr/bin/env python3
"""Lightweight smoke checks for Taskmill (no browser)."""
import os
import sys

def main():
    os.chdir(os.path.dirname(os.path.abspath(__file__)) or ".")
    errors = []
    try:
        from app import create_app
        app = create_app()
    except Exception as e:
        print("FAIL create_app:", e)
        return 1

    with app.app_context():
        try:
            from extensions import db
            db.session.execute(db.text("SELECT 1"))
            print("OK database")
        except Exception as e:
            errors.append(f"database: {e}")
            print("FAIL database:", e)

        for name in ("User", "Membership", "Product", "Deposit", "Withdrawal"):
            try:
                mod = __import__(f"models.{name.lower() if name != 'User' else 'user'}", fromlist=[name])
                # rough
            except Exception:
                pass
        try:
            from models.user import User
            from models.membership import Membership
            print("OK models", "users=", User.query.count(), "memberships=", Membership.query.count())
        except Exception as e:
            errors.append(f"models: {e}")
            print("FAIL models:", e)

        client = app.test_client()
        for path in ("/login", "/register", "/dashboard/faq", "/dashboard/about", "/dashboard/contact"):
            try:
                r = client.get(path, follow_redirects=False)
                ok = r.status_code in (200, 302)
                print(("OK" if ok else "FAIL"), path, r.status_code)
                if not ok:
                    errors.append(f"{path} -> {r.status_code}")
            except Exception as e:
                errors.append(f"{path}: {e}")
                print("FAIL", path, e)

        # auth-protected should redirect
        for path in ("/dashboard/", "/wallet/", "/tasks/"):
            try:
                r = client.get(path, follow_redirects=False)
                ok = r.status_code in (302, 401)
                print(("OK" if ok else "WARN"), path, r.status_code, "(expect redirect if logged out)")
            except Exception as e:
                print("FAIL", path, e)
                errors.append(str(e))

    if errors:
        print("\nSMOKE FAILED:", len(errors))
        return 1
    print("\nSMOKE PASSED")
    return 0

if __name__ == "__main__":
    sys.exit(main())
