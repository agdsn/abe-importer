from __future__ import annotations

from enum import Enum, auto
from typing import List

import ipaddr
from sqlalchemy import Column, Integer, String as sqlaString, Boolean, ForeignKey
from sqlalchemy.dialects import postgresql as pgtype
from sqlalchemy.ext.declarative import as_declarative, DeclarativeMeta
from sqlalchemy.orm import relationship, backref, foreign, remote
from sqlalchemy.types import Date, DateTime, TypeDecorator, Numeric


@as_declarative(metaclass=DeclarativeMeta)
class Base:
    def __repr__(self):
        return "{0}.{1}({2})".format(
            self.__module__, self.__class__.__name__,
            ", ".join("{0}={1!r}".format(key, getattr(self, key, "<unknown>"))
                      for key in self.__mapper__.columns.keys()))    


class String(TypeDecorator):
    @property
    def python_type(self):
        return str

    impl = sqlaString

    def process_literal_param(self, value, dialect):
        return value

    def process_bind_param(self, value, dialect):
        return value

    def process_result_value(self, value, dialect):
        return value.rstrip() if value else value

    def copy(self):
        return String(self.impl.length)


def id_pkey():
    return Column(Integer, primary_key=True)


class Building(Base):
    __tablename__ = 'imp_buildings'
    short_name = Column(String, primary_key=True)
    street = Column(String)
    number = Column(String)
    zip_code = Column(String)


class Access(Base):
    __tablename__ = 'imp_access'
    id = id_pkey()
    description = Column(String)
    building_shortname = Column('building', String)
    building: Building = relationship(
        Building,
        primaryjoin=foreign(building_shortname) == remote(Building.short_name),
        uselist=False
    )
    floor = Column(String)
    flat = Column(String)
    room = Column(String)
    switch = Column(String)
    port = Column(String)
    account = relationship('Account', primaryjoin='Account.access_id == Access.id')


class Account(Base):
    __tablename__ = 'imp_account'
    account = Column(String, primary_key=True)
    system_account = Column(Boolean)
    pycroft_login = Column(String)  # Provided by `imp_pycroft_account` mapping
    name = Column(String)
    entry_date = Column(Date)
    date_of_birth = Column(Date)
    access_id = Column('access', Integer, ForeignKey(Access.id))
    access = relationship(Access, primaryjoin=access_id == Access.id)
    use_cache = Column(Boolean, default=False)
    ldap_entry = relationship('LdapEntry', back_populates='account', uselist=False)

    booked_fees: List[AccountFeeRelation] = relationship(
        'AccountFeeRelation',
        order_by='AccountFeeRelation.fee_id'
    )


def map_uid(uid: int):
    return uid


class LdapEntry(Base):
    __tablename__ = 'imp_abe_ldap_matview'
    uid = Column(String, ForeignKey(Account.account), primary_key=True)
    account = relationship(Account, back_populates='ldap_entry', uselist=False)
    _uidnumber = Column('uidnumber', Integer)
    gidnumber = Column(Integer)
    userpassword = Column(String)
    homedirectory = Column(String)

    @property
    def uidnumber(self):
        return map_uid(self._uidnumber)

    
def account_fkey(**kw):
    return Column('account', String, ForeignKey(Account.account), **kw)


class Switch(Base):
    __tablename__ = 'imp_switch'
    name = Column(String, primary_key=True)
    building = Column(String, ForeignKey(Building.short_name))
    building_rel = relationship(Building, uselist=False)
    level = Column(Integer)
    room_number = Column(String)
    mgmt_ip_str = Column('mgmt_ip', String)

    @property
    def mgmt_ip(self):
        return ipaddr.IPAddress(self.mgmt_ip_str)


class Ip(Base):
    __tablename__ = 'ip'
    ip = Column(pgtype.INET, primary_key=True)
    account_name = account_fkey()
    account = relationship(Account, backref=backref("ips"))


class Mac(Base):
    __tablename__ = 'mac'
    id = id_pkey()
    account_name = Column('account', String, ForeignKey(Account.account))
    account = relationship(Account, backref=backref("macs"))
    mac = Column(pgtype.MACADDR)
    active = Column(Boolean, default=True)

    
class Subnet(Base):
    __tablename__ = 'subnet'
    id = id_pkey()
    description = Column(String)
    subnet = Column(pgtype.CIDR)
    gateway = Column(pgtype.INET)
    vlan_name = Column(String)
    vlan_id = Column(Integer)


class AccountProperty(Base):
    __tablename__ = 'account_property'
    account_name = account_fkey(primary_key=True)
    account = relationship(Account, backref=backref("property", uselist=False))
    active = Column(Boolean)
    fee_free = Column(Boolean)
    port_config = Column(String)
    firewall_config = Column(String)
    mail = Column(String)
    account_type = Column(String)
    

