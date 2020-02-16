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
            message=f"Room imported from legacy database abe. Access-ID: {access.id}",
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


def uid_mapping(abe_uid: int) -> int:
    return abe_uid + 20000


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
        login_has_been_sanitized = False
        if chosen_login != acc.account:
            ctx.logger.warning("Renaming '%s' → '%s'", acc.account, chosen_login)
            login_has_been_sanitized = True

        maybe_passwd_arg = {}
        unix_acc = None
        homedir_exists = False
        if acc.ldap_entry:
            abe_homedir = acc.ldap_entry.homedirectory
            homedir_exists = bool(ctx.pycroft_session.query(pycroft_model.UnixAccount)
                                     .filter_by(home_directory=abe_homedir).one_or_none())
            if homedir_exists:
                ctx.logger.warning("Moving %(h)s to %(h)s-hss", {'h': abe_homedir})
                abe_homedir = f"{abe_homedir}-hss"

            maybe_passwd_arg = {'passwd_hash': acc.ldap_entry.userpassword}
            unix_acc = pycroft_model.UnixAccount(
                home_directory=abe_homedir,
                uid=uid_mapping(acc.ldap_entry.uidnumber),
                gid=acc.ldap_entry.gidnumber,
            )
        else:
            ctx.logger.warning("User %s does not have an ldap_entry."
                               " Password and unix_account won't be set.",
                               acc.account)

        user_exists = bool(ctx.pycroft_session
                                    .query(pycroft_model.User)
                                    .filter_by(login=chosen_login)
                                    .one_or_none())
        if user_exists:
            ctx.logger.warning("Renaming %(acc)s → %(acc)s-hss", {'acc': chosen_login})
            chosen_login = f"{chosen_login}-hss"

        if unix_acc and user_exists and not homedir_exists:
            ctx.logger.info("User %s kept original homedir %s!",
                            chosen_login, unix_acc.home_directory)
        elif not login_has_been_sanitized and unix_acc \
                and unix_acc.home_directory != f"/home/{chosen_login}":
            ctx.logger.info("User %s has unusualy homedir %s!",
                            chosen_login, unix_acc.home_directory)

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
        objs.append(pycroft_model.UserLogEntry(
            message=f"Imported from legacy database abe. Account: {acc.account!r}",
            user=user,
            author_id=ROOT_ID,
        ))

        # TODO (in a separate translation) add memberships -> What about (former) orgs?.

    # 2. People who _do_ have a pycroft mapping

    for acc in ctx.abe_session.query(abe_model.Account)\
            .filter(abe_model.Account.pycroft_login != None):
        # TODO add to „manual intervention“ report
        pycroft_user = ctx.pycroft_session.query(pycroft_model.User) \
            .filter_by(login=acc.pycroft_login).one_or_none()
        if not pycroft_user:
            ctx.logger.error("Account %s is claimed to correspond to pycroft user %s,"
                             " but the latter does not exist",
                             acc.account, acc.pycroft_login)
            num_errors += 1
            continue
        ctx.logger.debug("Associating pycroft user %s to account %s",
                         acc.pycroft_login, acc.account)

        data.users[acc.account] = pycroft_user

    # TODO warn on people with neither access nor pycroft mapping
    _maybe_abort(num_errors, ctx.logger)
    return objs


RE_BEITRAG = r"Mitgliedsbeitrag 20\d\d-\d\d"


