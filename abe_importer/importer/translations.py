import re
from logging import Logger
from typing import List

from pycroft.helpers.i18n import deferred_gettext
from pycroft.model import _all as pycroft_model

from .. import model as abe_model
from .context import reg, IntermediateData, Context


@reg.provides(pycroft_model.Site)
def add_sites(_, data: IntermediateData):
    site = pycroft_model.Site(name="Hochschulstraße")
    data.hss_site = site
    return [site]


class ImportException(RuntimeError):
    pass


PycroftBase = pycroft_model.ModelBase


@reg.provides(pycroft_model.Building)
def translate_building(ctx: Context, data: IntermediateData) -> List[PycroftBase]:
    objs = []

    buildings: List[abe_model.Building] = ctx.query(abe_model.Building).all()
    for b in buildings:
        ctx.logger.debug(f"got building {b.short_name!r}")
        new_building = pycroft_model.Building(
            short_name=b.short_name,
            street=b.street,
            number=b.number,
        )
        data.buildings[b.short_name] = new_building
        objs.append(new_building)

    return objs


# We don't need to translate the external addresses, because the referenced accounts
# already have a mapping to a pycroft user
@reg.provides(pycroft_model.Address)
@reg.provides(pycroft_model.Room)
def translate_locations(ctx: Context, data: IntermediateData) -> List[PycroftBase]:
    objs = []
    accesses: List[abe_model.Access] = (
        ctx.query(abe_model.Access).filter(abe_model.Access.building != None).all()
    )

    for access in accesses:
        try:
            pycroft_building = data.buildings[access.building.short_name]
        except KeyError:
            ctx.logger.error("Could not find building data for shortname %s",
                             access.building.short_name)
            raise

        # consolidate nomecnlature
        level = access.floor
        room_number = f"{access.flat}{access.room}"
        address = pycroft_model.Address(
            street=access.building.street,
            number=access.building.number,
            zip_code=access.building.zip_code,
            addition=f"{level}-{room_number}"
        )
        objs.append(address)
        room = pycroft_model.Room(
            building=pycroft_building,
            inhabitable=True,
            level=level,
            number=room_number,
            address=address
        )
        objs.append(room)
        data.access_rooms[access.id] = room

    return objs


def sanitize_username(username: str):
    u = username.lower()

    if '_' in u:
        u = u.replace('_', '-')

    if re.match(r"^\d", u):
        u = f"hss-user-{u}"

    u = re.sub(r"([.-])*$", "", u)

    return u


@reg.provides(pycroft_model.User)
@reg.provides(pycroft_model.Account)
@reg.provides(pycroft_model.UnixAccount)
def translate_accounts(ctx: Context, data: IntermediateData) -> List[PycroftBase]:
    objs = []
    num_errors = 0
    ctx.logger.info("There are %s accounts in total.",
                    ctx.query(abe_model.Account).count())
    # 1. Accounts which do _not_ have a pycroft mapping
    accounts_with_access: List[abe_model.Account] = (
        ctx.query(abe_model.Account)
           .filter_by(pycroft_login=None)
           .filter(abe_model.Account.access_id != None)
           .all()
    )
    for acc in accounts_with_access:
        try:
            room = data.access_rooms[acc.access_id]
        except KeyError as e:
            ctx.logger.error("Could not find room for access %s (account %s)",
                             acc.access_id, acc.account)
            ctx.logger.debug(e.args)
            num_errors += 1
            continue

        props: abe_model.AccountProperty = acc.property
        chosen_login = sanitize_username(acc.account)
        if chosen_login != acc.account:
            ctx.logger.warning("Renaming '%s' → '%s'", acc.account, chosen_login)

        # TODO find out whether this user already exists in pycroft

        try:
            user = pycroft_model.User(
                login=chosen_login,
                room=room,
                address=room.address,
                # birthdate=acc.birth_date,  # TODO add birth date to model
                email=maybe_fix_mail(props.mail, ctx.logger),
            )
        except pycroft_model.IllegalLoginError as e:
            ctx.logger.error("Account '%s' has invalid login!",
                             chosen_login)
            ctx.logger.debug(e.args)
            num_errors += 1
            continue

        # TODO find password from ldap (or import that later)

        finance_account = pycroft_model.Account(
            name=deferred_gettext(u"HSS:User {login}").format(id=chosen_login).to_json(),
            type='USER_ASSET',
        )
        user.account = finance_account
        unix_acc = pycroft_model.UnixAccount(home_directory=f"/home/{chosen_login}")
        user.unix_account = unix_acc

        # TODO add user to data

        objs.extend([user, finance_account, unix_acc])

        # TODO (in a separate translation) add memberships -> What about (former) orgs?.

    # TODO import people with pycroft mapping
    # TODO warn on people with neither access nor pycroft mapping
    _maybe_abort(num_errors, ctx.logger)
    return objs


def maybe_fix_mail(mail: str, logger: Logger) -> str:
    if ".@" not in mail:
        return mail

    new_mail = mail.replace(".@", "_@")
    logger.warning("Changing mail %s → %s", mail, new_mail)
    return new_mail


def _maybe_abort(num_errors: int, logger: Logger):
    if num_errors:
        logger.critical("Got %s errors. Aborting.", num_errors)
        raise ImportException
