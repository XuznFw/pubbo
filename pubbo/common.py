import inspect
import enum
import types
import time
import datetime
from .util import under_score_to_camel, camel_to_under_score


class FlagEnum(enum.Enum):
    REQUEST = 0b10000000
    RESPONSE = 0b00000000


class ResponseStatusEnum(enum.Enum):
    OK = 20
    CLIENT_TIMEOUT = 30
    SERVER_TIMEOUT = 31
    BAD_REQUEST = 40
    BAD_RESPONSE = 50
    SERVICE_NOT_FOUND = 60
    SERVICE_ERROR = 70
    SERVER_ERROR = 80
    CLIENT_ERROR = 90
    SERVER_THREADPOOL_EXHAUSTED_ERROR = 100

    @staticmethod
    def response_status(value):
        for i in ResponseStatusEnum.__members__.values():
            if value == i.value:
                return i
        raise Exception("not found response status")


class ResponseTypeEnum(enum.Enum):
    EXCEPTION = 0
    VALUE = 1
    NULL = 2

    @staticmethod
    def response_type(value):
        for i in ResponseTypeEnum.__members__.values():
            if value == i.value:
                return i
        raise Exception("not found response type")


class Message(object):
    pass


class RequestMessage(Message):
    dubbo_version = None
    service_name = None
    service_version = None
    method_name = None
    method_parameter_types = []
    method_arguments = []


class ResponseMessage(Message):
    type = None
    message = None


class JavaObject(object):
    _class = None
    _value = None

    _primitive_relation = {
        bytes: "java.lang.Byte",
        bool: "java.lang.Boolean",
        float: "java.lang.Double",
        int: "java.lang.Integer",
        str: "java.lang.String",
        list: "java.util.List",
        dict: "java.util.Map",
        datetime.datetime: "java.util.Date"
    }

    def __init__(self, clazz):
        self._class = clazz

    @staticmethod
    def parse(value):
        clazz = JavaObject._primitive_relation.get(type(value))
        if isinstance(value, (dict,)):
            if "class" in value.keys():
                clazz = value.pop("class")

        if clazz is None:
            raise Exception("java object parse error")

        java_object = JavaObject(clazz)
        java_object._class = clazz

        if java_object.is_primitive():
            java_object._value = value
        else:
            for k in value.keys():
                v = value.get(k)
                name = camel_to_under_score(k)
                setattr(java_object, name, v)
        return java_object

    def is_primitive(self):
        return self._class in self._primitive_relation.values()

    def dubbo_value(self):
        if self.is_primitive():
            if type(self._value) is bytes:
                value = str(self._value, encoding="utf-8")
            else:
                value = self._value
            return value

        i = {"class": self._class}

        members = inspect.getmembers(self)
        for member in members:
            name, *_ = member
            if name.startswith("_"): continue
            if isinstance(member[1], (types.FunctionType, types.MethodType,)): continue
            value = getattr(self, name)
            if isinstance(value, (JavaObject,)):
                value = value.dubbo_value()
            name = under_score_to_camel(name)
            if isinstance(value, (datetime.datetime,)):
                value = int(time.mktime(value.timetuple())) * 1000
            i[name] = value
        return i

    def python_value(self):
        if self.is_primitive():
            return self._value
        return self


class GenericException(Exception):
    cause = None
    detail_message = None
    exception_class = None
    exception_message = None
    stack_trace = None
    suppressed_exceptions = None

    def __init__(self, exception):
        self.cause = exception.cause
        self.detail_message = exception.detail_message
        self.exception_class = exception.exception_class
        self.exception_message = exception.exception_message
        self.stack_trace = exception.stack_trace
        self.suppressed_exceptions = exception.suppressed_exceptions

    def __repr__(self):
        return self.exception_message

    def __str__(self):
        return self.__repr__()
