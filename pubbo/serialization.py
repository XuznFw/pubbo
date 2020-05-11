import random
import json
from .common import FlagEnum, RequestMessage, ResponseMessage, ResponseTypeEnum, ResponseStatusEnum
from .hessian import Hessian2


class Serialization(object):
    magic_high: bytes = 0xda.to_bytes(length=1, byteorder="big")
    magic_low: bytes = 0xbb.to_bytes(length=1, byteorder="big")
    flag: bin = None
    two_way: bin = None
    event: bin = None
    serialization_id: bin = None
    status: bytes = None
    request_id: bytes = None
    data_length: bytes = None
    variable_part: bytes = None

    @property
    def magic(self):
        return self.magic_high + self.magic_low

    @property
    def message(self):
        second_position_bin = self.flag | self.two_way | self.event | self.serialization_id
        second_position = second_position_bin.to_bytes(length=1, byteorder="big")
        return self.magic + second_position + self.status + self.request_id + self.data_length + self.variable_part

    def encode(self, message):
        if isinstance(message, (RequestMessage,)):
            return self.encode_request(message)
        elif isinstance(message, (ResponseMessage,)):
            raise Exception("todo")
        else:
            raise Exception("oop")

    def decode(self, flag: FlagEnum, message):
        if flag is FlagEnum.REQUEST:
            raise Exception("todo")
        elif flag is FlagEnum.RESPONSE:
            return self.decode_response(message)
        else:
            raise Exception("oop")

    def init_request(self):
        self.flag = FlagEnum.REQUEST.value
        self.two_way = 0b01000000
        self.event = 0b00000000
        self.status = 0b00000000.to_bytes(length=1, byteorder="big")
        self.request_id = random.randint(0, 4294967295).to_bytes(length=8, byteorder="big")

    def encode_request(self, message):
        raise Exception("need to overwrite")

    def decode_response(self, message):
        serialization = None
        for clazz in Serialization.__subclasses__():
            if clazz.serialization_id == message[2]:
                serialization = clazz()
                break
        if serialization is None:
            raise Exception("not found serialization")

        status = ResponseStatusEnum.response_status(message[3])
        if status is not ResponseStatusEnum.OK:
            raise Exception(status.name)

        serialization.magic_high = message[0]
        serialization.magic_low = message[1]
        serialization.status = message[3]
        serialization.request_id = message[4:12]
        serialization.data_length = message[12:16]
        serialization.variable_part = message[16:16 + int.from_bytes(serialization.data_length, byteorder='big')]
        return serialization.decode_response(message)


class HessianSerialization(Serialization):
    serialization_id = 0b00000010  # 2

    def decode_response(self, message):
        response = ResponseMessage()

        response_type = ResponseTypeEnum.response_type(Hessian2(self.variable_part[0:1]).decode())
        response.type = response_type

        if response.type is ResponseTypeEnum.NULL:
            response.message = None
            return response

        response.message = Hessian2(self.variable_part[1:]).decode()
        return response


class FastJSONSerialization(Serialization):
    serialization_id = 0b00000110  # 6

    def encode_request(self, message):
        self.init_request()
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
            '[{}]'.format(",".join(['"{}"'.format(i) for i in message.method_parameter_types])),
            '[{}]'.format(",".join(json.dumps(i, separators=(",", ":")) for i in message.method_arguments)),
            '{}'.format(json.dumps(attachments, separators=(",", ":")))
        ]
        self.variable_part = ("\r\n".join(message_list) + "\r\n").encode("utf-8")
        self.data_length = len(self.variable_part).to_bytes(length=4, byteorder="big")
        return self.message
