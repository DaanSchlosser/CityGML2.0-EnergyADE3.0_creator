"""Generic xsdata object construction from dictionaries.

Provides a schema-agnostic way to build xsdata-generated dataclasses from
nested dicts and to attach children to parents via field introspection.
No feature-type-specific code lives here; all behaviour is derived from
the xsdata bindings (which are generated from the XSD).
"""

from __future__ import annotations

import dataclasses
import enum
import types
import typing
import warnings
from collections.abc import Iterator, Mapping
from decimal import Decimal
from functools import lru_cache
from typing import Any, Union

from xsdata.models.datatype import XmlDate, XmlDateTime, XmlDuration, XmlPeriod, XmlTime

from .namespaces import NS_PREFIX_MAP, iter_binding_classes

# ---------------------------------------------------------------------------
# Class registry: map "prefix:ElementName" → xsdata class
# ---------------------------------------------------------------------------


@lru_cache(maxsize=1)
def _build_class_registry() -> dict[str, type]:
    """Build ``{"prefix:ElementName": cls}`` from every xsdata element class.

    Only element classes (``Meta.namespace`` set) are registered; type-only
    classes (``Meta.target_namespace`` without ``namespace``) are skipped
    because they cannot appear as the root of an XML element and so are
    never referenced by a user's ``"prefix:Name"`` type string.

    The ``dir(bindings)`` walk itself happens in
    :func:`citygml_energy.namespaces.iter_binding_classes`; this function
    only filters and keys its output. Unregistered URIs are collected and
    surfaced as a warning so a schema regeneration that introduced a new
    namespace fails loudly instead of silently dropping element types.
    """
    registry: dict[str, type] = {}
    unknown_namespaces: set[str] = set()
    for info in iter_binding_classes():
        if not info.is_element:
            continue
        prefix = NS_PREFIX_MAP.get(info.namespace)
        if prefix is None:
            unknown_namespaces.add(info.namespace)
            continue
        key = f"{prefix}:{info.xml_name}"
        # First registered class wins (stable iteration order).
        registry.setdefault(key, info.cls)

    if unknown_namespaces:
        warnings.warn(
            "xsdata bindings contain element classes in namespaces that are "
            "not registered in citygml_energy.namespaces.NSMAP; those classes "
            "cannot be resolved from JSON input. Add a prefix for: "
            + ", ".join(sorted(unknown_namespaces)),
            stacklevel=2,
        )

    return registry


def resolve_class(type_string: str) -> type:
    """Resolve ``"bldg:Building"`` to its xsdata element class.

    Raises :class:`ValueError` with a helpful message when the type string
    is not found in the registry.
    """
    registry = _build_class_registry()
    cls = registry.get(type_string)
    if cls is None:
        raise ValueError(
            f"Unknown type {type_string!r}. "
            f"Available types ({len(registry)}): " + ", ".join(sorted(registry)[:30]) + " ..."
        )
    return cls


def list_available_types() -> list[str]:
    """Return all registered ``prefix:ElementName`` strings, sorted."""
    return sorted(_build_class_registry())


# ---------------------------------------------------------------------------
# Field introspection
# ---------------------------------------------------------------------------


@dataclasses.dataclass(frozen=True, slots=True)
class FieldInfo:
    """Resolved metadata for a single dataclass field."""

    name: str  # Python attribute name
    inner_type: type  # unwrapped type (no Optional/list)
    is_list: bool
    xml_name: str | None  # from xsdata metadata["name"]
    is_attribute: bool  # XML attribute (vs element)
    namespace: str | None  # from xsdata metadata["namespace"]


