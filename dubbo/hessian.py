import util.unicode
import util.clazz

is_binary = lambda x: x == 0x41 or x == 0x42 or 0x20 <= x <= 0x2f or 0x34 <= x <= 0x37
is_boolean = lambda x: x == 0x54 or x == 0x46
is_class_def = lambda x: x == 0x43
is_date = lambda x: x == 0x4a or x == 0x4b
is_double = lambda x: x == 0x44 or x == 0x5b or x == 0x5c or x == 0x5d or x == 0x5e or x == 0x5f
is_int = lambda x: x == 0x49 or 0x80 <= x <= 0xbf or 0xc0 <= x <= 0xcf or 0xd0 <= x <= 0xd7
is_list = lambda x: x == 0x55 or x == 0x56 or x == 0x57 or x == 0x58 or 0x70 <= x <= 0x77 or 0x78 <= x <= 0x7f
is_long = lambda x: x == 0x4c or 0xd8 <= x <= 0xef or 0xf0 <= x <= 0xff or 0x38 <= x <= 0x3f or x == 0x59
is_map = lambda x: x == 0x48 or x == 0x4d
is_null = lambda x: x == 0x4e
is_object = lambda x: x == 0x4f or 0x60 <= x <= 0x6f
is_ref = lambda x: x == 0x51
is_string = lambda x: x == 0x52 or x == 0x53 or 0x00 <= x <= 0x1f or 0x30 <= x <= 0x33


class ClassDef(object):
    name = None
    fields = None

    def __init__(self, name, fields):
        self.name = name
        # 这里很不好 把 Java 中的驼峰风格改为下划线风格 但我就是有强迫症啊
        self.fields = [util.unicode.camel_to_under_score(i) for i in fields]

    def new(self):
        temp = self.name.split(".")
        class_name = temp.pop(-1)
        package = ".".join(temp)

        fields = {i: None for i in self.fields}
        fields["_package"] = package
        c = util.clazz.create_class(class_name, (), fields)
        return c()


