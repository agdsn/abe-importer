import ipaddress
from dataclasses import dataclass, field
from datetime import datetime
from functools import cached_property
from logging import Logger
from typing import Dict, Callable, List, Any

from pycroft.model import _all as pycroft_model
from sqlalchemy import func
from sqlalchemy.orm import Session, Query

from .tools import TranslationRegistry
from .. import model as abe_model


@dataclass
class Context:
    abe_session: Session
    pycroft_session: Session
    logger: Logger
    now: datetime = field(init=False)

    def __post_init__(self):
        self.now = self.pycroft_session.query(func.current_timestamp()).scalar()

    def query(self, *entities: Any, **kwargs: Any) -> Query:
        return self.abe_session.query(*entities, **kwargs)

    @cached_property
    def config(self) -> pycroft_model.Config:
        return self.pycroft_session.query(pycroft_model.Config).one()


def dict_field():
    return field(default_factory=lambda: {})


@dataclass
class IntermediateData:
    hss_site: pycroft_model.Site = None

    # shortname → Building
    buildings: Dict[str, pycroft_model.Building] = dict_field()

    # An access results in a room
    access_rooms: Dict[int, pycroft_model.Room] = dict_field()
    account_external_address: Dict[str, pycroft_model.Address] = dict_field()

    # switch_name → Switch
    switches: Dict[str, pycroft_model.Switch] = dict_field()

    # account-name → User
    users: Dict[str, pycroft_model.User] = dict_field()

    both_users: Dict[abe_model.Account, pycroft_model.User] = dict_field()

    # account_statement_log.name → Account
    deleted_finance_accounts: Dict[str, pycroft_model.Account] = dict_field()

    # account-name → month of membership
    membership_months: Dict[str, List[datetime]] = dict_field()

    # IPv4Network → Subnet
    subnets: Dict[ipaddress.IPv4Network, pycroft_model.Subnet] = dict_field()


reg: TranslationRegistry[
    Callable[[Context, IntermediateData], List[pycroft_model.ModelBase]],
    pycroft_model.ModelBase
] \
    = TranslationRegistry()
