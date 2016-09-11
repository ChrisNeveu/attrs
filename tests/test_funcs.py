"""
Tests for `attr._funcs`.
"""

from __future__ import absolute_import, division, print_function

from collections import OrderedDict, Sequence, Mapping

try:
    from typing import Any, Dict, List, Optional, Set, Union
except ImportError:
    Any = Dict = List = Optional = Set = Union = None

import pytest

from hypothesis import assume, given, strategies as st

from .utils import simple_classes, nested_classes

from attr._funcs import (
    asdict,
    assoc,
    astuple,
    fromdict,
    has,
)
from attr._make import (
    attr,
    attributes,
    fields,
)
from attr.exceptions import AttrsAttributeNotFoundError

MAPPING_TYPES = (dict, OrderedDict)
SEQUENCE_TYPES = (list, tuple)


class TestAsDict(object):
    """
    Tests for `asdict`.
    """
    @given(st.sampled_from(MAPPING_TYPES))
    def test_shallow(self, C, dict_factory):
        """
        Shallow asdict returns correct dict.
        """
        assert {
            "x": 1,
            "y": 2,
        } == asdict(C(x=1, y=2), False, dict_factory=dict_factory)

    @given(st.sampled_from(MAPPING_TYPES))
    def test_recurse(self, C, dict_class):
        """
        Deep asdict returns correct dict.
        """
        assert {
            "x": {"x": 1, "y": 2},
            "y": {"x": 3, "y": 4},
        } == asdict(C(
            C(1, 2),
            C(3, 4),
        ), dict_factory=dict_class)

    @given(nested_classes, st.sampled_from(MAPPING_TYPES))
    def test_recurse_property(self, cls, dict_class):
        """
        Property tests for recursive asdict.
        """
        obj = cls()
        obj_dict = asdict(obj, dict_factory=dict_class)

        def assert_proper_dict_class(obj, obj_dict):
            assert isinstance(obj_dict, dict_class)
            for field in fields(obj.__class__):
                field_val = getattr(obj, field.name)
                if has(field_val.__class__):
                    # This field holds a class, recurse the assertions.
                    assert_proper_dict_class(field_val, obj_dict[field.name])
                elif isinstance(field_val, Sequence):
                    dict_val = obj_dict[field.name]
                    for item, item_dict in zip(field_val, dict_val):
                        if has(item.__class__):
                            assert_proper_dict_class(item, item_dict)
                elif isinstance(field_val, Mapping):
                    # This field holds a dictionary.
                    assert isinstance(obj_dict[field.name], dict_class)
                    for key, val in field_val.items():
                        if has(val.__class__):
                            assert_proper_dict_class(val,
                                                     obj_dict[field.name][key])

        assert_proper_dict_class(obj, obj_dict)

    @given(st.sampled_from(MAPPING_TYPES))
    def test_filter(self, C, dict_factory):
        """
        Attributes that are supposed to be skipped are skipped.
        """
        assert {
            "x": {"x": 1},
        } == asdict(C(
            C(1, 2),
            C(3, 4),
        ), filter=lambda a, v: a.name != "y", dict_factory=dict_factory)

    @given(container=st.sampled_from(SEQUENCE_TYPES))
    def test_lists_tuples(self, container, C):
        """
        If recurse is True, also recurse into lists.
        """
        assert {
            "x": 1,
            "y": [{"x": 2, "y": 3}, {"x": 4, "y": 5}, "a"],
        } == asdict(C(1, container([C(2, 3), C(4, 5), "a"])))

    @given(container=st.sampled_from(SEQUENCE_TYPES))
    def test_lists_tuples_retain_type(self, container, C):
        """
        If recurse and retain_collection_types are True, also recurse
        into lists and do not convert them into list.
        """
        assert {
            "x": 1,
            "y": container([{"x": 2, "y": 3}, {"x": 4, "y": 5}, "a"]),
        } == asdict(C(1, container([C(2, 3), C(4, 5), "a"])),
                    retain_collection_types=True)

    @given(st.sampled_from(MAPPING_TYPES))
    def test_dicts(self, C, dict_factory):
        """
        If recurse is True, also recurse into dicts.
        """
        res = asdict(C(1, {"a": C(4, 5)}), dict_factory=dict_factory)
        assert {
            "x": 1,
            "y": {"a": {"x": 4, "y": 5}},
        } == res
        assert isinstance(res, dict_factory)

    @given(simple_classes(), st.sampled_from(MAPPING_TYPES))
    def test_roundtrip(self, cls, dict_class):
        """
        Test dumping to dicts and back for Hypothesis-generated classes.
        """
        instance = cls()
        dict_instance = asdict(instance, dict_factory=dict_class)

        assert isinstance(dict_instance, dict_class)

        roundtrip_instance = cls(**dict_instance)

        assert instance == roundtrip_instance

    @given(simple_classes())
    def test_asdict_preserve_order(self, cls):
        """
        Field order should be preserved when dumping to OrderedDicts.
        """
        instance = cls()
        dict_instance = asdict(instance, dict_factory=OrderedDict)

        assert [a.name for a in fields(cls)] == list(dict_instance.keys())


