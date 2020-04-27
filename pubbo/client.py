import socket
from .common import JavaObject, GenericException
from .serialization import RequestMessage, ResponseTypeEnum, Serialization, FastJSONSerialization
from .util import under_score_to_camel


class InterfaceProxy(object):
    client = None
    interface = None

    class Method(object):
        def __init__(self, proxy, method):
            self.proxy = proxy
            self.method = method

        def __call__(self, *args, **kwargs):
            return self.proxy.invoke(self.method, *args, **kwargs)

    def __init__(self, client, interface):
        self.client = client
        self.interface = interface

    def invoke(self, method, *args, **kwargs):
        message = RequestMessage()
        message.dubbo_version = "2.6.2"
        message.service_name = self.interface
        message.service_version = "1.0.0"
        message.method_name = method
        message.method_parameter_types = []
        message.method_arguments = []

        for i in args:
            if not isinstance(i, (JavaObject,)):
                i = JavaObject.parse(i)
            message.method_parameter_types.append(i._class)
            message.method_arguments.append(i.dubbo_value())

        message = FastJSONSerialization().encode_request(message)

        self.client.connect.send(message)

        response = b""
        while True:
            # TODO 处理恰好是这个size的情况
            chunk = self.client.connect.recv(1024)
            response += chunk
            if len(chunk) < 1024:
                break

        response = Serialization().decode_response(response)

        if response.type is ResponseTypeEnum.NULL:
            return response.message
        elif response.type is ResponseTypeEnum.VALUE:
            return JavaObject.parse(response.message).python_value()
        elif response.type is ResponseTypeEnum.EXCEPTION:
            raise GenericException(response.message)
        else:
            raise Exception("oop")

    def __call__(self, method, *args, **kwargs):
        return self.invoke(method, *args, **kwargs)

    def __getattr__(self, method):
        method = under_score_to_camel(method)
        return self.Method(self, method)


class DubboClient(object):
    connect = None

    def __init__(self, url: str):
        ip, port = url.split(":")
        self.connect = socket.socket()
        self.connect.connect((ip, int(port)))

    def __del__(self):
        self.connect.close()

    def proxy(self, interface):
        return InterfaceProxy(self, interface)
