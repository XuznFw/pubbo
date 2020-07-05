import socket
from .common import JavaObject, RequestMessage, GenericException
from .serialization import ResponseTypeEnum, FastJSONSerialization, HessianSerialization
from .util import under_score_to_camel


class InterfaceProxy(object):
    client = None
    interface = None
    service_version = None

    class Method(object):
        def __init__(self, proxy, method):
            self.proxy = proxy
            self.method = method

        def __call__(self, *args, **kwargs):
            return self.proxy.invoke(self.method, *args, **kwargs)

    def __init__(self, client, interface, service_version):
        self.client = client
        self.interface = interface
        self.service_version = service_version

    def invoke(self, method, *args, **kwargs):
        message = RequestMessage()
        message.dubbo_version = "2.6.2"
        message.service_name = self.interface
        message.service_version = self.service_version
        message.method_name = method
        message.method_parameter_types = []
        message.method_arguments = []

        for i in args:
            if not isinstance(i, (JavaObject,)):
                i = JavaObject.parse(i)
            message.method_parameter_types.append(i._class)
            message.method_arguments.append(i)

        request_serialization = FastJSONSerialization()
        message_byte = request_serialization.encode_request(message)

        self.client.connect.send(message_byte)

        response_serialization = HessianSerialization()

        head = self.client.connect.recv(16)
        payload_length = response_serialization.deserialize_head(head)

        payload = b""
        while len(payload) != payload_length:
            payload += self.client.connect.recv(1024)

        response = response_serialization.deserialize_payload(payload)

        if response.type is ResponseTypeEnum.NULL:
            return response.message
        elif response.type is ResponseTypeEnum.VALUE:
            return JavaObject.parse(response.message).value()
        elif response.type is ResponseTypeEnum.EXCEPTION:
            raise GenericException(response.message)
        else:
            raise Exception("dubbo response type undefined")

    def __call__(self, method, *args, **kwargs):
        return self.invoke(method, *args, **kwargs)

    def __getattr__(self, method):
        method = under_score_to_camel(method)
        return self.Method(self, method)


class DubboClient(object):
    connect = None

    def __init__(self, url: str, timeout=5):
        ip, port = url.split(":")
        self.connect = socket.socket()
        self.connect.settimeout(timeout)
        self.connect.connect((ip, int(port)))

    def __del__(self):
        self.connect.close()

    def proxy(self, interface, service_version):
        return InterfaceProxy(self, interface, service_version)
