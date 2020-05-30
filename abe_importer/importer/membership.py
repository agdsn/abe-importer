from __future__ import annotations

from collections import Iterable
from dataclasses import dataclass
from datetime import datetime
from functools import total_ordering, reduce
from typing import List, Optional

from dateutil.relativedelta import relativedelta
from pycroft.helpers import interval

MEMBERSHIP_FEE_PATTERN = "Mitgliedsbeitrag %-%"


@total_ordering
@dataclass
class FeeMonth:
    year: int
    month: int

    @classmethod
    def from_desc(cls, desc: str) -> FeeMonth:
        assert desc.startswith("Mitglieds")
        # Mitgliedsbeitrag 2018-08
        _, isomonth = desc.split(' ')
        year, month = isomonth.split('-')
        return FeeMonth(year=int(year.strip()), month=int(month.strip()))

    @staticmethod
    def _is_valid_operand(other):
        return all(hasattr(other, x) for x in ["year", "month"])

    def __lt__(self, other):

        if not self._is_valid_operand(other):
            return False
        return self.year < other.year or self.year == other.year and self.month < other.month

    @property
    def beginning(self) -> datetime:
        return datetime(year=self.year, month=self.month, day=1)

    @property
    def next_beginning(self) -> datetime:
        """Return the datetime of the (first day of the) next month"""
        return self.beginning + relativedelta(months=1)

    def to_interval(self, max_month: FeeMonth = None) -> interval.Interval:
        return interval.closedopen(self.beginning,
                                   self.next_beginning if max_month is None or self < max_month
                                   else None)


def get_latest_month(descriptions: Iterable[str]) -> FeeMonth:
    def take_max(cur: FeeMonth, new: str):
        return max(cur, FeeMonth.from_desc(new))

    return reduce(take_max, descriptions, FeeMonth(0, 0))


def test_latest_month():
    descriptions = [
        "Mitgliedsbeitrag 2019-11",
        "Mitgliedsbeitrag 2020-01",
        "Mitgliedsbeitrag 2020-02",
        "Mitgliedsbeitrag 2020-03",
        "Mitgliedsbeitrag 2020-04",
    ]
    latest_month = get_latest_month(descriptions)

    assert latest_month == FeeMonth(year=2020, month=4)
    assert_membership_intervals(descriptions, interval.IntervalSet((
        interval.closedopen(datetime(2019, 11, 1), datetime(2019, 12, 1)),
        interval.closedopen(datetime(2020, 1, 1), datetime(2020, 5, 1)),
    )), latest_month=None)
    assert_membership_intervals(descriptions, interval.IntervalSet((
        interval.closedopen(datetime(2019, 11, 1), datetime(2019, 12, 1)),
        interval.closedopen(datetime(2020, 1, 1), None),
    )), latest_month=latest_month)


def assert_membership_intervals(descriptions: List[str],
                                expected_intervals: interval.IntervalSet,
                                latest_month: Optional[FeeMonth]):
    assert interval.IntervalSet(FeeMonth.from_desc(d).to_interval(latest_month)
                                for d in descriptions) \
           == expected_intervals