@reg.provides(pycroft_model.BankAccount, pycroft_model.BankAccountActivity)
def translate_bank_statements(ctx: Context, data: IntermediateData) -> List[PycroftBase]:
    objs = []
    num_errors = 0
    hss_account = pycroft_model.Account(
        name="Hochschulstraße",
        type="BANK_ASSET",
        legacy=False,
    )
    bank_account = pycroft_model.BankAccount(
        name="HSS-Konto",
        bank="Ostsächsische Sparkasse Dresden",
        account_number="3120241937",
        routing_number="85050300",
        iban="DE40850503003120241937",
        bic="OSDDDE81XXX",
        fints_endpoint="https://banking-sn5.s-fints-pt-sn.de/fints30",
        account=hss_account,
    )
    objs.append(bank_account)

    dead_memberships_account = pycroft_model.Account(
        name="Mitgliedsbeiträge gelöschter Abe-Accounts",
        type="REVENUE",
    )
    objs.append(dead_memberships_account)

    for log in ctx.abe_session.query(abe_model.AccountStatementLog).all():
        assert isinstance(log, abe_model.AccountStatementLog)
        activity = pycroft_model.BankAccountActivity(
            bank_account=bank_account,
            amount=log.amount,
            reference=log.purpose,
            # `log.timestamp` probably resembles `valid_on`, but there's no other information
            # so `imported_at` and `posted_on` aren't exact, but “close enough”
            imported_at=log.timestamp,
            valid_on=log.timestamp.date(),
            posted_on=log.timestamp.date(),
            other_account_number="NO NUMBER GIVEN",
            other_routing_number="NO NUMBER GIVEN",
            other_name=log.payer,  # log.name is a heuristic for abe that's irrelevant here
            # the split is going to be added if we know a relationship to an account
            # split = relationship(Split, foreign_keys=(transaction_id, account_id),
        )
        objs.append(activity)
        if log.account:
            user = data.users.get(log.account_name)
            user_account = user.account
            if not user:
                ctx.logger.error("We have a transaction (id %d) to non-imported account '%s'",
                                 log.id, log.account_name)
                num_errors += 1
                continue

            transaction, user_split, bank_split = create_user_transaction(
                log, user_account, hss_account, activity
            )
            assert len(transaction.splits) == 2
            assert len({s.account for s in transaction.splits})

            objs.append(transaction)
            continue

        # account not set
        if log.name:
            account = data.deleted_finance_accounts.get(log.name)
            if not account:
                account = pycroft_model.Account(
                    name=f"Account of deleted HSS user {log.name}",
                    type="USER_ASSET",
                )
                data.deleted_finance_accounts[log.name] = account
                objs.append(account)
            transaction, former_user_split, bank_split = create_user_transaction(
                log, account, hss_account, activity
            )
            assert len(transaction.splits) == 2
            objs.append(transaction)

            balancing_transaction = pycroft_model.Transaction(
                author_id=ROOT_ID,
                description=f"Reconstructed membership fee of {log.name}",
                posted_at=log.timestamp,
                valid_on=log.timestamp.date(),
            )
            balancing_transaction.splits = [
                pycroft_model.Split(amount=log.amount, account=account),
                pycroft_model.Split(amount=-log.amount, account=dead_memberships_account)
            ]
            continue

        # neither account nor name set
        ctx.logger.warning("New unmatched transaction from statement log %d", log.id)

    _maybe_abort(num_errors, ctx.logger)
    return objs


def create_user_transaction(log, user_account, hss_account, activity):
    transaction = pycroft_model.Transaction(
        author_id=ROOT_ID,
        description=log.purpose,
        posted_at=log.timestamp,
        valid_on=log.timestamp.date(),
    )
    user_split = pycroft_model.Split(transaction=transaction, amount=-log.amount,
                                     account=user_account)
    bank_split = pycroft_model.Split(transaction=transaction, amount=log.amount,
                                     account=hss_account)
    activity.split = bank_split
    return transaction, user_split, bank_split


@reg.requires_function(translate_bank_statements)
@reg.provides(pycroft_model.Transaction, pycroft_model.Split, pycroft_model.BankAccountActivity)
def translate_fees(ctx: Context, data: IntermediateData) -> List[PycroftBase]:
    objs: List[pycroft_model.ModelBase] = []

    for fee_rel in ctx.abe_session.query(abe_model.AccountFeeRelation).all():
        assert isinstance(fee_rel, abe_model.AccountFeeRelation)
        is_membership_fee = fee_rel.fee.description.startswith("Mitgliedsbeitrag")

        if is_membership_fee:
            # TODO import fee and add membership info to intermediate data
            continue

        is_allowance = fee_rel.fee.description.startswith("Aufwandsentsch")
        if is_allowance:
            # TODO create a transaction member account <-> allowances account
            continue
        # TODO just import as a compensation member account <-> membership account

    # TODO warn on balance mismatch (abe-proclaimed vs actual)

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
