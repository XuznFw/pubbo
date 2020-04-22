import inspect
import enum
import util.unicode

FlagEnum = enum.Enum("FlagEnum", ("REQUEST", "RESPONSE"))


class ResponseTypeEnum(enum.Enum):
    EXCEPTION = 0
    NULL = 2


class RequestMessage(object):
    dubbo_version = None
    service_name = None
    service_version = None
    method_name = None
    method_parameter_types = []
    method_arguments = []


class ResponseMessage(object):
    type = None
    message = None


class BaseModel(object):
    def __iter__(self):
        i = []
        members = inspect.getmembers(self)
        for member in members:
            name, *_ = member
            if name.startswith("_"): continue
            value = getattr(self, name)
            if isinstance(value, (Parameter,)):
                value = dict(value)

            name = util.unicode.under_score_to_camel(name)  # 下划线转驼峰
            i.append([name, value])
        return iter(i)


class Parameter(BaseModel):
    _class = None

    def __init__(self, clazz):
        self._class = clazz


class Response(BaseModel):
    def __init__(self, response: dict):
        for k in response.keys():
            v = response.get(k)
            if isinstance(v, (dict,)):
                v = Response(v)

            name = util.unicode.camel_to_under_score(k)
            if name == "class": name = "_class"
            setattr(self, name, v)


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