import orjson


class ORJSONEncoder:
    @staticmethod
    def encode(o):
        return orjson.dumps(o)


class ORJSONDecoder:
    @staticmethod
    def decode(s):
        return orjson.loads(s)
