from datetime import datetime, timedelta

import pytz
from sqlalchemy.orm import Session

LAST_REFRESH_TABLENAME = 'imp_last_ldap_refresh'


def get_last_refresh(session: Session) -> datetime:
    return session.execute(f"select * from {LAST_REFRESH_TABLENAME}").scalar()


def ldap_view_too_old(session: Session) -> bool:
    return datetime.now(tz=pytz.UTC) - get_last_refresh(session) > timedelta(days=1)


REFRESH_FUNCTION_NAME = 'imp_refresh_abe_ldap'


def refresh_ldap_view(session: Session):
    session.execute(f"select * from {REFRESH_FUNCTION_NAME}()")
    session.commit()
