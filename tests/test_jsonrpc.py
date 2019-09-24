import json
import re

from fastjsonrpc import jsonrpc
from fastjsonrpc.jsonrpc import JSONRPCError

from .helpers import ExtendedTestCase, Regex


class TestEncodeRequest(ExtendedTestCase):

    def assert_json(self, value, expected):
        value = json.loads(value)
        expected = json.loads(expected)
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

    def test_noArgs(self):
        self.assertRaises(TypeError, jsonrpc.encodeRequest)

    def test_onlyMethod(self):
        result = jsonrpc.encodeRequest('method')
        pattern = r'\{"method": "method", "id": \d+\}'
        self.assertTrue(re.match(pattern, result))

    def test_methodIdInt(self):
        result = jsonrpc.encodeRequest('method', id_=123)
        expected = '{"method": "method", "id": 123}'
        self.assert_json(result, expected)

    def test_methodIdStr(self):
        result = jsonrpc.encodeRequest('method', id_='abc')
        expected = '{"method": "method", "id": "abc"}'
        self.assert_json(result, expected)

    def test_methodArgs(self):
        result = jsonrpc.encodeRequest('method', ['abc', 'def'])
        self.assert_json_values(result, params=['abc', 'def'], method='method', id=Regex(r'\d+'))

    def test_methodKwargs(self):
        result = jsonrpc.encodeRequest('method', {'first': 'a', 'second': 'b'})
        self.assert_json_values(result, params={'first': 'a', 'second': 'b'}, method='method', id=Regex(r'\d+'))

    def test_methodVersion1(self):
        result = jsonrpc.encodeRequest('method', version=1.0)
        self.assert_json_values(result, method='method', id=Regex(r'\d+'))

    def test_methodVersion2(self):
        result = jsonrpc.encodeRequest('method', version=2.0)
        self.assert_json_values(result, jsonrpc='2.0', method='method', id=Regex(r'\d+'))

    def test_methodVersion2int(self):
        result = jsonrpc.encodeRequest('method', version=2)
        self.assert_json_values(result, jsonrpc='2.0', method='method', id=Regex(r'\d+'))

    def test_methodVersion3(self):
        result = jsonrpc.encodeRequest('method', version=3)
        self.assert_json_values(result, method='method', id=Regex(r'\d+'))

    def test_methodIdVersion(self):
        result = jsonrpc.encodeRequest('method', version=2.0, id_=123)
        self.assert_json_values(result, jsonrpc='2.0', method='method', id=123)

    def test_methodArgsId(self):
        result = jsonrpc.encodeRequest('method', 'abcdef', id_=123)
        self.assert_json_values(result, params='abcdef', method='method', id=123)

    def test_methodArgsVersion2(self):
        result = jsonrpc.encodeRequest('method', 'abcdef', version=2)
        self.assert_json_values(result, jsonrpc='2.0', params='abcdef', method='method', id=Regex(r'\d+'))

    def test_all(self):
        result = jsonrpc.encodeRequest('method', 'abcdef', id_=123, version=2.0)
        self.assert_json_values(result, jsonrpc='2.0', params='abcdef', method='method', id=123)