class TestAsTuple(object):
    """
    Tests for `astuple`.
    """
    @given(st.sampled_from(SEQUENCE_TYPES))
    def test_shallow(self, C, tuple_factory):
        """
        Shallow astuple returns correct dict.
        """
        assert (tuple_factory([1, 2]) ==
                astuple(C(x=1, y=2), False, tuple_factory=tuple_factory))

    @given(st.sampled_from(SEQUENCE_TYPES))
    def test_recurse(self, C, tuple_factory):
        """
        Deep astuple returns correct tuple.
        """
        assert (tuple_factory([tuple_factory([1, 2]),
                              tuple_factory([3, 4])])
                == astuple(C(
                            C(1, 2),
                            C(3, 4),
                            ),
                           tuple_factory=tuple_factory))

    @given(nested_classes, st.sampled_from(SEQUENCE_TYPES))
    def test_recurse_property(self, cls, tuple_class):
        """
        Property tests for recursive astuple.
        """
        obj = cls()
        obj_tuple = astuple(obj, tuple_factory=tuple_class)

        def assert_proper_tuple_class(obj, obj_tuple):
            assert isinstance(obj_tuple, tuple_class)
            for index, field in enumerate(fields(obj.__class__)):
                field_val = getattr(obj, field.name)
                if has(field_val.__class__):
                    # This field holds a class, recurse the assertions.
                    assert_proper_tuple_class(field_val, obj_tuple[index])

        assert_proper_tuple_class(obj, obj_tuple)

    @given(nested_classes, st.sampled_from(SEQUENCE_TYPES))
    def test_recurse_retain(self, cls, tuple_class):
        """
        Property tests for asserting collection types are retained.
        """
        obj = cls()
        obj_tuple = astuple(obj, tuple_factory=tuple_class,
                            retain_collection_types=True)

        def assert_proper_col_class(obj, obj_tuple):
            # Iterate over all attributes, and if they are lists or mappings
            # in the original, assert they are the same class in the dumped.
            for index, field in enumerate(fields(obj.__class__)):
                field_val = getattr(obj, field.name)
                if has(field_val.__class__):
                    # This field holds a class, recurse the assertions.
                    assert_proper_col_class(field_val, obj_tuple[index])
                elif isinstance(field_val, (list, tuple)):
                    # This field holds a sequence of something.
                    assert type(field_val) is type(obj_tuple[index])  # noqa: E721
                    for obj_e, obj_tuple_e in zip(field_val, obj_tuple[index]):
                        if has(obj_e.__class__):
                            assert_proper_col_class(obj_e, obj_tuple_e)
                elif isinstance(field_val, dict):
                    orig = field_val
                    tupled = obj_tuple[index]
                    assert type(orig) is type(tupled)  # noqa: E721
                    for obj_e, obj_tuple_e in zip(orig.items(),
                                                  tupled.items()):
                        if has(obj_e[0].__class__):  # Dict key
                            assert_proper_col_class(obj_e[0], obj_tuple_e[0])
                        if has(obj_e[1].__class__):  # Dict value
                            assert_proper_col_class(obj_e[1], obj_tuple_e[1])

        assert_proper_col_class(obj, obj_tuple)

    @given(st.sampled_from(SEQUENCE_TYPES))
    def test_filter(self, C, tuple_factory):
        """
        Attributes that are supposed to be skipped are skipped.
        """
        assert tuple_factory([tuple_factory([1, ]), ]) == astuple(C(
            C(1, 2),
            C(3, 4),
        ), filter=lambda a, v: a.name != "y", tuple_factory=tuple_factory)

    @given(container=st.sampled_from(SEQUENCE_TYPES))
    def test_lists_tuples(self, container, C):
        """
        If recurse is True, also recurse into lists.
        """
        assert ((1, [(2, 3), (4, 5), "a"])
                == astuple(C(1, container([C(2, 3), C(4, 5), "a"])))
                )

    @given(st.sampled_from(SEQUENCE_TYPES))
    def test_dicts(self, C, tuple_factory):
        """
        If recurse is True, also recurse into dicts.
        """
        res = astuple(C(1, {"a": C(4, 5)}), tuple_factory=tuple_factory)
        assert tuple_factory([1, {"a": tuple_factory([4, 5])}]) == res
        assert isinstance(res, tuple_factory)

    @given(container=st.sampled_from(SEQUENCE_TYPES))
    def test_lists_tuples_retain_type(self, container, C):
        """
        If recurse and retain_collection_types are True, also recurse
        into lists and do not convert them into list.
        """
        assert (
            (1, container([(2, 3), (4, 5), "a"]))
            == astuple(C(1, container([C(2, 3), C(4, 5), "a"])),
                       retain_collection_types=True))

    @given(container=st.sampled_from(MAPPING_TYPES))
    def test_dicts_retain_type(self, container, C):
        """
        If recurse and retain_collection_types are True, also recurse
        into lists and do not convert them into list.
        """
        assert (
            (1, container({"a": (4, 5)}))
            == astuple(C(1, container({"a": C(4, 5)})),
                       retain_collection_types=True))

    @given(simple_classes(), st.sampled_from(SEQUENCE_TYPES))
    def test_roundtrip(self, cls, tuple_class):
        """
        Test dumping to tuple and back for Hypothesis-generated classes.
        """
        instance = cls()
        tuple_instance = astuple(instance, tuple_factory=tuple_class)

        assert isinstance(tuple_instance, tuple_class)

        roundtrip_instance = cls(*tuple_instance)

        assert instance == roundtrip_instance


