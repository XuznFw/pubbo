import datetime
from .common import JavaClass
from .util import camel_to_under_score


class ClassDef(object):
    name = None
    fields = None

    def __init__(self, name, fields):
        self.name = name
        # 这里很不好 把 Java 中的驼峰风格改为下划线风格 但我就是有强迫症啊
        self.fields = [camel_to_under_score(i) for i in fields]

    def new(self):
        o = JavaClass(self.name)

        for i in self.fields:
            o.__setattr__(i, None)

        return o


deserialize_relation = {}


def register(condition):
    def decorator(function):
        deserialize_relation.update({condition: function})

        def wrapper(self, *args, **kwargs):
            return function(self, *args, **kwargs)

        return wrapper

    return decorator


class Hessian2Deserializer(object):
    message = None

    cursor = 0

    class_def = []
    refs = []

    def __init__(self, message):
        self.message = message
        self.cursor = 0
        self.class_def, self.refs = [], []

    @property
    def code(self):
        return self.message[self.cursor]

    def move_cursor(self, scale):
        self.cursor += scale

    def move_one_scale(self):
        code = self.code
        self.move_cursor(1)
        return code

    @register(lambda x: x == 0x41 or x == 0x42 or 0x20 <= x <= 0x2f or 0x34 <= x <= 0x37)
    def deserialize_binary(self):
        #            # 8-bit binary data split into 64k chunks
        # binary     ::= x41 b1 b0 <binary-data> binary # non-final chunk
        #            ::= 'B' b1 b0 <binary-data>        # final chunk
        #            ::= [x20-x2f] <binary-data>        # binary data of length 0-15
        #            ::= [x34-x37] <binary-data>        # binary data of length 0-1023

        code = self.move_one_scale()

        if code == 0x41:
            b1 = self.move_one_scale()
            b0 = self.move_one_scale()
            scale = (b1 << 8) + b0
        elif code == 0x42:
            b1 = self.move_one_scale()
            b0 = self.move_one_scale()
            scale = (b1 << 8) + b0
        elif 0x20 <= code <= 0x2f:
            scale = code - 0x20
        elif 0x34 <= code <= 0x37:
            b0 = self.move_one_scale()
            scale = ((code - 0x34) << 8) + b0
        else:
            raise Exception("oop")

        value = self.message[self.cursor:self.cursor + scale]
        self.move_cursor(scale)
        return value

    @register(lambda x: x == 0x54 or x == 0x46)
    def deserialize_boolean(self):
        #            # boolean true/false
        # boolean    ::= 'T'
        #            ::= 'F'

        relation = {0x54: True, 0x46: False}

        code = self.move_one_scale()
        value = relation.get(code)

        if value is None:
            raise Exception("oop")
        return value

    @register(lambda x: x == 0x43)
    def deserialize_class_def(self):
        #            # definition for an object (compact map)
        # class-def  ::= 'C' string int string*

        self.move_one_scale()
        class_name = self.deserialize_string()
        field_count = self.deserialize_int()
        fields = [self.deserialize_string() for _ in range(field_count)]
        class_def = ClassDef(class_name, fields)
        self.class_def.append(class_def)

        return self.deserialize_object()

    @register(lambda x: x == 0x4f or 0x60 <= x <= 0x6f)
    def deserialize_object(self):
        #            # Object instance
        # object     ::= 'O' int value*
        # 	         ::= [x60-x6f] value*
        code = self.move_one_scale()

        if code == 0x4f:  # O
            ref_index = self.deserialize_int()
        elif 0x60 <= code <= 0x6f:
            ref_index = code - 0x60
        else:
            raise Exception("oop")

        class_def = self.class_def[ref_index]
        instance = class_def.new()
        self.refs.append(instance)

        for i in class_def.fields:
            value = self.deserialize()
            instance.__setattr__(i, value)

        return instance

    @register(lambda x: x == 0x51)
    def deserialize_ref(self):
        #            # value reference (e.g. circular trees and graphs)
        # ref        ::= x51 int            # reference to nth map/list/object

        self.move_one_scale()
        ref_index = self.deserialize_int()
        return self.refs[ref_index]

    @register(lambda x: x == 0x4a or x == 0x4b)
    def deserialize_date(self):
        #            # time in UTC encoded as 64-bit long milliseconds since
        #            #  epoch
        # date       ::= x4a b7 b6 b5 b4 b3 b2 b1 b0
        #            ::= x4b b3 b2 b1 b0       # minutes since epoch

        code = self.move_one_scale()
        if code == 0x4a:
            b7 = self.move_one_scale()
            b6 = self.move_one_scale()
            b5 = self.move_one_scale()
            b4 = self.move_one_scale()
            b3 = self.move_one_scale()
            b2 = self.move_one_scale()
            b1 = self.move_one_scale()
            b0 = self.move_one_scale()
            value = (b7 << 56) + (b6 << 48) + (b5 << 40) + (b4 << 32) + (b3 << 24) + (b2 << 16) + (b1 << 8) + b0
        elif code == 0x4b:
            b3 = self.move_one_scale()
            b2 = self.move_one_scale()
            b1 = self.move_one_scale()
            b0 = self.move_one_scale()
            value = ((b3 << 24) + (b2 << 16) + (b1 << 8) + b0) * 60000
        else:
            raise Exception("oop")

        return datetime.datetime.fromtimestamp(value / 1000)

    @register(lambda x: x == 0x44 or x == 0x5b or x == 0x5c or x == 0x5d or x == 0x5e or x == 0x5f)
    def deserialize_double(self):
        #            # 64-bit IEEE double
        # double     ::= 'D' b7 b6 b5 b4 b3 b2 b1 b0
        #            ::= x5b                   # 0.0
        #            ::= x5c                   # 1.0
        #            ::= x5d b0                # byte cast to double  (-128.0 to 127.0)
        #            ::= x5e b1 b0             # short cast to double
        #            ::= x5f b3 b2 b1 b0       # 32-bit float cast to double

        code = self.move_one_scale()

        if code == 0x44:
            b7 = self.move_one_scale()
            b6 = self.move_one_scale()
            b5 = self.move_one_scale()
            b4 = self.move_one_scale()
            b3 = self.move_one_scale()
            b2 = self.move_one_scale()
            b1 = self.move_one_scale()
            b0 = self.move_one_scale()
            value = (b7 << 56) + (b6 << 48) + (b5 << 40) + (b4 << 32) + (b3 << 24) + (b2 << 16) + (b1 << 8) + b0
        elif code == 0x5b:
            value = 0.0
        elif code == 0x5c:
            value = 1.0
        elif code == 0x5d:
            b0 = self.move_one_scale()
            value = b0
        elif code == 0x5e:
            b1 = self.move_one_scale()
            b0 = self.move_one_scale()
            value = (b1 << 8) + b0
        elif code == 0x5f:
            b3 = self.move_one_scale()
            b2 = self.move_one_scale()
            b1 = self.move_one_scale()
            b0 = self.move_one_scale()
            value = (b3 << 24) + (b2 << 16) + (b1 << 8) + b0 * 0.001
        else:
            raise Exception("oop")
        return value

    @register(lambda x: x == 0x49 or 0x80 <= x <= 0xbf or 0xc0 <= x <= 0xcf or 0xd0 <= x <= 0xd7)
    def deserialize_int(self):
        #            # 32-bit signed integer
        # int        ::= 'I' b3 b2 b1 b0
        #            ::= [x80-xbf]             # -x10 to x3f
        #            ::= [xc0-xcf] b0          # -x800 to x7ff
        #            ::= [xd0-xd7] b1 b0       # -x40000 to x3ffff

        code = self.move_one_scale()

        if code == 0x49:
            b3 = self.move_one_scale()
            b2 = self.move_one_scale()
            b1 = self.move_one_scale()
            b0 = self.move_one_scale()
            value = (b3 << 24) + (b2 << 16) + (b1 << 8) + b0
        elif 0x80 <= code <= 0xbf:
            value = code - 0x90
        elif 0xc0 <= code <= 0xcf:
            b0 = self.move_one_scale()
            value = ((code - 0xc8) << 8) + b0
        elif 0xd0 <= code <= 0xd7:
            b1 = self.move_one_scale()
            b0 = self.move_one_scale()
            value = ((code - 0xd4) << 16) + (b1 << 8) + b0
        else:
            raise Exception("oop")
        return value

    @register(lambda x: x == 0x55 or x == 0x56 or x == 0x57 or x == 0x58 or 0x70 <= x <= 0x77 or 0x78 <= x <= 0x7f)
    def deserialize_list(self):
        #            # list/vector
        # list       ::= x55 type value* 'Z'   # variable-length list
        # 	         ::= 'V' type int value*   # fixed-length list
        #            ::= x57 value* 'Z'        # variable-length untyped list
        #            ::= x58 int value*        # fixed-length untyped list
        # 	         ::= [x70-77] type value*  # fixed-length typed list
        # 	         ::= [x78-7f] value*       # fixed-length untyped list

        code = self.move_one_scale()

        result = []
        self.refs.append(result)

        if code == 0x55:
            type = self.deserialize()
            while self.code != 0x5a:
                result.append(self.deserialize())
            self.move_one_scale()
        elif code == 0x56:  # V
            type = self.deserialize()
            length = self.move_one_scale() - 0x90
            for _ in range(length):
                result.append(self.deserialize())
        elif code == 0x57:
            while self.code != 0x5a:
                result.append(self.deserialize())
            self.move_one_scale()
        elif code == 0x58:
            length = self.deserialize_int()
            for i in range(length):
                result.append(self.deserialize())
        elif 0x70 <= code <= 0x77:
            length = code - 0x70
            type = self.deserialize()
            for _ in range(length):
                result.append(self.deserialize())
        elif 0x78 <= code <= 0x7f:
            length = code - 0x78
            for _ in range(length):
                result.append(self.deserialize())
        else:
            raise Exception("oop")
        return result

    @register(lambda x: x == 0x4c or 0xd8 <= x <= 0xef or 0xf0 <= x <= 0xff or 0x38 <= x <= 0x3f or x == 0x59)
    def deserialize_long(self):
        #            # 64-bit signed long integer
        # long       ::= 'L' b7 b6 b5 b4 b3 b2 b1 b0
        #            ::= [xd8-xef]             # -x08 to x0f
        #            ::= [xf0-xff] b0          # -x800 to x7ff
        #            ::= [x38-x3f] b1 b0       # -x40000 to x3ffff
        #            ::= x59 b3 b2 b1 b0       # 32-bit integer cast to long

        code = self.move_one_scale()

        if code == 0x4c:
            b7 = self.move_one_scale()
            b6 = self.move_one_scale()
            b5 = self.move_one_scale()
            b4 = self.move_one_scale()
            b3 = self.move_one_scale()
            b2 = self.move_one_scale()
            b1 = self.move_one_scale()
            b0 = self.move_one_scale()
            value = (b7 << 56) + (b6 << 48) + (b5 << 40) + (b4 << 32) + (b3 << 24) + (b2 << 16) + (b1 << 8) + b0
        elif 0xd8 <= code <= 0xef:
            value = code - 0xe0
        elif 0xf0 <= code <= 0xff:
            b0 = self.move_one_scale()
            value = ((code - 0xf8) << 8) + b0
        elif 0x38 <= code <= 0x3f:
            b1 = self.move_one_scale()
            b0 = self.move_one_scale()
            value = ((code - 0x3c) << 16) + (b1 << 8) + b0
        elif code == 0x59:
            b3 = self.move_one_scale()
            b2 = self.move_one_scale()
            b1 = self.move_one_scale()
            b0 = self.move_one_scale()
            value = (b3 << 24) + (b2 << 16) + (b1 << 8) + b0
        else:
            raise Exception("oop")

        return value

    @register(lambda x: x == 0x48 or x == 0x4d)
    def deserialize_map(self):
        #            # map/object
        # map        ::= 'M' type (value value)* 'Z'  # key, value map pairs
        # 	         ::= 'H' (value value)* 'Z'       # untyped key, value

        code = self.move_one_scale()

        values = []
        map = dict()
        self.refs.append(map)

        if code == 0x4d:  # M
            type = self.deserialize()
        elif code == 0x48:  # H
            pass

        while self.code != 0x5a:
            values.append(self.deserialize())
        self.move_one_scale()

        for i in range(int(len(values) / 2)):
            key, value = values[i * 2], values[i * 2 + 1]
            map[key] = value

        return map

    @register(lambda x: x == 0x4e)
    def deserialize_null(self):
        self.move_one_scale()
        return None

    @register(lambda x: x == 0x52 or x == 0x53 or 0x00 <= x <= 0x1f or 0x30 <= x <= 0x33)
    def deserialize_string(self):
        #            # UTF-8 encoded character string split into 64k chunks
        # string     ::= x52 b1 b0 <utf8-data> string  # non-final chunk
        #            ::= 'S' b1 b0 <utf8-data>         # string of length   0-65535
        #            ::= [x00-x1f] <utf8-data>         # string of length   0-31
        #            ::= [x30-x33] b0 <utf8-data>      # string of length   0-1023

        # 嗅探 utf-8 使用的 byte 长度
        def sniff_utf8_length(flag):
            flag = format(flag, "#010b")

            if flag.startswith("0b0") or flag.startswith("0b10"):
                return 1
            elif flag.startswith("0b110"):
                return 2
            elif flag.startswith("0b1110"):
                return 3
            elif flag.startswith("0b11110"):
                return 4
            else:
                raise Exception("oop")

        code = self.move_one_scale()

        if code == 0x52 or code == 0x53:
            b1 = self.move_one_scale()
            b0 = self.move_one_scale()
            count = (b1 << 8) + b0
        elif 0x00 <= code <= 0x1f:
            count = code
        elif 0x30 <= code <= 0x33:
            b0 = self.move_one_scale()
            count = ((code - 0x30) << 8) + b0
        else:
            raise Exception("oop")

        string = []
        for i in range(count):
            length = sniff_utf8_length(self.code)
            string.append(str(self.message[self.cursor:self.cursor + length], encoding="utf-8"))
            self.move_cursor(length)

        if code == 0x52:
            tail = self.deserialize_string()
            string.append(tail)

        return "".join(string)

    def deserialize(self):
        for condition in deserialize_relation.keys():
            if condition(self.code) is True:
                function = deserialize_relation.get(condition)
                value = function(self)
                return value
        else:
            raise Exception("have unkown hessian 2 code")
