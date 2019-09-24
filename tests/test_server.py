import os
import sys
sys.path.insert(0, os.path.abspath('..'))
import json

from io import BytesIO

from twisted.internet import reactor, defer
from twisted.internet.defer import succeed
from twisted.internet.protocol import Protocol
from twisted.web.client import Agent, ContentDecoderAgent, GzipDecoder
from twisted.web.http_headers import Headers
from twisted.web.iweb import IBodyProducer
from twisted.web.server import NOT_DONE_YET, Site
from twisted.web.test.test_web import DummyRequest
from zope.interface import implementer

from fastjsonrpc.server import JSONRPCServer, EncodingJSONRPCServer

from .dummyserver import DummyServer, DBFILE
from .helpers import ExtendedTestCase


def _render(resource, request):
    result = resource.render(request)
    if isinstance(result, str):
        request.write(result)
        request.finish()
        return succeed(None)
    elif result is NOT_DONE_YET:
        if request.finished:
            return succeed(None)
        else:
            return request.notifyFinish()
    else:
        raise ValueError('Unexpected return value: %r' % (result,))


class TestRender(ExtendedTestCase):
    timeout = 1

    def setUp(self):
        self.srv = DummyServer()

    def tearDown(self):
        if os.path.exists(DBFILE):
            os.unlink(DBFILE)

    def test_emptyRequest(self):
        request = DummyRequest([''])
        request.content = BytesIO(b'')
        d = _render(self.srv, request)

        def rendered(_):
            expected = '{"jsonrpc": "2.0", "id": null, "error": ' + \
                       '{"message": "Parse error", "code": -32700}}'
            self.assert_json(request.written[0], expected)

        d.addCallback(rendered)
        return d

    def test_malformed(self):
        request = DummyRequest([''])
        request.content = BytesIO(b'{"method": "sql", "id')
        d = _render(self.srv, request)

        def rendered(_):
            expected = '{"jsonrpc": "2.0", "id": null, "error": ' + \
                       '{"message": "Parse error", "code": -32700}}'
            self.assert_json(request.written[0], expected)

        d.addCallback(rendered)
        return d

    def test_contentType(self):
        request = DummyRequest([''])
        request.content = BytesIO(b'{"method": "echo", "id": 1, "params": ["ab"]}')
        d = _render(self.srv, request)

        def rendered(_):
            self.assert_has_header(request.responseHeaders, name='content-type', expected='application/json')

        d.addCallback(rendered)
        return d

    def test_contentLength(self):
        request = DummyRequest([''])
        request.content = BytesIO(b'{"method": "echo", "id": 1, "params": ["ab"]}')
        d = _render(self.srv, request)

        def rendered(_):
            self.assert_has_header(request.responseHeaders, name='content-length',
                                   expected=str(len(request.written[0])))

        d.addCallback(rendered)
        return d

    def test_idStrV1(self):
        request = DummyRequest([''])
        request.content = BytesIO(b'{"method": "echo", "id": "abcd", "params": ["ab"]}')
        d = _render(self.srv, request)

        def rendered(_):
            expected = '{"error": null, "id": "abcd", "result": "ab"}'
            self.assert_json(request.written[0], expected)

        d.addCallback(rendered)
        return d

    def test_idStrV2(self):
        request = DummyRequest([''])
        request.content = BytesIO(b'{"method": "echo", "id": "abcd", "params": ["ab"], "jsonrpc": "2.0"}')
        d = _render(self.srv, request)

        def rendered(_):
            expected = '{"jsonrpc": "2.0", "id": "abcd", ' + \
                       '"result": "ab"}'
            self.assert_json(request.written[0], expected)

        d.addCallback(rendered)
        return d

    def test_returnNone(self):
        request = DummyRequest([''])
        request.content = BytesIO(b'{"method": "returnNone", "id": 1}')

        d = _render(self.srv, request)

        def rendered(_):
            expected = '{"error": null, "id": 1, "result": null}'
            self.assert_json(request.written[0], expected)

        d.addCallback(rendered)
        return d

    def test_caseSensitiveMethodV1(self):
        request = DummyRequest([''])
        request.content = BytesIO(b'{"method": "ECHO", "id": "ABCD", "params": ["AB"]}')
        d = _render(self.srv, request)

        def rendered(_):
            expected = '{"result": null, "id": "ABCD", "error": {' + \
                       '"message": "Method ECHO not found", "code": -32601}}'
            self.assert_json(request.written[0], expected)

        d.addCallback(rendered)
        return d

    def test_caseSensitiveParamsV2(self):
        request = DummyRequest([''])
        request.content = BytesIO(b'{"method": "echo", "id": "ABCD", "params": ["AB"], "jsonrpc": "2.0"}')
        d = _render(self.srv, request)

        def rendered(_):
            expected = '{"jsonrpc": "2.0", "id": "ABCD", "result": "AB"}'
            self.assert_json(request.written[0], expected)

        d.addCallback(rendered)
        return d

    def test_invalidMethodCaseSensitive(self):
        request = DummyRequest([''])
        request.content = BytesIO(b'{"METHOD": "echo", "id": "ABCD", "params": ["AB"]}')
        d = _render(self.srv, request)

        def rendered(_):
            expected = '{"result": null, "id": "ABCD", "error": ' + \
                       '{"message": "Invalid method type", "code": -32600}}'
            self.assert_json(request.written[0], expected)

        d.addCallback(rendered)
        return d

    def test_invalidIdCaseSensitive(self):
        request = DummyRequest([''])
        request.content = BytesIO(b'{"method": "echo", "ID": "ABCD", "params": ["AB"]}')
        d = _render(self.srv, request)

        def rendered(_):
            self.assertEquals(request.written, [])

        d.addCallback(rendered)
        return d

    def test_invalidParamsCaseSensitive(self):
        request = DummyRequest([''])
        request.content = BytesIO(b'{"method": "echo", "id": "ABCD", "PARAMS": ["AB"]}')
        d = _render(self.srv, request)

        def rendered(_):
            expected = '{"id": "ABCD", "error": {"message": "jsonrpc_echo() missing 1 required positional argument:' + \
                       ' \'data\'", "code": -32602}, "result": null}'
            self.assert_json(request.written[0], expected)

        d.addCallback(rendered)
        return d

    def test_echoOk(self):
        request = DummyRequest([''])
        request.content = BytesIO(b'{"method": "echo", "id": 1, "params": ["ab"]}')
        d = _render(self.srv, request)

        def rendered(_):
            expected = '{"error": null, "id": 1, "result": "ab"}'
            self.assert_json(request.written[0], expected)

        d.addCallback(rendered)
        return d

    def test_echoOkV2(self):
        request = DummyRequest([''])
        request.content = BytesIO(b'{"method": "echo", "id": 1, "params": ["ab"], "jsonrpc": "2.0"}')
        d = _render(self.srv, request)

        def rendered(_):
            expected = '{"jsonrpc": "2.0", "id": 1, "result": "ab"}'
            self.assert_json(request.written[0], expected)

        d.addCallback(rendered)
        return d

    def test_sqlOkV1(self):
        request = DummyRequest([''])
        request.content = BytesIO(b'{"method": "sql", "id": 1}')
        d = _render(self.srv, request)

        def rendered(_):
            self.assert_json_values(request.written[0], error=None, id=1, result=list)

        d.addCallback(rendered)
        return d

    def test_sqlOkV2(self):
        request = DummyRequest([''])
        request.content = BytesIO(b'{"jsonrpc": "2.0", "method": "sql", "id": 1}')
        d = _render(self.srv, request)

        def rendered(_):
            self.assert_json_values(request.written[0], jsonrpc="2.0", id=1, result=list)

        d.addCallback(rendered)
        return d

    def test_notificationV1(self):
        request = DummyRequest([''])
        request.content = BytesIO(b'{"method": "sql"}')
        d = _render(self.srv, request)

        def rendered(_):
            self.assertEquals(request.written, [])

        d.addCallback(rendered)
        return d

    def test_notificationV2(self):
        request = DummyRequest([''])
        request.content = BytesIO(b'{"method": "sql", "jsonrpc": "2.0"}')
        d = _render(self.srv, request)

        def rendered(_):
            self.assertEquals(request.written, [])

        d.addCallback(rendered)
        return d

    def test_noSuchMethodNoId(self):
        request = DummyRequest([''])
        request.content = BytesIO(b'{"method": "aaaa"}')
        d = _render(self.srv, request)

        def rendered(_):
            self.assertEquals(request.written, [])

        d.addCallback(rendered)
        return d

    def test_noSuchMethodV1(self):
        request = DummyRequest([''])
        request.content = BytesIO(b'{"method": "aaaa", "id": 1}')
        d = _render(self.srv, request)

        def rendered(_):
            expected = '{"result": null, "id": 1, "error": ' + \
                       '{"message": "Method aaaa not found", ' + \
                       '"code": -32601}}'
            self.assert_json(request.written[0], expected)

        d.addCallback(rendered)
        return d

    def test_noSuchMethodV2(self):
        request = DummyRequest([''])
        request.content = BytesIO(b'{"method": "aaaa", "id": 1, "jsonrpc": "2.0"}')
        d = _render(self.srv, request)

        def rendered(_):
            expected = '{"jsonrpc": "2.0", "id": 1, "error": ' + \
                       '{"message": "Method aaaa not found", ' + \
                       '"code": -32601}}'
            self.assert_json(request.written[0], expected)

        d.addCallback(rendered)
        return d

    def test_wrongParams(self):
        request = DummyRequest([''])
        request.content = BytesIO(b'{"method": "sql", "id": 1, "params": ["aa", "bb"]}')
        d = _render(self.srv, request)

        def rendered(_):
            expected = '{"id": 1, "error": {"message": "jsonrpc_sql() takes 1 positional argument ' + \
                       'but 3 were given", "code": -32602}, "result": null}'
            self.assert_json(request.written[0], expected)

        d.addCallback(rendered)
        return d

    def test_keywordsOkV1(self):
        request = DummyRequest([''])
        request.content = BytesIO(b'{"method": "echo", "id": 1, "params": {"data": "arg"}}')
        d = _render(self.srv, request)

        def rendered(_):
            expected = '{"error": null, "id": 1, "result": "arg"}'
            self.assert_json(request.written[0], expected)

        d.addCallback(rendered)
        return d

    def test_keywordsOkV2(self):
        request = DummyRequest([''])
        request.content = BytesIO(b'{"method": "echo", "id": 1, "params": {"data": "arg"}, "jsonrpc": "2.0"}')
        d = _render(self.srv, request)

        def rendered(_):
            expected = '{"jsonrpc": "2.0", "id": 1, "result": "arg"}'
            self.assert_json(request.written[0], expected)

        d.addCallback(rendered)
        return d

    def test_keywordsUnexpected(self):
        request = DummyRequest([''])
        request.content = BytesIO(b'{"method": "echo", "id": 1, "params": {"wrongname": "arg"}}')
        d = _render(self.srv, request)

        def rendered(_):
            expected = '{"result": null, "id": 1, "error": {"message": ' + \
                       '"jsonrpc_echo() got an unexpected keyword argument' + \
                       ' \'wrongname\'", "code": -32602}}'

            self.assert_json(request.written[0], expected)

        d.addCallback(rendered)
        return d

    def test_batch(self):
        json = '[{"method": "echo", "id": 1, "params": {"data": "arg"}}, ' + \
               '{"method": "echo", "id": 2, "params": {"data": "arg"}}]'
        request = DummyRequest([''])
        request.content = BytesIO(json.encode())
        d = _render(self.srv, request)

        def rendered(_):
            expected = '[{"error": null, "id": 1, "result": "arg"}, ' + \
                       '{"error": null, "id": 2, "result": "arg"}]'
            self.assert_json(request.written[0], expected)

        d.addCallback(rendered)
        return d

    def test_batchNotificationOnly(self):
        json = '[{"method": "echo", "params": {"data": "arg"}}, ' + \
               '{"method": "echo", "params": {"data": "arg"}}]'
        request = DummyRequest([''])
        request.content = BytesIO(json.encode())
        d = _render(self.srv, request)

        def rendered(_):
            self.assertEquals(request.written, [])

        d.addCallback(rendered)
        return d

    def test_batchNotificationMixed(self):
        json = '[{"method": "echo", "id": 1, "params": {"data": "arg"}}, ' + \
               '{"method": "echo", "id": 2, "params": {"data": "arg"}}, ' + \
               '{"method": "echo", "params": {"data": "arg"}}]'
        request = DummyRequest([''])
        request.content = BytesIO(json.encode())
        d = _render(self.srv, request)

        def rendered(_):
            expected = '[{"error": null, "id": 1, "result": "arg"}, ' + \
                       '{"error": null, "id": 2, "result": "arg"}]'
            self.assert_json(request.written[0], expected)

        d.addCallback(rendered)
        return d

    def test_batchV1V2(self):
        json = '[{"method": "echo", "id": 1, "params": ["arg"]}, ' + \
               '{"method": "echo", "id": "abc", "params": ["arg"], ' + \
               '"jsonrpc": "2.0"}]'
        request = DummyRequest([''])
        request.content = BytesIO(json.encode())
        d = _render(self.srv, request)

        def rendered(_):
            expected = '[{"error": null, "id": 1, "result": "arg"}, ' + \
                       '{"jsonrpc": "2.0", "id": "abc", "result": "arg"}]'
            self.assert_json(request.written[0], expected)

        d.addCallback(rendered)
        return d

    def test_batchSingle(self):
        json = '[{"method": "echo", "id": 1, "params": ["arg"]}]'
        request = DummyRequest([''])
        request.content = BytesIO(json.encode())
        d = _render(self.srv, request)

        def rendered(_):
            expected = '[{"error": null, "id": 1, "result": "arg"}]'
            self.assert_json(request.written[0], expected)

        d.addCallback(rendered)
        return d

    def test_batchNotificationAndSingle(self):
        json = '[{"method": "echo", "id": 1, "params": ["arg"]}, ' + \
               '{"method": "echo", "params": ["arg"]}]'
        request = DummyRequest([''])
        request.content = BytesIO(json.encode())
        d = _render(self.srv, request)

        def rendered(_):
            expected = '[{"error": null, "id": 1, "result": "arg"}]'
            self.assert_json(request.written[0], expected)

        d.addCallback(rendered)
        return d