class TestFromDict(object):
    """
    Tests for `asdict`.
    """
    def test_shallow(self, C):
        """
        Shallow fromdict returns correct class.
        """
        assert C(
            x=1,
            y=2
        ) == fromdict(C, {"x": 1, "y": 2}, False)

    def test_recurse(self, C):
        """
        Deep fromdict returns correct class.
        """

        @attributes
        class D(object):
            x = attr(type=C)
            y = attr(type=C)

        assert D(
            C(1, 2),
            C(3, 4),
        ) == fromdict(D, {
            "x": {"x": 1, "y": 2},
            "y": {"x": 3, "y": 4},
        })

    def test_shallow_iterables(self):
        """
        Shallow fromdict with iterables returns correct class.
        """
        if not List:
            assert True
            return

        @attributes
        class C(object):
            x = attr(type=list)
            y = attr(type=set)

        assert C(
            [{"x": 1, "y": 2}],
            set([3, 4]),
        ) == fromdict(C, {
            "x": [{"x": 1, "y": 2}],
            "y": [3, 4],
        })

    def test_recurse_iterables(self, C):
        """
        Deep fromdict with iterables returns correct class.
        """
        if not List:
            assert True
            return

        @attributes
        class D(object):
            x = attr(type=List[C])
            y = attr(type=Set[C])

        assert D(
            [C(1, 2)],
            set([C(3, 4)]),
        ) == fromdict(D, {
            "x": [{"x": 1, "y": 2}],
            "y": [{"x": 3, "y": 4}],
        })

    def test_shallow_optional(self):
        """
        Shallow fromdict with optionals returns correct class.
        """
        if not Optional:
            assert True
            return

        @attributes
        class C(object):
            x = attr(type=Optional[int])
            y = attr(type=Optional[str])

        assert C(
            'foo',
            None,
        ) == fromdict(C, {
            "x": 'foo',
            "y": None,
        })

    def test_recurse_optional(self, C):
        """
        Deep fromdict with optionals returns correct class.
        """
        if not List:
            assert True
            return

        @attributes
        class D(object):
            x = attr(type=Optional[C])
            y = attr(type=Optional[C])

        assert D(
            C(1, 2),
            None,
        ) == fromdict(D, {
            "x": {"x": 1, "y": 2},
            "y": None,
        })

    def test_shallow_dict(self):
        """
        Shallow fromdict with optionals returns correct class.
        """
        if not Dict:
            assert True
            return

        @attributes
        class C(object):
            x = attr(type=Dict[str, int])
            y = attr(type=dict)

        assert C(
            {"x": 1, "y": 2},
            {"x": 3, "y": 4},
        ) == fromdict(C, {
            "x": {"x": 1, "y": 2},
            "y": {"x": 3, "y": 4},
        })

    def test_recurse_dict(self, C):
        """
        Deep fromdict with optionals returns correct class.
        """
        if not Dict:
            assert True
            return

        @attributes
        class D(object):
            x = attr(type=Dict[str, C])

        assert D(
            {"x": C(1, 2), "y": C(3, 4)},
        ) == fromdict(D, {
            "x": {"x": {"x": 1, "y": 2}, "y": {"x": 3, "y": 4}},
        })

    def test_shallow_union(self):
        """
        Shallow fromdict with unions returns correct class.
        """
        if not Union:
            assert True
            return

        @attributes
        class C(object):
            x = attr(type=Union[str, int])
            y = attr(type=Union[str, int])

        assert C(
            "one",
            1,
        ) == fromdict(C, {
            "x": "one",
            "y": 1,
        })

    def test_recurse_union(self, C):
        """
        Deep fromdict with unions returns correct class.
        """
        if not Union:
            assert True
            return

        @attributes
        class B(object):
            x = attr()
            y = attr()

        @attributes
        class D(object):
            x = attr(type=Union[B, C])
            y = attr(type=Union[B, C])

        def by_type(dct, t):
            if dct["type"] == "B":
                return B
            else:
                return C

        assert D(
            B(1, 2),
            C(3, 4),
        ) == fromdict(D, {
            "x": {"type": "B", "x": 1, "y": 2},
            "y": {"type": "C", "x": 3, "y": 4},
        }, union_discriminator=by_type)