@lru_cache(maxsize=1024)
def get_fields(cls: type) -> dict[str, FieldInfo]:
    """Field info for *cls*, keyed by **Python** field name.

    Public entry point for generic introspection of xsdata dataclasses.
    Non-dataclass inputs return an empty dict so callers can use the result
    unconditionally.
    """
    if not dataclasses.is_dataclass(cls):
        return {}
    hints = typing.get_type_hints(cls)
    result: dict[str, FieldInfo] = {}
    for f in dataclasses.fields(cls):
        hint = hints.get(f.name)
        if hint is None:
            continue
        is_list, inner = _unwrap_hint(hint)
        meta: Mapping[str, Any] = f.metadata or {}
        xml_name = meta.get("name")
        is_attr = meta.get("type") == "Attribute"
        result[f.name] = FieldInfo(
            name=f.name,
            inner_type=inner,
            is_list=is_list,
            xml_name=xml_name,
            is_attribute=is_attr,
            namespace=meta.get("namespace"),
        )
    return result


@lru_cache(maxsize=1024)
def _get_xml_name_map(cls: type) -> dict[str, FieldInfo]:
    """Field info for *cls*, keyed by **XML element/attribute name**."""
    return {info.xml_name: info for info in get_fields(cls).values() if info.xml_name is not None}


def _unwrap_hint(hint: Any) -> tuple[bool, type[Any]]:
    """Unwrap ``list[X]``, ``X | None``, etc. to ``(is_list, inner_type)``."""
    origin = getattr(hint, "__origin__", None)
    args = getattr(hint, "__args__", ())

    # list[X]
    if origin is list:
        if args:
            _, inner = _unwrap_hint(args[0])
            return True, inner
        return True, object

    # Union / X | None  (Python 3.10+ uses types.UnionType)
    if origin is Union or isinstance(hint, types.UnionType):
        non_none = [a for a in args if a is not type(None)]
        if non_none:
            return _unwrap_hint(non_none[0])

    if isinstance(hint, type):
        return False, hint

    return False, object


def _resolve_field(cls: type, key: str) -> FieldInfo | None:
    """Find a field on *cls* by Python name or XML name."""
    info = get_fields(cls).get(key)
    if info is not None:
        return info
    return _get_xml_name_map(cls).get(key)


# ---------------------------------------------------------------------------
# Smart coercion: JSON leaf values → xsdata types
# ---------------------------------------------------------------------------


def _coerce(target: type, raw: Any) -> Any:
    """Coerce a raw JSON value to *target* xsdata type."""
    if raw is None:
        return None

    # bool is a subclass of int, so check it before the isinstance fast-path
    # to make sure True/False are not accepted where an int or float is expected.
    if target is bool:
        if isinstance(raw, str):
            return raw.lower() in ("true", "1", "yes")
        return bool(raw)
    if target in (int, float, Decimal) and isinstance(raw, bool):
        raise TypeError(
            f"Cannot coerce bool {raw!r} to {target.__name__}: "
            f"refusing implicit bool→numeric conversion"
        )

    if isinstance(raw, target):
        return raw

    # --- Enums (xsdata generates these for XSD enumerations) ---
    if isinstance(target, type) and issubclass(target, enum.Enum):
        return _coerce_enum(target, raw)

    # --- xsdata date/time types from strings ---
    if target is XmlPeriod and isinstance(raw, (str, int)) and not isinstance(raw, bool):
        return XmlPeriod(str(raw))
    if target is XmlDate and isinstance(raw, str):
        return XmlDate.from_string(raw)
    if target is XmlDateTime and isinstance(raw, str):
        return XmlDateTime.from_string(raw)
    if target is XmlTime and isinstance(raw, str):
        return XmlTime.from_string(raw)
    if target is XmlDuration and isinstance(raw, str):
        return XmlDuration(raw)

    # --- Primitives ---
    # Reject containers explicitly: ``str({"a": 1})`` would otherwise produce
    # ``"{'a': 1}"`` and silently emit nonsense XML content.
    if target is str:
        if isinstance(raw, (dict, list)):
            raise TypeError(f"Cannot coerce {type(raw).__name__} to str: expected a scalar value")
        return str(raw)
    if target is float:
        return float(raw)
    if target is int:
        return int(raw)
    # xsd:decimal maps to Decimal (e.g. gml:TimeIntervalLengthType.value).
    # Route through str so JSON floats don't carry binary-FP noise into the
    # exact-decimal type.
    if target is Decimal and isinstance(raw, (int, float, str)):
        return Decimal(str(raw))

    # --- Dict → dataclass (recursive) ---
    if isinstance(raw, dict) and dataclasses.is_dataclass(target):
        return build_from_dict(target, raw)

    # --- Scalar → dataclass with a 'value' field ---
    #     Handles CodeType("x"), Name("x"), BdgIsProtected(true), etc.
    if not isinstance(raw, (dict, list)) and dataclasses.is_dataclass(target):
        return _scalar_to_dataclass(target, raw)

    # --- list[float] for MeasureListType.value (tokens field) ---
    if target is list and isinstance(raw, list):
        return raw

    # Refuse to silently pass through values whose shape doesn't match the
    # declared field type. This surfaces JSON typos at build time instead
    # of producing malformed XML at serialization time.
    target_name = getattr(target, "__name__", repr(target))
    raise TypeError(
        f"Cannot coerce {type(raw).__name__} {raw!r} to {target_name}: no conversion rule applies"
    )


