import logging

import ddtrace

from ...constants import VERSION_KEY, ENV_KEY
from ...utils.wrappers import unwrap as _u
from ...vendor.wrapt import wrap_function_wrapper as _w

RECORD_ATTR_ENV = "dd.env"
RECORD_ATTR_VERSION = "dd.version"
RECORD_ATTR_TRACE_ID = "dd.trace_id"
RECORD_ATTR_SPAN_ID = "dd.span_id"
RECORD_ATTR_VALUE_ZERO = 0
RECORD_ATTR_VALUE_EMPTY = ""

ddtrace.config._add("logging", dict(tracer=None))  # by default, override here for custom tracer


def _inject_or_default(record, key, value, default=RECORD_ATTR_VALUE_EMPTY):
    if not value:
        value = default
    setattr(record, key, value)


def _w_makeRecord(func, instance, args, kwargs):
    record = func(*args, **kwargs)

    # We must *always* inject these variables into the record, even if we don't
    #   have an active span, if someone hard codes their format string to add these
    #   then they must be there
    #
    # - dd.env
    # - dd.version
    # - dd.trace_id
    # - dd.span_id

    tracer = ddtrace.config.logging.tracer or ddtrace.tracer
    span = tracer.current_span()

    # Add the application version to LogRecord
    # Order of precedence:
    #   - `env`/`version` tag if set on the span (this might be automatic if they used DD_ENV/DD_VERSION)
    #   - `ddtrace.config.version` if defined
    #     - Even though this gets set to the `env`/`version` tag we fallback here in case there
    #       is no currently active span, we should still be able to log this information
    version = ddtrace.config.version
    if span and VERSION_KEY in span.meta:
        version = span.get_tag(VERSION_KEY)
    _inject_or_default(record, RECORD_ATTR_VERSION, version)
    env = ddtrace.config.env
    if span and ENV_KEY in span.meta:
        env = span.get_tag(ENV_KEY)
    _inject_or_default(record, RECORD_ATTR_ENV, env)

    # TODO: Inject DD_SERVICE

    # add correlation identifiers to LogRecord
    if span and span.trace_id and span.span_id:
        setattr(record, RECORD_ATTR_TRACE_ID, span.trace_id)
        setattr(record, RECORD_ATTR_SPAN_ID, span.span_id)
    else:
        setattr(record, RECORD_ATTR_TRACE_ID, RECORD_ATTR_VALUE_ZERO)
        setattr(record, RECORD_ATTR_SPAN_ID, RECORD_ATTR_VALUE_ZERO)

    return record


def patch():
    """
    Patch ``logging`` module in the Python Standard Library for injection of
    tracer information by wrapping the base factory method ``Logger.makeRecord``
    """
    if getattr(logging, "_datadog_patch", False):
        return
    setattr(logging, "_datadog_patch", True)

    _w(logging.Logger, "makeRecord", _w_makeRecord)


def unpatch():
    if getattr(logging, "_datadog_patch", False):
        setattr(logging, "_datadog_patch", False)

        _u(logging.Logger, "makeRecord")