class TestDecodeRequest(ExtendedTestCase):

    def test_empty(self):
        self.assertRaises(Exception, jsonrpc.decodeRequest, '')

    def test_malformed(self):
        self.assertRaises(Exception, jsonrpc.decodeRequest, '{"method": "aa')

    def test_onlyMethod(self):
        result = jsonrpc.decodeRequest('{"method": "aa"}')
        expected = {'method': 'aa'}
        self.assert_json(result, expected)

    def test_onlyParams(self):
        request = '{"params": "abcdef"}'
        result = jsonrpc.decodeRequest(request)
        expected = {'params': 'abcdef'}
        self.assert_json(result, expected)

    def test_onlyIdInt(self):
        request = '{"id": 123}'
        result = jsonrpc.decodeRequest(request)
        expected = {'id': 123}
        self.assertEquals(result, expected)

    def test_onlyIdStr(self):
        request = '{"id": "1b3"}'
        result = jsonrpc.decodeRequest(request)
        expected = {'id': '1b3'}
        self.assertEquals(result, expected)

    def test_onlyVersionInt(self):
        request = '{"jsonrpc": 1}'
        result = jsonrpc.decodeRequest(request)
        expected = {'jsonrpc': 1}
        self.assertEquals(result, expected)

    def test_onlyVersionFloat(self):
        request = '{"jsonrpc": 2.0}'
        result = jsonrpc.decodeRequest(request)
        expected = {'jsonrpc': 2.0}
        self.assertEquals(result, expected)

    def test_onlyVersionStr(self):
        request = '{"jsonrpc": "2"}'
        result = jsonrpc.decodeRequest(request)
        expected = {'jsonrpc': "2"}
        self.assertEquals(result, expected)

    def test_combined(self):
        request = '{"method": "abc", "params": ["p1", 12321], "jsonrpc": 2.0, '
        request += '"id": 123}'
        result = jsonrpc.decodeRequest(request)
        expected = {'method': 'abc', 'params': ['p1', 12321], 'jsonrpc': 2.0,
                    'id': 123}
        self.assertEquals(result, expected)


class TestVerifyMethodCall(ExtendedTestCase):

    def test_onlyMethod(self):
        request = {'method': 'abc'}
        self.assertEquals(request, jsonrpc.verifyMethodCall(request))

    def test_onlyId(self):
        request = {'id': 123}
        self.assertRaises(JSONRPCError, jsonrpc.verifyMethodCall, request)

    def test_onlyVersion(self):
        request = {'jsonrpc': 2}
        self.assertRaises(JSONRPCError, jsonrpc.verifyMethodCall, request)

    def test_onlyParams(self):
        request = {'params': [123, 'afaf']}
        self.assertRaises(JSONRPCError, jsonrpc.verifyMethodCall, request)

    def test_paramsNotSequence(self):
        request = {'method': 'aa', 'params': 123}
        self.assertRaises(JSONRPCError, jsonrpc.verifyMethodCall, request)

    def test_paramsSequence(self):
        request = {'method': 'aa', 'params': ['abcdef', 12321]}
        self.assertEquals(request, jsonrpc.verifyMethodCall(request))

    def test_paramsMapping(self):
        request = {'method': 'aa', 'params': {'name': 'data', 'name2': 'data'}}
        self.assertEquals(request, jsonrpc.verifyMethodCall(request))

    def test_idInt(self):
        request = {'method': 'aa', 'id': 1}
        self.assertEquals(request, jsonrpc.verifyMethodCall(request))

    def test_idStr(self):
        request = {'method': 'aa', 'id': '1b3'}
        self.assertEquals(request, jsonrpc.verifyMethodCall(request))

    def test_versionInt(self):
        request = {'method': 'aa', 'jsonrpc': 2}
        self.assertRaises(JSONRPCError, jsonrpc.verifyMethodCall, request)

    def test_versionFloat(self):
        request = {'method': 'aa', 'jsonrpc': 2.0}
        self.assertEquals(request, jsonrpc.verifyMethodCall(request))

    def test_versionStr(self):
        request = {'method': 'aa', 'jsonrpc': '2'}
        self.assertEquals(request, jsonrpc.verifyMethodCall(request))


