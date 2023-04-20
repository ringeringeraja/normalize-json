import typing
import re
import json
import dateutil.parser as dateparser

TYPE_MAPPING = {
    'text': 'str',
    'string': 'str',
    'select': 'str',
    'datetime': 'datetime',
    'number': 'float',
    'integer': 'int',
    'objectid': 'ObjectId',
    'boolean': 'bool'
}

FIELDS_KEY='__fields'

def _normalize_translation_table(obj: dict):
    table = {}
    entry = obj.get(FIELDS_KEY)

    if entry:
        table = { k: v for k, v in obj.items() if k != FIELDS_KEY }
        table[FIELDS_KEY] = _normalize_translation_table(obj[FIELDS_KEY])
        return table

    for k, v in obj.items():
        if type(v) == dict:
            if FIELDS_KEY in v:
                table[k] = {
                    **v,
                    FIELDS_KEY: _normalize_translation_table(v[FIELDS_KEY])
                }
                continue

        if type(v) == str:
            table[k] = {
                'map': v,
                'type': 'text'
            }
            continue

        table[k] = {
            **v,
            'type': v.get('type', 'text')
        }
    return table

def serialize(raw: dict|str|bytes, mime: typing.Literal['json']):
    if mime == 'json':
        if isinstance(raw, dict): return raw
        if isinstance(raw, bytes) or isinstance(raw, str):
            try:
                return json.loads(raw)
            except:
                raise TypeError('non-serializable string starting with: {}'.format(raw[:20]))

def _flatten(obj, acc:str|None=None, res:dict={}, separator: str='.'):
    if type(obj) == list:
        return [ _flatten(e, None, {}, separator=separator) for e in obj ]

    if type(obj) != dict:
        return obj

    for k, v in obj.items():
        flat = f'{acc}{separator}{k}' if acc else k
        if type(v) == dict: _flatten(v, flat, res, separator=separator)
        elif type(v) == list: res[flat] = [ _flatten(e, None, {}, separator=separator) for e in v ]
        else: res[flat] = v

    return res

def flatten(obj:dict, separator:str = '.'):
    return _flatten(obj, None, {}, separator=separator)

def translate(obj, table:dict, acc:dict = {}, parent:str|None = None, switches:dict = {}):
    if type(obj) == str:
        try:
            has = lambda x : x == obj if type(x) is str else obj in x
            return [ k for k, v in table[FIELDS_KEY].items() if has(v) ][0]
        except IndexError:
            raise IndexError(f'{obj} doesnt exist in {table}')

    if type(obj) == dict:
        ret = {}
        table_entry = _normalize_translation_table(table)
        table_entry = table_entry[FIELDS_KEY]

        get_switch = lambda x : table.get(x, switches.get(x, False))
        switches = {
            k: get_switch(k)
            for k in [
                'array',
                'strict',
                'reverse',
                'default_null',
                'type',
                'enforce'
            ]
        }

        for k, v in table_entry.items():
            # ensure that types won't be inherited
            for _k, _v in filter(lambda x : x[0] != 'type', switches.items()):
                switches[_k] = v.get(_k, _v)

            strict, reverse, default_null, vtype, trim_start, trim_end = (
                switches['strict'],
                switches['reverse'],
                switches['default_null'],
                switches['type'] or v.get('type'),
                v.get('trim_start'),
                v.get('trim_end')
            )

            if v == '': continue
            v['type'] = vtype

            k, symbols = re.findall('([^<!/#]+)(.*)', k)[0]
            symbols = list(symbols)

            if '<' in symbols or reverse:
                reverse=True
                _ = v['map']
                v['map'] = k
                k = _

            mapped_name = v.get('map')
            value = None
            array_base = None

            if mapped_name:
                array_base = re.compile(r'\[(\w+)?\]\.?').split(mapped_name)
                for n in (mapped_name if type(mapped_name) is list else mapped_name.split('|')):
                    if not value:
                        mapped_name = n
                        value = obj.get(array_base[0])

            if '!' in symbols: strict=True
            if '/' in symbols and value: value = value.split(' ')[0]
            if '#' in symbols and value:
                vtype = 'integer'
                switches['enforce'] = True

            # plain value
            if FIELDS_KEY not in v:
                if type(mapped_name) is str:
                    if array_base and len(array_base) == 3:
                        _, idx, field = array_base

                        if type(ret) != list and idx == None:
                            ret = acc.get(parent) \
                                if type(parent) == object \
                                else [ {} for _ in range(len(value or [])) ]

                        if idx != None:
                            if isinstance(value, list) and isinstance(ret, dict):
                                ret[k] = value[int(idx)][field]
                            continue

                        for i, e in enumerate(value or []):
                            if isinstance(ret, list):
                                ret[i][k] = e[field]
                        continue

                if mapped_name == '{}':
                    if isinstance(ret, list): ret = [ { **r, k: {} } for r in ret ]
                    elif isinstance(ret, dict): ret[k] = '{}'
                    continue

                ts = lambda i : i.__class__.__name__

                if not value:
                    if 'default' in v or default_null:
                        value = v.get('default', None)
                        vtype = ts(value)
                    else:
                        if strict: raise ValueError('({}) required value'.format(mapped_name))
                        continue

                if isinstance(value, str):
                    if trim_start: value = value[trim_start*-1:]
                    if trim_end: value = str(value)[:trim_end]

                if switches.get('array') and not vtype:
                    vtype = ts(value)

                if switches.get('enforce'):
                    if vtype in ['number', 'integer'] and type(value) == str:
                        value = re.sub(r'[^0-9]', '', value) or '0'

                    match vtype:
                        case 'number': value = float(value)
                        case 'integer': value = int(value)
                        case 'text': value = str(value)
                        case 'datetime': value = dateparser.parse(value)

                actual = ts(value)
                expected = TYPE_MAPPING.get(str(vtype), vtype)

                if actual != expected and not (actual == 'NoneType' and default_null):
                    raise TypeError('({}) expected type: {}, got: {}'.format(mapped_name, expected, actual))

                if isinstance(ret, dict):
                    ret[k] = value

            else:
                child = obj[mapped_name] if mapped_name else obj
                if isinstance(ret, dict):
                    res = translate(child, v, ret, k, switches)
                    ret[k] = res
                    continue

        return ret

    elif type(obj) == list:
        table_entry = _normalize_translation_table(table)
        table_entry = table_entry[FIELDS_KEY]

        if table.get('array') != True:
            raise TypeError('illegal array: ' + str(table))

        return [
            translate(i, table, switches=switches)
            for i in obj
        ]

