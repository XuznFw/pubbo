import inspect
import enum
import types
import time
import datetime
import json
from .util import under_score_to_camel, camel_to_under_score


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
    SERVER_THREAD_POOL_EXHAUSTED_ERROR = 100

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


JAVA_PRIMITIVE_RELATION = {
    bytes: "java.lang.Byte",
    bool: "java.lang.Boolean",
    float: "java.lang.Double",
    int: "java.lang.Integer",
    str: "java.lang.String",
    list: "java.util.List",
    dict: "java.util.Map",
    datetime.datetime: "java.util.Date"
}


class JavaObjectJsonEncoder(json.JSONEncoder):

    def serializable_datetime(self, o):
        return int(time.mktime(o.timetuple())) * 1000

    def serializable_java_class(self, o):
        i = {}
        members = inspect.getmembers(o)
        for member in members:
            name, *_ = member
            if name.startswith("_"): continue
            if isinstance(member[1], (types.FunctionType, types.MethodType,)): continue
            value = getattr(o, name)
            i[name] = value
        return i

    def serializable_java_primitive_class(self, o):
        return o.value()

    def serializable_java_enum(self, o):
        return {"name": o._name}

    def default(self, o):
        relation = {
            datetime.datetime: self.serializable_datetime,
            JavaClass: self.serializable_java_class,
            JavaPrimitiveClass: self.serializable_java_primitive_class,
            JavaEnum: self.serializable_java_enum
        }

        serializable_function = None

        for i in relation.keys():
            if isinstance(o, (i,)):
                serializable_function = relation.get(i)

        if serializable_function is not None:
            return serializable_function(o)
        else:
            return super(JavaObjectJsonEncoder, self).default(o)


class JavaObjectCamelJsonEncoder(JavaObjectJsonEncoder):
    def serializable_java_class(self, o):
        i = {}
        members = inspect.getmembers(o)
        for member in members:
            name, *_ = member
            if name.startswith("_"): continue
            if isinstance(member[1], (
                    types.FunctionType, types.LambdaType, types.CodeType, types.MappingProxyType, types.GeneratorType,
                    types.CoroutineType, types.AsyncGeneratorType, types.MethodType, types.BuiltinFunctionType,
                    types.BuiltinMethodType, types.WrapperDescriptorType, types.MethodWrapperType,
                    types.MethodDescriptorType, types.ClassMethodDescriptorType, types.ModuleType,
                    types.GetSetDescriptorType, types.MemberDescriptorType
            )):
                continue
            value = getattr(o, name)
            name = under_score_to_camel(name)
            i[name] = value
        return i


class JavaObject(object):
    _class = None

    def __init__(self, clazz):
        self._class = clazz

    def __repr__(self):
        return "{}{}".format(self._class, json.dumps(self, cls=JavaObjectJsonEncoder, ensure_ascii=False))

    def is_primitive(self):
        return self._class in JAVA_PRIMITIVE_RELATION.values()

    @staticmethod
    def parse(value):
        if isinstance(value, (dict,)):
            if "class" in value.keys():
                clazz = JavaClass(value.pop("class"))
                for k in value.keys():
                    name = camel_to_under_score(k)
                    setattr(clazz, name, value.get(k))
                return clazz

        # 原生类型
        primitive_class = JAVA_PRIMITIVE_RELATION.get(type(value))
        if primitive_class is not None:
            clazz = JavaPrimitiveClass(primitive_class)
            clazz._value = value
            return clazz

        raise Exception("java object parse error")

    def value(self):
        raise Exception("need to overwrite")


class JavaClass(JavaObject):
    def value(self):
        return self


class JavaPrimitiveClass(JavaObject):
    _value = None

    def __repr__(self):
        return self._value

    def __iter__(self):
        return self._value

    def value(self):
        return self._value


class JavaEnum(JavaObject):
    _name = None

    def __getattr__(self, item):
        self._name = item
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
