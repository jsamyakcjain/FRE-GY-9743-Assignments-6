"""Convention-driven factory adapted from the instructor template.

Swap axis1 is tenor or start-offset x tenor. FRA uses start-offset x end-offset,
with both offsets measured from value_date, or two explicit ISO dates.
"""

from typing import Any
from fixedincomelib.date import Date, TermOrDate, add_period
from fixedincomelib.market.data_conventions import (
    CompoundingMethod, DataConvention, DataConventionFRA,
    DataConventionRFRSwap, DataConventionOvernightIndexBasisSwap,
)
from fixedincomelib.product.product_interfaces import ProductBuilderRegistry
from fixedincomelib.product.linear_products import ProductFRA, ProductRFRSwap, ProductOvernightIndexBasisSwap
from fixedincomelib.product.utilities import PayOrReceive


class ProductFactory:
    @classmethod
    def create_product_from_data_convention(
        cls,
        value_date: Date,
        axis1: str,
        data_convention: DataConvention,
        values: float,
        **kwargs: Any,
    ):

        convention_obj: DataConvention = data_convention
        prod_type = convention_obj.type()
        func = ProductBuilderRegistry().get(prod_type)
        return func(value_date, axis1, convention_obj, values, **kwargs)

    @classmethod
    def create_rfr_swap(
        cls,
        value_date: Date,
        axis1: str,
        data_convention: DataConventionRFRSwap,
        values: float,
        **kwargs: Any,
    ) -> ProductRFRSwap:

        from fixedincomelib.date.basics import Period
        from fixedincomelib.market.basics import AccrualBasis, BusinessDayConvention, HolidayConvention

        def get(names, default=None):
            for n in names:
                if hasattr(data_convention, n):
                    v = getattr(data_convention, n)
                    return v() if callable(v) else v
            return default

        def conv(kind, v):
            return kind(v) if isinstance(v, str) else v

        bdc = conv(BusinessDayConvention, get(["payment_business_day_convention", "payment_business_day_convention_",
                                               "business_day_convention"]))
        holidays = conv(HolidayConvention, get(["payment_holiday_convention", "payment_holiday_convention_",
                                                "holiday_convention"]))

        start, end = cls._tokenize_axis1(axis1)
        if end is None:  # "1Y": spot-starting
            effective_date, termination = Date(value_date), start
        elif start.is_term():  # "3Mx1Y"
            effective_date, termination = add_period(value_date, start.get_term(), bdc, holidays), end
        else:  # explicit dates
            effective_date, termination = start.get_date(), TermOrDate(end.get_date())

        return ProductRFRSwap(
            effective_date,
            termination,
            conv(Period, get(["payment_offset", "pay_offset"])),
            get(["index_str", "on_index_str"]),
            values,
            PayOrReceive.from_string(kwargs.get("pay_or_rec", "receive")),
            kwargs.get("notional", 1e4),
            conv(Period, get(["accrual_period", "fixed_leg_accrual_period", "acc_period"])),
            conv(AccrualBasis, get(["acc_basis", "accrual_basis"])),
            conv(Period, get(["floating_leg_accrual_period", "floating_acc_period"])),
            bdc,
            holidays,
            kwargs.get("spread", 0.0),
            get(["compounding_method"], CompoundingMethod.COMPOUND),
        )

    @classmethod
    def create_overnight_index_basis_swap(
        cls,
        value_date: Date,
        axis1: str,
        data_convention: DataConventionOvernightIndexBasisSwap,
        values: float,
        **kwargs: Any,
    ) -> ProductOvernightIndexBasisSwap:

        from fixedincomelib.date.basics import Period
        from fixedincomelib.market.basics import AccrualBasis, BusinessDayConvention, HolidayConvention

        dc = data_convention

        def conv(kind, v):
            return kind(v) if isinstance(v, str) else v

        bdc = conv(BusinessDayConvention, dc.payment_business_day_convention_)
        holidays = conv(HolidayConvention, dc.payment_holiday_convention_)

        start, end = cls._tokenize_axis1(axis1)
        if end is None:  # "1Y": spot-starting
            effective_date, termination = Date(value_date), start
        elif start.is_term():  # "3Mx1Y"
            effective_date, termination = add_period(value_date, start.get_term(), bdc, holidays), end
        else:  # explicit dates
            effective_date, termination = start.get_date(), TermOrDate(end.get_date())

        return ProductOvernightIndexBasisSwap(
            effective_date,
            termination,
            conv(Period, dc.payment_offset),
            dc.index_1_str,
            dc.index_2_str,
            values,
            PayOrReceive.from_string(kwargs.get("pay_or_rec", "receive")),
            kwargs.get("notional", 1e4),
            conv(Period, dc.acc_period_1),
            conv(AccrualBasis, dc.acc_basis),
            conv(Period, dc.acc_period_2),
            bdc,
            holidays,
            dc.compounding_method,
        )

    @classmethod
    def create_fra(cls, value_date, axis1, data_convention, values, **kwargs):
        start, end = cls._tokenize_axis1(axis1)
        bdc = data_convention.business_day_convention
        holidays = data_convention.holiday_convention
        if start.is_term():
            effective_date = add_period(value_date, start.get_term(), bdc, holidays)
            termination_date = add_period(value_date, end.get_term(), bdc, holidays)
        else:
            effective_date = start.get_date()
            termination_date = end.get_date()
        return ProductFRA(
            effective_date, TermOrDate(termination_date), data_convention.index_str,
            values, PayOrReceive.from_string(kwargs.get("pay_or_rec", "receive")),
            kwargs.get("notional", 1e4), data_convention.acc_basis, bdc, holidays,
        )

    @staticmethod
    def _tokenize_axis1(axis1):
        tokens = axis1.strip().replace("X", "x").split("x")
        first = TermOrDate(tokens[0].strip())
        second = TermOrDate(tokens[1].strip()) if len(tokens) == 2 else None
        return first, second


ProductBuilderRegistry().register(DataConventionFRA.type(), ProductFactory.create_fra)
ProductBuilderRegistry().register(DataConventionRFRSwap.type(), ProductFactory.create_rfr_swap)
ProductBuilderRegistry().register(DataConventionOvernightIndexBasisSwap.type(),
                                  ProductFactory.create_overnight_index_basis_swap)