import random
import json
import dubbo.hessian
import dubbo.common


class Serialization(object):
    magic_high: bytes = 0xda.to_bytes(length=1, byteorder="big")
    magic_low: bytes = 0xbb.to_bytes(length=1, byteorder="big")
    flag: bin = None
    two_way: bin = None
    event: bin = 0b00000000
    serialization_id: bin = None
    status: bytes = 0b00000000.to_bytes(length=1, byteorder="big")
    request_id: bytes = None
    data_length: bytes = None
    variable_part: bytes = None

    __flag_request = 0b10000000
    __flag_response = 0b00000000

    def __init__(self):
        self.request_id = random.randint(0, 4294967295).to_bytes(length=8, byteorder="big")
        self.flag = self.__flag_request
        self.two_way = 0b01000000

    @property
    def magic(self):
        return self.magic_high + self.magic_low

    @property
    def message(self):
        second_position_bin = self.flag | self.two_way | self.event | self.serialization_id
        second_position = second_position_bin.to_bytes(length=1, byteorder="big")

        return self.magic + second_position + self.status + self.request_id + self.data_length + self.variable_part

    def encode(self, message):
        raise Exception()

    def decode(self, message):
        serialization: Serialization = None
        for clazz in Serialization.__subclasses__():
            if clazz.serialization_id == message[2]:
                serialization = clazz()
                break
        if serialization is None: raise Exception("not found serialization")

        serialization.magic_high = message[0]
        serialization.magic_low = message[1]
        serialization.status = message[3]
        serialization.request_id = message[4:12]
        serialization.data_length = message[12:16]
        serialization.variable_part = message[16:16 + int.from_bytes(serialization.data_length, byteorder='big')]
        return serialization.decode(message)


class FastJSONSerialization(Serialization):
    serialization_id = 0b00000110  # 6

    def encode(self, message):
        attachments = {
            "path": message.service_name,
            "interface": message.service_name,
            "version": message.service_version,
            "generic": "true"
        }
        message_list = [
            '"{}"'.format(message.dubbo_version),
            '"{}"'.format(message.service_name),
            '"{}"'.format(message.service_version),
            '"$invoke"',
            '"Ljava/lang/String;[Ljava/lang/String;[Ljava/lang/Object;"',
            '"{}"'.format(message.method_name),
            '[{}]'.format("".join(['"{}"'.format(i) for i in message.method_parameter_types])),
            '[{}]'.format("".join(json.dumps(i, separators=(",", ":")) for i in message.method_arguments)),
            '{}'.format(json.dumps(attachments, separators=(",", ":")))
        ]
        self.variable_part = ("\r\n".join(message_list) + "\r\n").encode("utf-8")
        self.data_length = len(self.variable_part).to_bytes(length=4, byteorder="big")


class HessianSerialization(Serialization):
    serialization_id = 0b00000010  # 2

    def decode(self, message):
        response = dubbo.common.ResponseMessage()

        response.type = dubbo.hessian.Hessian2(self.variable_part[0:1]).decode()

        if response.type == 0:
            exception = dubbo.hessian.Hessian2(self.variable_part[1:]).decode()
            return dubbo.common.GenericException(exception)
        elif response.type == 1:
            result = dubbo.hessian.Hessian2(self.variable_part[1:]).decode()
            return dubbo.common.Response(result)
        elif response.type == 2:
            return None