class TestHas(object):
    """
    Tests for `has`.
    """
    def test_positive(self, C):
        """
        Returns `True` on decorated classes.
        """
        assert has(C)

    def test_positive_empty(self):
        """
        Returns `True` on decorated classes even if there are no attributes.
        """
        @attributes
        class D(object):
            pass

        assert has(D)

    def test_negative(self):
        """
        Returns `False` on non-decorated classes.
        """
        assert not has(object)


class TestAssoc(object):
    """
    Tests for `assoc`.
    """
    @given(slots=st.booleans(), frozen=st.booleans())
    def test_empty(self, slots, frozen):
        """
        Empty classes without changes get copied.
        """
        @attributes(slots=slots, frozen=frozen)
        class C(object):
            pass

        i1 = C()
        i2 = assoc(i1)

        assert i1 is not i2
        assert i1 == i2

    @given(simple_classes())
    def test_no_changes(self, C):
        """
        No changes means a verbatim copy.
        """
        i1 = C()
        i2 = assoc(i1)

        assert i1 is not i2
        assert i1 == i2

    @given(simple_classes(), st.integers())
    def test_change(self, C, val):
        """
        Changes work.
        """
        # Take the first attribute, and change it.
        assume(fields(C))  # Skip classes with no attributes.
        original = C()
        attribute = fields(C)[0]
        changed = assoc(original, **{attribute.name: val})
        assert getattr(changed, attribute.name) == val

    @given(simple_classes())
    def test_unknown(self, C):
        """
        Wanting to change an unknown attribute raises a ValueError.
        """
        # No generated class will have a four letter attribute.
        with pytest.raises(AttrsAttributeNotFoundError) as e:
            assoc(C(), aaaa=2)
        assert (
            "aaaa is not an attrs attribute on {cls!r}.".format(cls=C),
        ) == e.value.args

    def test_frozen(self):
        """
        Works on frozen classes.
        """
        @attributes(frozen=True)
        class C(object):
            x = attr()
            y = attr()

        assert C(3, 2) == assoc(C(1, 2), x=3)
