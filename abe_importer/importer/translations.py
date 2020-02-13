import re
from logging import Logger
from typing import List, Optional

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


ROOT_ID = 0


@reg.provides(pycroft_model.Building)
def translate_building(ctx: Context, data: IntermediateData) -> List[PycroftBase]:
    objs = []

    hss = pycroft_model.Site(name="Hochschulstraße")
    objs.append(hss)

    buildings: List[abe_model.Building] = ctx.query(abe_model.Building).all()
    for b in buildings:
        ctx.logger.debug(f"got building {b.short_name!r}")
        new_building = pycroft_model.Building(
            short_name=b.short_name,
            street=b.street,
            number=b.number,
            site=hss,
        )
        data.buildings[b.short_name] = new_building
        objs.append(new_building)

    return objs


def addr_equal(a1: pycroft_model.Address, a2: pycroft_model.Address) -> bool:
    keys = ['street', 'number', 'addition', 'zip_code', 'city', 'state', 'country']
    return all(getattr(a1, k) == getattr(a2, k) for k in keys)


# @reg.provides(pycroft_model.Switch, pycroft_model.Host,
#              satisfies=(pycroft_model.Switch.host,))
def maybe_existing_address(address: pycroft_model.Address, objs: List[pycroft_model.IntegerIdModel]) \
        -> pycroft_model.Address:
    # TODO check whether this is still needed
    server_addrs = [a for a in objs if isinstance(a, pycroft_model.Address) and addr_equal(a, address)]
    assert len(server_addrs) <= 2, f"there are more than two addresses like {address}"
    return address if not server_addrs else server_addrs[0]


def translate_switch(ctx: Context, data: IntermediateData) -> List[PycroftBase]:
    objs = []

    switches: List[abe_model.Switch] = ctx.query(abe_model.Switch).all()

    for s in switches:
        ctx.logger.debug(f"got switch {s.name!r}")

        try:
            building = data.buildings[s.building]
        except KeyError:
            ctx.logger.error(f"switch {s.name!r} references nonextistent building {s.building!r}")
            continue
        address = maybe_existing_address(
            address_from_building(s.building_rel, s.level, s.room_number + "_datenraum"),
            objs
        )
        room = pycroft_model.Room(
            building=building,
            level=s.level,
            number=s.room_number,
            inhabitable=False,
            address=address,
        )
        objs.append(room)

        host = pycroft_model.Host(
            name=s.name,
            room=room,
            owner_id=ROOT_ID,
        )
        objs.append(host)

        switch = pycroft_model.Switch(
            host=host,
            management_ip=s.mgmt_ip,
        )
        objs.append(switch)
        data.switches[s.name] = switch  # necessary for ref in `SwitchPort`s

    return objs


def try_create_switch_port(access: abe_model.Access, data, logger: Logger) \
        -> Optional[pycroft_model.SwitchPort]:
    if not access.port:
        return None

    try:
        switch = data.switches[access.switch]
    except KeyError:
        logger.critical("Could not find switch %r in intermediate data", access.switch)
        raise
        # TODO add an `ImporterError` (here: `InconsistencyError`) for nicer reporting

    return pycroft_model.SwitchPort(
        switch=switch,
        name=access.port,
        # TODO add default_vlans
    )


def address_from_building(building: abe_model.Building,
                          level: int,
                          room_number: str) -> pycroft_model.Address:
    return pycroft_model.Address(
        street=building.street,
        number=building.number,
        zip_code=building.zip_code,
        addition=f"{level}-{room_number}"
    )


def try_create_room(access: abe_model.Access, data, logger: Logger) \
        -> Optional[pycroft_model.Room]:
    if not access.building:
        return None

    try:
        pycroft_building = data.buildings[access.building.short_name]
    except KeyError:
        logger.error("Could not find building data for shortname %s",
                     access.building.short_name)
        raise

    # consolidate nomecnlature
    try:
        level = int(access.floor)
    except ValueError:
        logger.warning("access with non-integer floor: %r", access)
        return None

    room_number = f"{access.flat}{access.room}"
    address = address_from_building(access.building, level, room_number)
    room = pycroft_model.Room(
        building=pycroft_building,
        inhabitable=True,
        level=level,
        number=room_number,
        address=address
    )
    return room  # address will be committed as well


