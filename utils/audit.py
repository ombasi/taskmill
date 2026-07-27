from flask import request

from extensions import db
from models.audit_log import AuditLog


def log_admin_action(
    admin,
    module,
    action,
    target="",
    description=""
):
    """
    Record an admin action in the audit log.
    """

    log = AuditLog(

        admin_id=admin.id,

        module=module,

        action=action,

        target=target,

        description=description,

        ip_address=request.remote_addr

    )

    db.session.add(log)