def _coerce_enum(cls: type[enum.Enum], raw: Any) -> enum.Enum:
    """Coerce *raw* to a member of the xsdata-generated ``Enum`` *cls*.

    Accepts the enum's wire value (``XmlEnumValue``), its Python member name,
    or the raw underlying value. Raises ``ValueError`` listing valid options
    when no match is found, so JSON typos surface with actionable detail.
    """
    if isinstance(raw, cls):
        return raw
    # Match by value (the XML token, e.g. "averageInSucceedingInterval").
    for member in cls:
        if member.value == raw:
            return member
    # Fall back to member name (e.g. "AVERAGE_IN_SUCCEEDING_INTERVAL").
    if isinstance(raw, str) and raw in cls.__members__:
        return cls[raw]
    valid = ", ".join(repr(m.value) for m in cls)
    raise ValueError(f"Cannot coerce {raw!r} to {cls.__name__}: expected one of {valid}")


def _scalar_to_dataclass(cls: type, scalar: Any) -> Any:
    """Wrap a scalar in a dataclass via its ``value`` field.

    Works for ``CodeType("x")``, ``Name("text")``,
    ``BdgIsProtected(True)``, ``BdgOwnerName("name")``, etc.
    """
    fields = get_fields(cls)
    value_info = fields.get("value")
    if value_info is None:
        raise TypeError(
            f"Cannot coerce {type(scalar).__name__} {scalar!r} to "
            f"{cls.__name__}: class has no 'value' field"
        )
    coerced = _coerce(value_info.inner_type, scalar)
    return cls(value=coerced)


# ---------------------------------------------------------------------------
# Generic recursive builder
# ---------------------------------------------------------------------------

# Keys that are input-format meta, not xsdata field names.
_META_KEYS = frozenset({"type", "parent", "parent_field"})


def build_from_dict(cls: type, data: dict[str, Any]) -> Any:
    """Recursively build an xsdata dataclass from a dict.

    Keys in *data* can be either Python field names (``year_of_construction``)
    or XML element/attribute names (``yearOfConstruction``).  Leaf values are
    coerced to the field's declared type automatically.
    """
    if not dataclasses.is_dataclass(cls):
        raise TypeError(f"{cls.__name__} is not a dataclass")

    fields_map = get_fields(cls)
    kwargs: dict[str, Any] = {}

    for key, raw_value in data.items():
        if key in _META_KEYS:
            continue

        info = _resolve_field(cls, key)
        if info is None:
            available = sorted(fields_map.keys())
            raise ValueError(
                f"Unknown field {key!r} on {cls.__name__}. "
                f"Available fields: {', '.join(available[:30])}"
            )

        try:
            if info.is_list:
                items = raw_value if isinstance(raw_value, list) else [raw_value]
                kwargs[info.name] = [_coerce(info.inner_type, item) for item in items]
            else:
                kwargs[info.name] = _coerce(info.inner_type, raw_value)
        except (TypeError, ValueError) as exc:
            # Re-raise with the offending field name prepended so upstream
            # InputFileError messages stay actionable ("pv_panel_1.installed_power:
            # ..." instead of just "could not convert string to float").
            raise type(exc)(f"field {key!r}: {exc}") from exc

    return cls(**kwargs)


