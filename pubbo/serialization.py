import random
import json
from .common import ResponseMessage, ResponseTypeEnum, ResponseStatusEnum, JavaObjectCamelJsonEncoder
from .hessian import Hessian2Deserializer

REQUEST_FLAG = 0b10000000
RESPONSE_FLAG = 0b00000000


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

    def init_request(self):
        self.flag = REQUEST_FLAG
        self.two_way = 0b01000000
        self.event = 0b00000000
        self.status = 0b00000000.to_bytes(length=1, byteorder="big")
        self.request_id = random.randint(0, 4294967295).to_bytes(length=8, byteorder="big")


class HessianSerialization(Serialization):
    serialization_id = 0b00000010  # 2

    def deserialize_head(self, message):

        if len(message) != 16:
            raise Exception("error dubbo response head")

        status = ResponseStatusEnum.response_status(message[3])
        if status is not ResponseStatusEnum.OK:
            raise Exception(status.name)

        self.magic_high = message[0]
        self.magic_low = message[1]
        self.status = message[3]
        self.request_id = message[4:12]
        self.data_length = message[12:16]

        payload_length = int.from_bytes(message[12:16], byteorder='big')
        return payload_length

    def deserialize_payload(self, message):

        payload_length = int.from_bytes(self.data_length, byteorder='big')
        assert payload_length == len(message)

        response = ResponseMessage()
        response.type = ResponseTypeEnum.response_type(Hessian2Deserializer(message[0:1]).deserialize())

        if response.type is ResponseTypeEnum.NULL:
            response.message = None
            return response

        response.message = Hessian2Deserializer(message[1:]).deserialize()
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
            '[{}]'.format(",".join(json.dumps(
                i, cls=JavaObjectCamelJsonEncoder, separators=(",", ":")
            ) for i in message.method_arguments)),
            '{}'.format(json.dumps(attachments, separators=(",", ":")))
        ]
        self.variable_part = ("\r\n".join(message_list) + "\r\n").encode("utf-8")
        self.data_length = len(self.variable_part).to_bytes(length=4, byteorder="big")
        return self.message