class TestPrepareMethodResponse(ExtendedTestCase):

    def test_noResponseNoVersion(self):
        result = jsonrpc.prepareMethodResponse(None, 123)
        expected = {"error": None, "id": 123, "result": None}
        self.assertEquals(result, expected)

    def test_noResponseV2(self):
        result = jsonrpc.prepareMethodResponse(None, 123, 2)
        expected = {"jsonrpc": "2.0", "id": 123, "result": None}
        self.assertEquals(result, expected)

    def test_responseStr(self):
        result = jsonrpc.prepareMethodResponse("result", 123)
        expected = {"error": None, "id": 123, "result": "result"}
        self.assertEquals(result, expected)

    def test_responseInt(self):
        result = jsonrpc.prepareMethodResponse(12321, 123)
        expected = {"error": None, "id": 123, "result": 12321}
        self.assertEquals(result, expected)

    def test_noId(self):
        result = jsonrpc.prepareMethodResponse(None, None)
        expected = None
        self.assertEquals(result, expected)

    def test_idStr(self):
        result = jsonrpc.prepareMethodResponse(None, '1b3')
        expected = {"error": None, "id": "1b3", "result": None}
        self.assertEquals(result, expected)

    def test_responseException(self):
        response = ValueError('The method raised an exception!')
        result = jsonrpc.prepareMethodResponse(response, 123)
        expected = {"result": None, "id": 123,
                    "error": {"message": "The method raised an exception!", "code": -32603}}
        self.assertEquals(result, expected)

    def test_invalidParams(self):
        response = TypeError('Invalid params')
        result = jsonrpc.prepareMethodResponse(response, 123)
        expected = {"result": None, "id": 123,
                    "error": {"message": "Invalid params", "code": -32602}}
        self.assertEquals(result, expected)

    def test_methodNotFount(self):
        response = JSONRPCError('Method aa not found',
                                jsonrpc.METHOD_NOT_FOUND)
        result = jsonrpc.prepareMethodResponse(response, 123)
        expected = {"result": None, "id": 123,
                    "error": {"message": "Method aa not found", "code": -32601}}
        self.assertEquals(result, expected)


class TestDecodeResponse(ExtendedTestCase):

    def test_noResponse(self):
        self.assertRaises(Exception, jsonrpc.decodeResponse, '')

    def test_malformedResponse(self):
        self.assertRaises(Exception, jsonrpc.decodeResponse, '{"respons')

    def test_onlyId(self):
        response = '{"id": 123}'
        self.assertRaises(ValueError, jsonrpc.decodeResponse, response)

    def test_idVersion(self):
        response = '{"id": 123, "jsonrpc": "2.0"}'
        self.assertRaises(ValueError, jsonrpc.decodeResponse, response)

    def test_onlyResult(self):
        response = '{"result": "abcd"}'
        ret = 'abcd'
        self.assertEquals(ret, jsonrpc.decodeResponse(response))

    def test_onlyErrorRaises(self):
        response = '{"error": {"message": "some error", "code": 123}}'
        self.assertRaises(JSONRPCError, jsonrpc.decodeResponse, response)

    def test_onlyErrorExceptionDetails(self):
        response = '{"error": {"message": "some error", "code": 123}}'
        try:
            jsonrpc.decodeResponse(response)
        except jsonrpc.JSONRPCError as e:
            self.assertEquals(e.strerror, 'some error')
            self.assertEquals(e.errno, 123)
            self.assertEquals(e.version, jsonrpc.VERSION_1)

    def test_resultAndErrorNull(self):
        response = '{"result": "abcd", "error": null}'
        ret = 'abcd'
        self.assertEquals(ret, jsonrpc.decodeResponse(response))

    def test_errorAndResultNull(self):
        response = '{"result": null, "error": {"message": "some error", '
        response += '"code": 123}}'
        self.assertRaises(JSONRPCError, jsonrpc.decodeResponse, response)

    def test_errorAndResultNullExceptionDetails(self):
        response = '{"result": null, "error": {"message": "some error", '
        response += '"code": 123}}'
        try:
            jsonrpc.decodeResponse(response)
        except jsonrpc.JSONRPCError as e:
            self.assertEquals(e.strerror, 'some error')
            self.assertEquals(e.errno, 123)
            self.assertEquals(e.version, jsonrpc.VERSION_1)

    def test_errorAndResult(self):
        response = '{"error": {"message": "some error", "code": 123}, '
        response += '"result": "abcd"}'
        self.assertRaises(ValueError, jsonrpc.decodeResponse, response)

    def test_errorAndResult2(self):
        response = '{"error": {"message": "some error", "code": 123}, '
        response += '"result": "abcd", "jsonrpc": "2.0"}'
        self.assertRaises(ValueError, jsonrpc.decodeResponse, response)

    def test_emptyResult(self):
        response = '{"result": null}'
        self.assertEquals(None, jsonrpc.decodeResponse(response))