# ---------------------------------------------------------------------------
# Parent–child attachment via field introspection
# ---------------------------------------------------------------------------


def attach_child(
    parent: Any,
    child: Any,
    *,
    field_hint: str | None = None,
) -> None:
    """Attach *child* to *parent* by discovering the appropriate field.

    When *field_hint* is given (Python name or XML name of a field on the
    parent), the child is placed there directly.  Otherwise the field is
    auto-discovered: the parent's fields are scanned for one whose type
    (or whose property-type wrapper's inner type) matches the child's class.

    Raises :class:`TypeError` when no field matches or when multiple fields
    match (ambiguous: caller must provide *field_hint*).
    """
    child_type = type(child)
    parent_type = type(parent)

    if field_hint is not None:
        info = _resolve_field(parent_type, field_hint)
        if info is None:
            raise ValueError(f"Field {field_hint!r} not found on {parent_type.__name__}")
        _do_attach(parent, child, info)
        return

    # Auto-discover
    candidates = _find_attachment_candidates(parent_type, child_type)

    if len(candidates) == 0:
        raise TypeError(
            f"Cannot attach {child_type.__name__} to "
            f"{parent_type.__name__}: no matching field found"
        )
    if len(candidates) > 1:
        names = [c[0].name for c in candidates]
        raise TypeError(
            f"Ambiguous attachment of {child_type.__name__} to "
            f"{parent_type.__name__}: fields {names} all match. "
            f"Specify 'parent_field' to disambiguate."
        )

    info, wrapper_field_name = candidates[0]
    if wrapper_field_name is not None:
        wrapper = info.inner_type(**{wrapper_field_name: child})
        _set_or_append(parent, info, wrapper)
    else:
        _set_or_append(parent, info, child)


def _find_attachment_candidates(
    parent_type: type,
    child_type: type,
) -> list[tuple[FieldInfo, str | None]]:
    """Find parent fields that can hold *child_type*.

    Returns ``(field_info, wrapper_field_name_or_None)`` tuples.
    ``wrapper_field_name`` is set when the field's type is a property-type
    wrapper with an inner field matching the child.

    Uses MRO distance to rank matches: exact type matches are preferred
    over generic base-class matches.  Fields whose wrapper matches only
    via ``object`` (e.g. ``any_element``) are excluded.
    """
    parent_fields = get_fields(parent_type)
    scored: list[tuple[int, FieldInfo, str | None]] = []

    for info in parent_fields.values():
        if info.is_attribute:
            continue

        # Direct match
        if isinstance(info.inner_type, type) and issubclass(child_type, info.inner_type):
            dist = _mro_distance(child_type, info.inner_type)
            if dist is not None and info.inner_type is not object:
                scored.append((dist, info, None))
            continue

        # Wrapper match
        if isinstance(info.inner_type, type) and dataclasses.is_dataclass(info.inner_type):
            best_dist: int | None = None
            best_wf: str | None = None
            for wf in get_fields(info.inner_type).values():
                if wf.is_attribute:
                    continue
                if not isinstance(wf.inner_type, type):
                    continue
                if wf.inner_type is object:
                    continue  # skip any_element: object
                if issubclass(child_type, wf.inner_type):
                    dist = _mro_distance(child_type, wf.inner_type)
                    if dist is not None and (best_dist is None or dist < best_dist):
                        best_dist = dist
                        best_wf = wf.name
            if best_wf is not None:
                scored.append((best_dist, info, best_wf))  # type: ignore[arg-type]

    if not scored:
        return []

    # Keep only the best-scoring candidates (lowest MRO distance)
    best_score = min(s[0] for s in scored)
    tied = [(info, wf) for score, info, wf in scored if score == best_score]

    if len(tied) <= 1:
        return tied

    # Tie-break: prefer fields whose namespace matches the child's namespace.
    child_ns = getattr(getattr(child_type, "Meta", None), "namespace", None)
    if child_ns:
        ns_matches = [(info, wf) for info, wf in tied if info.namespace == child_ns]
        if ns_matches:
            return ns_matches

    return tied


