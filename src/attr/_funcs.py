from __future__ import absolute_import, division, print_function

import copy

try:
    from typing import Any, Dict, Iterable, Optional, Union
except ImportError:
    Any = Dict = Iterable = Optional = Union = None

from ._compat import iteritems
from ._make import NOTHING, fields, _obj_setattr


def asdict(inst, recurse=True, filter=None, dict_factory=dict,
           retain_collection_types=False):
    """
    Return the ``attrs`` attribute values of *inst* as a dict.

    Optionally recurse into other ``attrs``-decorated classes.

    :param inst: Instance of an ``attrs``-decorated class.
    :param bool recurse: Recurse into classes that are also
        ``attrs``-decorated.
    :param callable filter: A callable whose return code deteremines whether an
        attribute or element is included (``True``) or dropped (``False``).  Is
        called with the :class:`attr.Attribute` as the first argument and the
        value as the second argument.
    :param callable dict_factory: A callable to produce dictionaries from.  For
        example, to produce ordered dictionaries instead of normal Python
        dictionaries, pass in ``collections.OrderedDict``.
    :param bool retain_collection_types: Do not convert to ``list`` when
        encountering an attribute which is type ``tuple`` or ``set``.  Only
        meaningful if ``recurse`` is ``True``.

    :rtype: return type of *dict_factory*

    ..  versionadded:: 16.0.0 *dict_factory*
    ..  versionadded:: 16.1.0 *retain_collection_types*
    """
    attrs = fields(inst.__class__)
    rv = dict_factory()
    for a in attrs:
        v = getattr(inst, a.name)
        if filter is not None and not filter(a, v):
            continue
        if recurse is True:
            if has(v.__class__):
                rv[a.name] = asdict(v, recurse=True, filter=filter,
                                    dict_factory=dict_factory)
            elif isinstance(v, (tuple, list, set)):
                cf = v.__class__ if retain_collection_types is True else list
                rv[a.name] = cf([
                    asdict(i, recurse=True, filter=filter,
                           dict_factory=dict_factory)
                    if has(i.__class__) else i
                    for i in v
                ])
            elif isinstance(v, dict):
                df = dict_factory
                rv[a.name] = df((
                    asdict(kk, dict_factory=df) if has(kk.__class__) else kk,
                    asdict(vv, dict_factory=df) if has(vv.__class__) else vv)
                    for kk, vv in iteritems(v))
            else:
                rv[a.name] = v
        else:
            rv[a.name] = v
    return rv


def fromdict(cls, dct, recurse=True, ignore_missing=False, rename=lambda a: a,
             union_discriminator=lambda v, t: Any):
    """
    Construct an instance of an ``attrs``-decorated class from a dict.

    Optionally recursively construct fields that are ``attrs``-decorated
    classes (requires type info).

    :param cls: An ``attrs``-decorated class.
    :param dct: A dictionary to construct in instance of *cls* from.
    :param bool recurse: Recursively construct fields that are also
        ``attrs``-decorated.
    :param bool ignore_missing: Keys not found in the dictionary are silently
           converted to None.
    :param callable rename: A callable that renames attribute names before
        looking them up in the dict.
    :param callable union_discrimator: A callable that accepts a value typed
        as a union and the union type and returns the appropriate type to
        deserialize the value as.

    :rtype: *cls*
    """


    def _is_optional(typ):
        if Union and issubclass(typ, Union) and not typ is Any:
            ret = False
            for i in range(len(typ.__union_params__)):
                if typ.__union_params__[i] is type(None):
                    ret = True
                    break
            return ret
        return False

    def _fromdict(cls, dct, context=[]):

        def deserialize_val(a, typ, name):
            try:
                if has(typ):
                    return _fromdict(typ, a, context + [name])
                elif _is_optional(typ):
                    if a is None:
                        return None
                    elif len(typ.__union_params__) > 2:
                        return deserialize_val(
                            a,
                            Union[tuple([t
                                         for t in typ.__union_params__
                                         if t is not type(None)])],
                            name
                        )
                    else:
                        return deserialize_val(a, typ.__union_params__[0], name)
                elif Dict and issubclass(typ, Dict):
                    if hasattr(typ, '__parameters__'):
                        key_gen = typ.__parameters__[0]
                        val_gen = typ.__parameters__[1]
                        return {deserialize_val(k, key_gen, name):
                                deserialize_val(v, val_gen, name + str(k))
                                for k, v in a.items()}
                    return a
                elif Iterable and issubclass(typ, Iterable) and typ is not str:
                    type_name = typ.__name__
                    if type_name == 'Tuple' or type_name == 'tuple':
                        mk = tuple
                    elif type_name == 'Set' or type_name == 'set':
                        mk = set
                    else:
                        mk = list
                    if hasattr(typ, '__parameters__'):
                        gen = typ.__parameters__[0]
                        return mk([deserialize_val(v, gen, name + '[]')
                                   for v in a])
                    else:
                        return mk(a)
                elif Union and issubclass(typ, Union):
                    actual_type = union_discriminator(a, typ)
                    return deserialize_val(a, actual_type, name)
                else:
                    return a
            except TypeError as e:
                raise TypeError(
                    "Unable to deserialize {val} as {typ} at "
                    "{context} because {reason}"
                    .format(val=a,
                            typ=typ,
                            context='.'.join(context) + '.' + key_name,
                            reason=str(e)))


        attrs = fields(cls)
        cons = {}
        for a in attrs:
            key_name = rename(a.name)
            if ignore_missing:
                val = dct.get(key_name)
            elif key_name in dct:
                val = dct[key_name]
            else:
                raise KeyError('.'.join(context) + '.' + key_name)

            if recurse and a.type is not None:
                cons[a.name] = deserialize_val(val, a.type, key_name)
            else:
                cons[a.name] = val
                
        return cls(**cons)


    return _fromdict(cls, dct)

def has(cls):
    """
    Check whether *cls* is a class with ``attrs`` attributes.

    :param type cls: Class to introspect.

    :raise TypeError: If *cls* is not a class.

    :rtype: :class:`bool`
    """
    return getattr(cls, "__attrs_attrs__", None) is not None


def assoc(inst, **changes):
    """
    Copy *inst* and apply *changes*.

    :param inst: Instance of a class with ``attrs`` attributes.

    :param changes: Keyword changes in the new copy.

    :return: A copy of inst with *changes* incorporated.
    """
    new = copy.copy(inst)
    attr_map = {a.name: a for a in new.__class__.__attrs_attrs__}
    for k, v in iteritems(changes):
        a = attr_map.get(k, NOTHING)
        if a is NOTHING:
            raise ValueError(
                "{k} is not an attrs attribute on {cl}."
                .format(k=k, cl=new.__class__)
            )
        _obj_setattr(new, k, v)
    return new