class Hessian2(object):
    message = None

    __offset = None
    __class_def = None
    __refs = None

    def __init__(self, message):
        self.message = message
        self.__offset = 0
        self.__class_def = []
        self.__refs = []

    def __move_cursor(self, length):
        self.__offset += length

    @property
    def __code(self):
        return self.message[self.__offset]

    def _decode_binary(self):
        #            # 8-bit binary data split into 64k chunks
        # binary     ::= x41 b1 b0 <binary-data> binary # non-final chunk
        #            ::= 'B' b1 b0 <binary-data>        # final chunk
        #            ::= [x20-x2f] <binary-data>        # binary data of length 0-15
        #            ::= [x34-x37] <binary-data>        # binary data of length 0-1023

        if self.__code == 0x41:
            raise
        elif self.__code == 0x42:
            raise
        elif 0x20 <= self.__code <= 0x2f:
            length = self.__code - 0x20
            self.__move_cursor(1)
            value = self.message[self.__offset:self.__offset + length]
            self.__move_cursor(length)
            return value
        elif 0x34 <= self.__code <= 0x37:
            raise
        else:
            raise

    def _decode_boolean(self):
        #            # boolean true/false
        # boolean    ::= 'T'
        #            ::= 'F'

        if self.__code == 0x54:
            b = True
        elif self.__code == 0x46:
            b = False
        else:
            raise
        self.__move_cursor(1)
        return b

    def _decode_class_def(self):
        #            # definition for an object (compact map)
        # class-def  ::= 'C' string int string*

        self.__move_cursor(1)
        class_name = self._decode_string()
        field_count = self._decode_int()
        fields = [self._decode_string() for _ in range(field_count)]
        class_def = ClassDef(class_name, fields)
        self.__class_def.append(class_def)

        return self._decode_object()

    def _decode_object(self):
        #            # Object instance
        # object     ::= 'O' int value*
        # 	         ::= [x60-x6f] value*

        if self.__code == 0x4f:  # O
            raise
        elif 0x60 <= self.__code <= 0x6f:
            ref_index = self.__code - 0x60
            class_def = self.__class_def[ref_index]
            instance = class_def.new()
            self.__refs.append(instance)
            self.__move_cursor(1)

            for i in class_def.fields:
                value = self._decode_snippet()
                instance.__setattr__(i, value)

            return instance
        else:
            raise

    def _decode_ref(self):
        #            # value reference (e.g. circular trees and graphs)
        # ref        ::= x51 int            # reference to nth map/list/object

        self.__move_cursor(1)
        ref_index = self._decode_int()
        return self.__refs[ref_index]

    def _decode_date(self):
        #            # time in UTC encoded as 64-bit long milliseconds since
        #            #  epoch
        # date       ::= x4a b7 b6 b5 b4 b3 b2 b1 b0
        #            ::= x4b b3 b2 b1 b0       # minutes since epoch

        raise Exception("date")

    def _decode_double(self):
        #            # 64-bit IEEE double
        # double     ::= 'D' b7 b6 b5 b4 b3 b2 b1 b0
        #            ::= x5b                   # 0.0
        #            ::= x5c                   # 1.0
        #            ::= x5d b0                # byte cast to double
        #                                      #  (-128.0 to 127.0)
        #            ::= x5e b1 b0             # short cast to double
        #            ::= x5f b3 b2 b1 b0       # 32-bit float cast to double

        if self.__code == 0x44:
            raise
        elif self.__code == 0x5b:
            self.__move_cursor(1)
            value = 0.0
        elif self.__code == 0x5c:
            raise
        elif self.__code == 0x5d:
            raise
        elif self.__code == 0x5e:
            raise
        elif self.__code == 0x5f:
            raise
        else:
            raise

        return value

    def _decode_int(self):
        #            # 32-bit signed integer
        # int        ::= 'I' b3 b2 b1 b0
        #            ::= [x80-xbf]             # -x10 to x3f
        #            ::= [xc0-xcf] b0          # -x800 to x7ff
        #            ::= [xd0-xd7] b1 b0       # -x40000 to x3ffff

        if 0x80 <= self.__code <= 0xbf:
            value = self.__code - 0x90
            self.__move_cursor(1)
        elif 0xc0 <= self.__code <= 0xcf:
            value = ((self.__code - 0xc8) << 8) + self.message[self.__offset + 1]
            self.__move_cursor(2)
        else:
            raise Exception()
        return value

    def _decode_list(self):
        #            # list/vector
        # list       ::= x55 type value* 'Z'   # variable-length list
        # 	         ::= 'V' type int value*   # fixed-length list
        #            ::= x57 value* 'Z'        # variable-length untyped list
        #            ::= x58 int value*        # fixed-length untyped list
        # 	         ::= [x70-77] type value*  # fixed-length typed list
        # 	         ::= [x78-7f] value*       # fixed-length untyped list

        result = []
        self.__refs.append(result)
        if self.__code == 0x55:
            raise
        elif self.__code == 0x56:  # V
            self.__move_cursor(1)
            type = self._decode_snippet()
            length = self.__code - 0x90
            self.__move_cursor(1)
            for _ in range(length):
                result.append(self._decode_snippet())
        elif self.__code == 0x57:
            raise
        elif self.__code == 0x58:
            self.__move_cursor(1)
            length = self._decode_int()
            for i in range(length):
                result.append(self._decode_snippet())
        elif 0x70 <= self.__code <= 0x77:
            length = self.__code - 0x70
            self.__move_cursor(1)
            type = self._decode_snippet()
            for _ in range(length):
                result.append(self._decode_snippet())
        elif 0x78 <= self.__code <= 0x7f:
            raise
        else:
            raise
        return result

    def _decode_long(self):
        #            # 64-bit signed long integer
        # long       ::= 'L' b7 b6 b5 b4 b3 b2 b1 b0
        #            ::= [xd8-xef]             # -x08 to x0f
        #            ::= [xf0-xff] b0          # -x800 to x7ff
        #            ::= [x38-x3f] b1 b0       # -x40000 to x3ffff
        #            ::= x59 b3 b2 b1 b0       # 32-bit integer cast to long

        raise Exception("long")

    def _decode_map(self):
        #            # map/object
        # map        ::= 'M' type (value value)* 'Z'  # key, value map pairs
        # 	         ::= 'H' (value value)* 'Z'       # untyped key, value

        values = []
        map = dict()
        self.__refs.append(map)

        if self.__code == 0x4d:  # M
            self.__move_cursor(1)
            type = self._decode_snippet()
        elif self.__code == 0x48:  # H
            self.__move_cursor(1)

        while self.__code != 0x5a:
            values.append(self._decode_snippet())
        self.__move_cursor(1)

        for i in range(int(len(values) / 2)):
            key, value = values[i * 2], values[i * 2 + 1]
            map[key] = value

        return map

    def _decode_null(self):
        #            # null value
        # null       ::= 'N'

        self.__move_cursor(1)
        return None

    def _decode_string(self):
        #            # UTF-8 encoded character string split into 64k chunks
        # string     ::= x52 b1 b0 <utf8-data> string  # non-final chunk
        #            ::= 'S' b1 b0 <utf8-data>         # string of length   0-65535
        #            ::= [x00-x1f] <utf8-data>         # string of length   0-31
        #            ::= [x30-x33] b0 <utf8-data>      # string of length   0-1023

        if self.__code == 0x52:
            raise
        elif self.__code == 0x53:
            raise
        elif 0x00 <= self.__code <= 0x1f:
            count = self.__code
            self.__move_cursor(1)
        elif 0x30 <= self.__code <= 0x33:
            self.__move_cursor(1)
            count = self.__code
            self.__move_cursor(1)
        else:
            raise
        string = []
        for i in range(count):
            length = util.unicode.byte_length(self.__code)
            string.append(str(self.message[self.__offset:self.__offset + length], encoding="utf-8"))
            self.__move_cursor(length)
        return "".join(string)

    def _decode_snippet(self):

        relation = {
            is_binary: self._decode_binary,
            is_boolean: self._decode_boolean,
            is_class_def: self._decode_class_def,
            is_date: self._decode_date,
            is_double: self._decode_double,
            is_int: self._decode_int,
            is_list: self._decode_list,
            is_long: self._decode_long,
            is_map: self._decode_map,
            is_null: self._decode_null,
            is_object: self._decode_object,
            is_ref: self._decode_ref,
            is_string: self._decode_string
        }

        for i in relation.keys():
            if i(self.__code) is True:
                function = relation.get(i)
                value = function()
                return value
        raise Exception("have unkown flag")

    def decode(self):
        value = self._decode_snippet()

        if self.__offset < len(self.message):
            raise Exception("parse error")

        return value
