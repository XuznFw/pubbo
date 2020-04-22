import socket
from dubbo.common import *
from dubbo.serialization import *
import util.unicode


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
            message.method_parameter_types.append(i._class)
            message.method_arguments.append(dict(i))

        serizlization = FastJSONSerialization()
        serizlization.encode(message)

        self.client.connect.send(serizlization.message)

        response = self.client.connect.recv(1024 * 4)
        response = Serialization().decode(response)

        if isinstance(response, (Exception,)):
            raise response
        else:
            return response

    def __call__(self, method, *args, **kwargs):
        return self.invoke(method, *args, **kwargs)

    def __getattr__(self, method):
        method = util.unicode.under_score_to_camel(method)
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
