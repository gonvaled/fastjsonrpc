import re
import json

from twisted.trial.unittest import TestCase


class Regex:

    def __init__(self, pattern):
        self._pattern = pattern

    @property
    def pattern(self):
        return self._pattern


class ExtendedTestCase(TestCase):

    def assert_json(self, value, expected):
        value = json.loads(value) if isinstance(value, (str, bytes)) else value
        expected = json.loads(expected) if isinstance(expected, (str, bytes)) else expected
        self.assertEquals(value, expected)

    def assert_json_values(self, value, **kwargs):
        value = json.loads(value)
        for key, expected in kwargs.items():
            if expected is list:
                assert isinstance(value[key], list)
            elif isinstance(expected, Regex):
                value2 = str(value[key])
                self.assertTrue(re.match(expected.pattern, value2))
            else:
                self.assertEquals(value[key], expected)

    def assert_has_header(self, headers, name, expected):
        value = headers.getRawHeaders(name.lower(), [None])[0]
        self.assertEquals(value, expected)