def _mro_distance(child: type, target: type) -> int | None:
    """MRO distance from *child* to *target* (0 = exact match)."""
    try:
        return child.__mro__.index(target)
    except ValueError:
        return None


def _do_attach(parent: Any, child: Any, info: FieldInfo) -> None:
    """Attach *child* at a specific field, auto-wrapping if needed."""
    child_type = type(child)

    # Direct fit
    if isinstance(info.inner_type, type) and isinstance(child, info.inner_type):
        _set_or_append(parent, info, child)
        return

    # Try wrapping
    if isinstance(info.inner_type, type) and dataclasses.is_dataclass(info.inner_type):
        wrapper_fields = get_fields(info.inner_type)
        for wf in wrapper_fields.values():
            if wf.is_attribute:
                continue
            if isinstance(wf.inner_type, type) and issubclass(child_type, wf.inner_type):
                wrapper = info.inner_type(**{wf.name: child})
                _set_or_append(parent, info, wrapper)
                return

    raise TypeError(
        f"Cannot attach {child_type.__name__} to field "
        f"{info.name} (expected {info.inner_type.__name__})"
    )


def _set_or_append(parent: Any, info: FieldInfo, value: Any) -> None:
    if info.is_list:
        getattr(parent, info.name).append(value)
    else:
        setattr(parent, info.name, value)


# ---------------------------------------------------------------------------
# Generic traversal: walk already-built xsdata trees
# ---------------------------------------------------------------------------


_FIELD_NAMES_CACHE: dict[type, tuple[str, ...]] = {}


def _dataclass_field_names(cls: type) -> tuple[str, ...]:
    """Return the dataclass field names of *cls*, cached per class.

    ``dataclasses.fields(obj)`` rebuilds a tuple from
    ``__dataclass_fields__`` on every call; we pay that cost once per
    class and reuse the result across every instance walked by
    :func:`iter_instances`.
    """
    try:
        return _FIELD_NAMES_CACHE[cls]
    except KeyError:
        names = tuple(f.name for f in dataclasses.fields(cls))
        _FIELD_NAMES_CACHE[cls] = names
        return names


def iter_instances(root: Any) -> Iterator[Any]:
    """Yield every dataclass instance reachable from *root* (DFS, cycle-safe).

    Descends into list fields and into single dataclass-typed fields. Skips
    scalars, strings, enums, and xsdata date/time types (which carry values,
    not further structure). Each instance is yielded at most once; cycles are
    handled by identity.
    """
    # Local aliases for the hot loop.
    is_dataclass = dataclasses.is_dataclass
    field_names = _dataclass_field_names

    seen: set[int] = set()
    seen_add = seen.add
    stack: list[Any] = [root]
    stack_pop = stack.pop
    stack_extend = stack.extend
    stack_append = stack.append

    while stack:
        obj = stack_pop()
        # Skip non-dataclass instances early: ``is_dataclass`` on a class
        # (rather than an instance) returns True, so also guard against
        # type objects (xsdata occasionally has class references in the
        # tree via forward-ref resolution scaffolding).
        if obj is None or isinstance(obj, type) or not is_dataclass(obj):
            continue
        oid = id(obj)
        if oid in seen:
            continue
        seen_add(oid)
        yield obj
        for name in field_names(type(obj)):
            value = getattr(obj, name, None)
            if value is None:
                continue
            if type(value) is list:
                stack_extend(
                    item for item in value if not isinstance(item, type) and is_dataclass(item)
                )
            elif is_dataclass(value) and not isinstance(value, type):
                stack_append(value)


def find_by_id(root: Any, gml_id: str) -> Any | None:
    """Return the first dataclass instance under *root* whose ``id`` is *gml_id*.

    ``id`` is the xsdata-generated attribute for the XML ``gml:id``. Works on
    any xsdata tree, agnostic to which XSD the bindings were generated from.
    """
    for obj in iter_instances(root):
        if getattr(obj, "id", None) == gml_id:
            return obj
    return None
