import logging

from ddtrace.helpers import get_correlation_ids
from ddtrace.constants import ENV_KEY, VERSION_KEY, SERVICE_VERSION_KEY
from ddtrace.compat import StringIO
from ddtrace.contrib.logging import patch, unpatch
from ddtrace.vendor import wrapt

from ...base import BaseTracerTestCase


logger = logging.getLogger()
logger.level = logging.INFO


def capture_function_log(func, fmt):
    # add stream handler to capture output
    out = StringIO()
    sh = logging.StreamHandler(out)

    try:
        formatter = logging.Formatter(fmt)
        sh.setFormatter(formatter)
        logger.addHandler(sh)
        result = func()
    finally:
        logger.removeHandler(sh)

    return out.getvalue().strip(), result


class LoggingTestCase(BaseTracerTestCase):
    def setUp(self):
        patch()
        super(LoggingTestCase, self).setUp()

    def tearDown(self):
        unpatch()
        super(LoggingTestCase, self).tearDown()

    def test_patch(self):
        """
        Confirm patching was successful
        """
        patch()
        log = logging.getLogger()
        self.assertTrue(isinstance(log.makeRecord, wrapt.BoundFunctionWrapper))

    def test_log_trace(self):
        """
        Check logging patched and formatter including trace info
        """

        @self.tracer.wrap()
        def func():
            logger.info("Hello!")
            return get_correlation_ids(tracer=self.tracer)

        with self.override_global_config(dict(env="prod", version="23.45.6")):
            with self.override_config("logging", dict(tracer=self.tracer)):
                # with format string for trace info
                output, result = capture_function_log(
                    func,
                    fmt="%(message)s - dd.trace_id=%(dd.trace_id)s dd.span_id=%(dd.span_id)s "
                    "dd.env=%(dd.env)s dd.version=%(dd.version)s",
                )
                self.assertEqual(
                    output, "Hello! - dd.trace_id={} dd.span_id={} dd.env=prod dd.version=23.45.6".format(*result),
                )

                # without format string
                output, _ = capture_function_log(func, fmt="%(message)s",)
                self.assertEqual(
                    output, "Hello!",
                )

    def test_log_no_trace(self):
        """
        Check traced funclogging patched and formatter not including trace info
        """

        def func():
            logger.info("Hello!")
            return get_correlation_ids()

        with self.override_global_config(dict(env="prod", version="23.45.6")):
            with self.override_config("logging", dict(tracer=self.tracer)):
                # with format string for trace info
                output, _ = capture_function_log(
                    func,
                    fmt="%(message)s - dd.trace_id=%(dd.trace_id)s dd.span_id=%(dd.span_id)s "
                    "dd.env=%(dd.env)s dd.version=%(dd.version)s",
                )
                self.assertEqual(
                    output, "Hello! - dd.trace_id=0 dd.span_id=0 dd.env=prod dd.version=23.45.6",
                )

    def test_log_no_env(self):
        """
        Check traced funclogging patched and formatter not including env info
        """

        def func():
            logger.info("Hello!")
            return get_correlation_ids()

        with self.override_config("logging", dict(tracer=self.tracer)):
            # with format string for trace info
            output, _ = capture_function_log(func, fmt="%(message)s - dd.env=%(dd.env)s",)
            self.assertEqual(
                output, "Hello! - dd.env=",
            )

    def test_log_no_version(self):
        """
        Check traced funclogging patched and formatter not including version info
        """

        def func():
            logger.info("Hello!")
            return get_correlation_ids()

        with self.override_config("logging", dict(tracer=self.tracer)):
            # with format string for trace info
            output, _ = capture_function_log(func, fmt="%(message)s - dd.version=%(dd.version)s",)
            self.assertEqual(
                output, "Hello! - dd.version=",
            )

    def test_log_span_env(self):
        """
        Check traced funclogging patched and formatter including span env info
        """

        def func():
            with self.tracer.trace("test.span") as span:
                span.set_tag(ENV_KEY, "prod")
                logger.info("Hello!")
                return get_correlation_ids()

        with self.override_config("logging", dict(tracer=self.tracer)):
            # with format string for trace info
            output, _ = capture_function_log(func, fmt="%(message)s - dd.env=%(dd.env)s",)
            self.assertEqual(
                output, "Hello! - dd.env=prod",
            )

    def test_log_span_version(self):
        """
        Check traced funclogging patched and formatter including span version info
        """

        def func():
            with self.tracer.trace("test.span") as span:
                span.set_tag(VERSION_KEY, "1.2.3")
                logger.info("Hello!")
                return get_correlation_ids()

        with self.override_config("logging", dict(tracer=self.tracer)):
            # with format string for trace info
            output, _ = capture_function_log(func, fmt="%(message)s - dd.version=%(dd.version)s",)
            self.assertEqual(
                output, "Hello! - dd.version=1.2.3",
            )

    def test_log_span_service_version(self):
        """
        Check traced funclogging patched and formatter including span version info
        """

        def func():
            with self.tracer.trace("test.span") as span:
                span.set_tag(SERVICE_VERSION_KEY, "1.2.3")
                logger.info("Hello!")
                return get_correlation_ids()

        with self.override_config("logging", dict(tracer=self.tracer)):
            # with format string for trace info
            output, _ = capture_function_log(func, fmt="%(message)s - dd.version=%(dd.version)s",)
            self.assertEqual(
                output, "Hello! - dd.version=1.2.3",
            )

    def test_log_span_global_and_env(self):
        """
        Check traced funclogging patched and formatter including env version info.
        The span tag for `env` should take precedence over the global config.
        """

        def func():
            with self.tracer.trace("test.span") as span:
                span.set_tag(ENV_KEY, "prod-staging")
                logger.info("Hello!")
                return get_correlation_ids()

        with self.override_global_config(dict(env="prod")):
            with self.override_config("logging", dict(tracer=self.tracer)):
                # with format string for trace info
                output, _ = capture_function_log(func, fmt="%(message)s - dd.env=%(dd.env)s",)
                self.assertEqual(
                    output, "Hello! - dd.env=prod-staging",
                )

    def test_log_span_global_and_version(self):
        """
        Check traced funclogging patched and formatter including span version info
        """

        def func():
            with self.tracer.trace("test.span") as span:
                span.set_tag(VERSION_KEY, "1.2.3")
                logger.info("Hello!")
                return get_correlation_ids()

        with self.override_global_config(dict(version="23.45.6")):
            with self.override_config("logging", dict(tracer=self.tracer)):
                # with format string for trace info
                output, _ = capture_function_log(func, fmt="%(message)s - dd.version=%(dd.version)s",)
                self.assertEqual(
                    output, "Hello! - dd.version=1.2.3",
                )

    def test_log_span_global_and_service_version(self):
        """
        Check traced funclogging patched and formatter including span version info
        """

        def func():
            with self.tracer.trace("test.span") as span:
                span.set_tag(SERVICE_VERSION_KEY, "1.2.3")
                logger.info("Hello!")
                return get_correlation_ids()

        with self.override_global_config(dict(version="23.45.6")):
            with self.override_config("logging", dict(tracer=self.tracer)):
                # with format string for trace info
                output, _ = capture_function_log(func, fmt="%(message)s - dd.version=%(dd.version)s",)
                self.assertEqual(
                    output, "Hello! - dd.version=1.2.3",
                )