class TestEncodingJSONRPCServer(ExtendedTestCase):

    timeout = 1

    @defer.inlineCallbacks
    def test_EncodingJSONRPCServer(self):

        DATA = {'foo': 'bar'}
        REQUEST = '{"jsonrpc": "2.0", "method": "test", "params": [], "id": 1}'
        RESPONSE = '{"jsonrpc": "2.0", "id": 1, "result": ' + json.dumps(DATA) + '}'

        class RPCServer(JSONRPCServer):
            def jsonrpc_test(self):
                return defer.succeed(DATA)

        class ReceiverProtocol(Protocol):
            def __init__(self, finished):
                self.finished = finished
                self.body = []

            def dataReceived(self, bytes):
                self.body.append(bytes)

            def connectionLost(self, reason):
                self.finished.callback(b''.join(self.body))

        @implementer(IBodyProducer)
        class StringProducer(object):

            def __init__(self, body):
                self.body = body
                self.length = len(body)

            def startProducing(self, consumer):
                consumer.write(self.body.encode())
                return defer.succeed(None)

            def pauseProducing(self):
                pass

            def stopProducing(self):
                pass

        server = RPCServer()
        resource = EncodingJSONRPCServer(server)
        site = Site(resource)

        port = reactor.listenTCP(8888, site, interface='127.0.0.1')

        agent = ContentDecoderAgent(Agent(reactor), [(b'gzip', GzipDecoder)])

        response = yield agent.request(b'POST', b'http://127.0.0.1:8888',
                                       Headers({'Accept-Encoding': ['gzip']}),
                                       StringProducer(REQUEST))

        self.assertTrue(isinstance(response, GzipDecoder))

        finished = defer.Deferred()

        response.deliverBody(ReceiverProtocol(finished))

        data = yield finished

        self.assert_json(data, RESPONSE)

        port.stopListening()
