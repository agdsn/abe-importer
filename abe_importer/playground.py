from typing import List

import colorama
from sqlalchemy import select
from sqlalchemy.orm import joinedload

from . import model as abe_model
from .cli import read_uri, check_connections
from .importer.context import Context
from .importer.membership import MEMBERSHIP_FEE_PATTERN, get_latest_month
from .logging import setup_logger
from .session import create_session


def main():
    colorama.init()
    abe_session = create_session(read_uri(uri_file='.abe_uri'))
    pycroft_session = create_session(read_uri(uri_file='.pycroft_uri'))
    logger_name = 'abe-importer'
    logger = setup_logger(logger_name, verbose=True)

    check_connections(abe_session, pycroft_session, logger=logger)

    ctx = Context(abe_session, pycroft_session, logger=logger)
    descs = [d[0] for d in ctx.abe_session.execute(
        select((abe_model.FeeInfo.description,))
        .where(abe_model.FeeInfo.description.like(MEMBERSHIP_FEE_PATTERN))
        .select_from(abe_model.FeeInfo)
    )]

    # ctx.logger.info("Current descriptions:")
    # for desc in descs:
    #     ctx.logger.info(desc)
    ctx.logger.info("Latest month: %s", get_latest_month(descs))

    all_accounts: List[abe_model.Account] = abe_session.query(abe_model.Account)\
        .options(joinedload(abe_model.Account.booked_fees)).all()

    ctx.logger.info("Fees of usesrs starting with pa:")
    for a in all_accounts:
        if not a.account.startswith("pak"):
            continue

        ctx.logger.info("Account %s has %d fees.", a, len(a.booked_fees))
        for f in a.booked_fees:
            ctx.logger.debug(f)


if __name__ == '__main__':
    main()