class AccountStatementLog(Base):
    __tablename__ = 'account_statement_log'
    id = id_pkey()
    timestamp = Column(DateTime)
    amount = Column(Numeric(2))
    purpose = Column(String)
    payer = Column(String)
    account_name = account_fkey()
    account = relationship(Account, backref=backref("statements"))
    name = Column(String)


class DisableEnum(Enum):
    Custom = auto()
    Payment = auto()
    Traffic = auto()
    DsgvoTransmission = auto()
    DsgvoDenial = auto()
    Moved = auto()

    _map = {
        "Custom Category": Custom,
        "No Membership Fee": Payment,
        "No Traffic remaining": Traffic,
        "DSGVO nicht zustellbar": DsgvoTransmission,
        "DSGVO Widerspruch": DsgvoDenial,
        "Ausgezogen": Moved,
    }

    @classmethod
    def from_description(cls, desc: str):
        return cls._map[desc.strip()]


class DisableCategory(Base):
    __tablename__ = 'disable_category'
    id = id_pkey()
    nat = Column(Boolean)
    disable_port = Column(Boolean)
    description = Column(String)

    @property
    def as_enum(self) -> DisableEnum:
        return DisableEnum.from_description(self.description)


class DisableRecord(Base):
    __tablename__ = 'disable_record'
    id = id_pkey()
    account_name = account_fkey()
    account = relationship(Account, backref=backref('disable_records'))
    info = Column(String)
    disable_category = Column(Integer, ForeignKey(DisableCategory.id))
    category: DisableCategory = relationship(DisableCategory)
    timestamp_start = Column(DateTime(timezone=False))
    timestamp_end = Column(DateTime(timezone=False))


class ExternalResidence(Base):
    __tablename__ = 'imp_external_residence'
    account_name = account_fkey(primary_key=True)
    account = relationship(Account, backref=backref('residence', uselist=False))
    street = Column(String)
    zip = Column(String)
    residence = Column(String)
    

class FeeInfo(Base):
    __tablename__ = 'fee_info'
    id = id_pkey()
    amount = Column(Numeric(2))
    description = Column(String)
    timestamp = Column(DateTime)


class AccountFeeRelation(Base):
    __tablename__ = 'account_fee_relation'
    fee_id = Column('fee', Integer, ForeignKey(FeeInfo.id), primary_key=True)
    fee = relationship(FeeInfo, lazy='joined')
    account_name = Column('account', String, ForeignKey(Account.account), primary_key=True)
    account = relationship(Account, back_populates='booked_fees')#backref=backref('booked_fees', order_by='fee_id'))

    def __str__(self):
        return f"Fee {self.fee.description!r} at {self.fee.timestamp.date()} "\
               f" ({self.fee.amount}€, #{self.fee_id})"


class IpLog(Base):
    __tablename__ = 'ip_log'
    id = id_pkey()
    account_name = account_fkey()
    account = relationship(Account, backref=backref('ip_logs'))
    ip_addr = Column('ip', pgtype.INET, ForeignKey(Ip.ip))
    ip = relationship(Ip, backref=backref('ip_logs'))
    timestamp = Column(DateTime)
    

class MailAlias(Base):
    __tablename__ = 'distinct_mail_alias'
    account_name = account_fkey(primary_key=True)
    account = relationship(Account, backref=backref("alias", uselist=False))
    mail = Column(String)
    

class PayCategoryOld(Base):
    __tablename__ = 'pay_category_old'
    id = id_pkey()
    description = Column(String)
    

class PayLogOld(Base):
    __tablename__ = 'pay_log_old'
    id = id_pkey()
    account_name = account_fkey()
    account = relationship(Account, backref=backref("old_pay_logs"))
    date = Column(Date)
    pay_category_id = Column('pay_category', Integer, ForeignKey(PayCategoryOld.id))
    pay_category = relationship(PayCategoryOld, backref=backref("pay_logs"))
    

class TrafficLog(Base):
    __tablename__ = 'traffic_log'
    id = id_pkey()
    account_name = account_fkey()
    account = relationship(Account, backref=backref('traffic_logs'))
    date = Column(Date)
    bytes_in = Column(pgtype.BIGINT)
    bytes_out = Column(pgtype.BIGINT)
    pkg_in = Column(pgtype.BIGINT)
    pkg_out = Column(pgtype.BIGINT)
    

class TrafficQuota(Base):
    __tablename__ = 'traffic_quota'
    id = id_pkey()
    daily_credit = Column(pgtype.BIGINT)
    max_credit = Column(pgtype.BIGINT)
    description = Column(String)


# update_notice probably not relevant
class Rights(Base):
    __tablename__ = 'imp_rights'
    account_name = account_fkey(primary_key=True)
    account = relationship(Account, backref=backref('rights'))
    rights = Column(Integer)
    mgmt = Column(Boolean)
    finances = Column(Boolean)
    administration = Column(Boolean)
