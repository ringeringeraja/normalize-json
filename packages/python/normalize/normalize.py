import re
import json
import dateutil.parser as dateparser

type_mapping = {
    'text': 'str',
    'string': 'str',
    'select': 'str',
    'datetime': 'datetime',
    'number': 'float',
    'integer': 'int',
    'objectid': 'ObjectId',
    'boolean': 'bool'
}

class Normalize:
    fields_key='__fields'

    def _transform_each(self, entry: dict):
        return entry

    def transform_each(self, entry: dict):
        return self._transform_each(entry)

    @classmethod
    def _normalize_translation_table(cls, obj: dict):
        table = {}
        entry = obj.get(cls.fields_key)

        if entry:
            table = { k: v for k, v in obj.items() if k != cls.fields_key }
            table[cls.fields_key] = cls._normalize_translation_table(obj[cls.fields_key])
            return table

        for k, v in obj.items():
            if type(v) == dict:
                if cls.fields_key in v:
                    table[k] = {
                        **v,
                        cls.fields_key: cls._normalize_translation_table(v[cls.fields_key])
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

    @staticmethod
    def serialize(raw: str, mime: str):
        if mime == 'json':
            return raw if type(raw) == dict else json.loads(raw)

    @classmethod
    def _flatten(cls, obj, acc:str|None=None, res:dict={}):
        if type(obj) == list:
            return [ cls._flatten(e, None, {}) for e in obj ]

        if type(obj) != dict:
            return obj

        for k, v in obj.items():
            flat = f'{acc}.{k}' if acc else k
            if type(v) == dict: cls._flatten(v, flat, res)
            elif type(v) == list: res[flat] = [ cls._flatten(e, None, {}) for e in v ]
            else: res[flat] = v

        return res

    @classmethod
    def flatten(cls, obj:dict):
        return cls._flatten(obj, None, {})

    @classmethod
    def translate(cls, obj, table:dict, acc:dict = {}, parent:str|None = None, switches:dict = {}):
        if type(obj) == str:
            try:
                has = lambda x : x == obj if type(x) is str else obj in x
                return [ k for k, v in table[cls.fields_key].items() if has(v) ][0]
            except IndexError:
                raise IndexError(f'{obj} doesnt exist in {table} @ {cls.__name__}')

        if type(obj) == dict:
            ret = {}
            table_entry = cls._normalize_translation_table(table)
            table_entry = table_entry[cls.fields_key]

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

                required, reverse, default_null, vtype, trim_start, trim_end = (
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

                if mapped_name:
                    for n in (mapped_name if type(mapped_name) is list else mapped_name.split('|')):
                        if not value:
                            mapped_name = n
                            value = obj.get(n.split('[]')[0])

                if '!' in symbols: required=True
                if '/' in symbols and value: value = value.split(' ')[0]
                if '#' in symbols and value:
                    vtype = 'integer'
                    switches['enforce'] = True

                # plain value
                if cls.fields_key not in v:
                    if type(mapped_name) is str and '[]' in mapped_name:
                        target = re.compile(r'\[\]\.?').split(mapped_name)
                        _, field = target

                        if type(ret) != list:
                            ret = acc.get(parent) \
                                if type(parent) == object \
                                else [ {} for _ in range(len(value or [])) ]

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
                            if required: raise ValueError('({}) required value'.format(mapped_name))
                            # raise OptionalFieldException(mapped_name)
                            continue

                    if isinstance(value, str):
                        if trim_start: value = value[trim_start*-1:]
                        if trim_end: value = str(value)[:trim_end]

                    if switches.get('array'):
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
                    expected = type_mapping.get(str(vtype), vtype)

                    if actual != expected and not (actual == 'NoneType' and default_null):
                        raise TypeError('({}) expected type: {}, got: {} % {}'.format(mapped_name, expected, actual, cls.__name__))

                    if isinstance(ret, dict):
                        ret[k] = value

                else:
                    child = obj[mapped_name] if mapped_name else obj
                    if isinstance(ret, dict):
                        res = cls.translate(child, v, ret, k, switches)
                        ret[k] = res
                        continue

            return ret

        elif type(obj) == list:
            table_entry = cls._normalize_translation_table(table)
            table_entry = table_entry[cls.fields_key]

            if table.get('array') != True:
                raise TypeError('illegal array: ' + str(table))

            return [
                cls.translate(i, table, switches=switches)
                for i in obj
            ]

