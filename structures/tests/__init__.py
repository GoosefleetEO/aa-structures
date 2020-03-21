import json


def to_json(obj):
    return json.dumps(obj, sort_keys=True)