def try_create_patch_port(room: pycroft_model.Room, access: abe_model.Access,
                          data: IntermediateData,
                          logger: Logger) -> Optional[pycroft_model.PatchPort]:
    if not access.switch:
        logger.warning(f"Access {access.id} ({room.short_name}) has no switch! "
                       f"You may need to create the PatchPort manually.")
        return None
    return pycroft_model.PatchPort(
        room=room,
        switch_room=data.switches[access.switch].host.room,
        name=f"??"  # ({room.short_name}) cannot be appended due to 8 char limit.
    )


# We don't need to translate the external addresses, because the referenced accounts
# already have a mapping to a pycroft user
@reg.provides(pycroft_model.Address)
@reg.provides(pycroft_model.Room)
def translate_locations(ctx: Context, data: IntermediateData) -> List[PycroftBase]:
    objs = translate_switch(ctx, data)
    accesses: List[abe_model.Access] = ctx.query(abe_model.Access).all()

    errors = 0
    unpatched_ports = 0
    unpatched_rooms = 0

    for access in accesses:
        # null if access.switch_port is null -> it MAY be that we have a `switch`!
        switch_port = try_create_switch_port(access, data, ctx.logger)
        room = try_create_room(access, data, ctx.logger)
        objs.extend(x for x in [switch_port, room] if x)

        if room and not switch_port:
            if not access.switch:
                ctx.logger.warning(f"Access {access.id} has on switch!")
            ctx.logger.debug(f"Unpatched room {room.short_name}")
            unpatched_rooms += 1
            continue
        if not room and switch_port:
            ctx.logger.debug(f"Unpatched port {switch_port.switch.host.name}/{access.port}")
            unpatched_ports += 1
            continue
        if not room and not switch_port:
            ctx.logger.critical(f"Access {access.id} references neither room nor switch!")
            errors += 1
            continue

        assert access.switch and access.building
        objs.extend([room, switch_port, room.address])
        data.access_rooms[access.id] = room  # necessary for adding the account

        patch_port = try_create_patch_port(room, access, data, ctx.logger)
        if not access.switch:
            ctx.logger.warning(f"Access {access.id} has no switch!")
            continue

        patch_port.switch_port = switch_port
        objs.append(patch_port)

        objs.append(pycroft_model.RoomLogEntry(
            message=deferred_gettext("User imported from legacy database abe.").to_json(),
            room=room,
            author_id=ROOT_ID,
        ))

    ctx.logger.info(f"Got {unpatched_ports} unpatched ports"
                    if unpatched_ports else "Kudos, all ports are patched!")
    ctx.logger.info(f"Got {unpatched_rooms} unpatched rooms"
                    if unpatched_rooms else "Kudos, all rooms are patched!")

    _maybe_abort(errors, ctx.logger)
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

        maybe_passwd_arg = {}
        unix_acc = None
        if acc.ldap_entry:
            maybe_passwd_arg = {'passwd_hash': acc.ldap_entry.userpassword}
            unix_acc = pycroft_model.UnixAccount(
                home_directory=acc.ldap_entry.homedirectory,
                uid=acc.ldap_entry.uidnumber,
                gid=acc.ldap_entry.gidnumber,
            )
        else:
            ctx.logger.warning("User %s does not have an ldap_entry."
                               " Password and unix_account won't be set.",
                               acc.account)

        try:
            user = pycroft_model.User(
                login=chosen_login,
                room=room,
                name=acc.name,
                address=room.address,
                birthdate=acc.date_of_birth,  # TODO add birth date to model
                registered_at=acc.entry_date,
                email=maybe_fix_mail(props.mail, ctx.logger),
                **maybe_passwd_arg,
            )
        except pycroft_model.IllegalLoginError as e:
            ctx.logger.error("Account '%s' has invalid login!",
                             chosen_login)
            ctx.logger.debug(e.args)
            num_errors += 1
            continue

        finance_account = pycroft_model.Account(
            name=deferred_gettext(u"HSS:User {login}").format(login=chosen_login).to_json(),
            type='USER_ASSET',
        )
        user.account = finance_account
        user.unix_account = unix_acc

        data.users[acc.account] = user

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
