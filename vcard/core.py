class TextReader:
    def __init__(self, stream):
        self.stream = stream
        self.line_number = 0

        self._next_line = None

    def readline(self):
        if self._next_line is None:
            line = self.stream.readline()
        else:
            line = self._next_line
            self._next_line = None

        if line:
            self.line_number += 1

        return line

    def peekline(self):
        if self._next_line is None:
            self._next_line = self.stream.readline()

        return self._next_line

    def close(self):
        self.stream.close()


class LineSpan:
    def __init__(self):
        self.start = 1
        self.end = 1

    def __str__(self):
        return f'{self.start}:{self.end}'


class VCardProperty:
    __line_span__ = None

    def __init__(self, name='', value=''):
        self.name = name
        self.parameters = {}
        self.value = value

    def add_parameter(self, name, value):
        self.parameters.setdefault(name, [])
        values = self.parameters[name]

        if value not in values:
            values.append(value)

    def remove_parameter(self, name):
        self.parameters.pop(name, None)


class VCard:
    __line_span__ = None

    def __init__(self):
        self.properties = {}

    def add_property(self, prop):
        self.properties.setdefault(prop.name, [])
        properties = self.properties[prop.name]
        properties.append(prop)

    def remove_property(self, name):
        self.properties.pop(name, None)


def _index_any(string, chars, start=0):
    index = start
    stop = len(string)

    while index < stop:
        if string[index] in chars:
            return index

        index += 1

    raise ValueError('Not found any expected char')


def parse_vcard_property(line):
    prop = VCardProperty()

    delimiter_index = _index_any(line, ';:')
    group_and_name_data = line[:delimiter_index]

    *_, property_name = group_and_name_data.split('.')

    prop.name = property_name.lower()

    if line[delimiter_index] == ';':
        start = delimiter_index + 1
        delimiter_index = _index_any(line, ':', start)
        parameters_data = line[start:delimiter_index]

        for parameter_data in filter(None, parameters_data.split(';')):
            pair = parameter_data.split('=', 1)

            if len(pair) == 2:
                parameter_name, parameter_value = pair
            else:
                parameter_name, parameter_value = 'type', pair[0]

            parameter_name = parameter_name.strip().lower()
            parameter_value = parameter_value.strip().lower()

            prop.add_parameter(parameter_name, parameter_value)

    prop.value = line[delimiter_index + 1:]

    if prop.name in ('begin', 'end'):
        prop.value = prop.value.lower()

    return prop


def _read_vcard_v21_property_value_quoted_printable(reader, first_fragment):
    fragment = first_fragment
    fragments = []

    while True:
        fragment = fragment.rstrip()

        if fragment.endswith('='):
            fragments.append(fragment[0:-1])
            fragment = reader.readline()

            if not fragment:
                raise ValueError(f'incomplete quoted-printable property value, line {reader.line_number}')
        else:
            fragments.append(fragment)
            break

    return ''.join(fragments)


def _read_vcard_v21_property_value_base64(reader, first_fragment):
    fragment = first_fragment
    fragments = []

    while fragment:
        fragment = fragment.strip()
        fragments.append(fragment)
        fragment = reader.readline()

        if not fragment or fragment[0] not in '\t ':
            raise ValueError(f'incomplete base64 property value, line {reader.line_number}')

        fragment = fragment.rstrip('\r\n')

    return ''.join(fragments)


def _read_vcard_property_value_folded(reader, first_fragment, version):
    fragment = first_fragment
    fragments = []

    while True:
        fragments.append(fragment)
        fragment = reader.peekline()

        if not fragment:
            break

        if fragment[0] not in '\t ':
            break

        fragment = reader.readline()
        fragment = fragment.rstrip('\r\n')

        if version == '2.1':
            fragment = fragment.lstrip()
        else:
            fragment = fragment[1:]

    return ''.join(fragments)


def read_vcard_property(reader, version='2.1'):
    while True:
        line = reader.readline()

        if not line:
            return

        line = line.rstrip('\r\n')

        if line:
            break

    try:
        prop = parse_vcard_property(line)
    except ValueError as exc:
        raise ValueError(f'Invalid property data, line {reader.line_number}: {exc}')

    prop.__line_span__ = LineSpan()
    prop.__line_span__.start = reader.line_number
    encoding = prop.parameters.get('encoding', [''])[0]

    first_fragment = prop.value

    if encoding == 'quoted-printable':
        prop.value = _read_vcard_v21_property_value_quoted_printable(reader, first_fragment)
    elif encoding == 'base64':
        prop.value = _read_vcard_v21_property_value_base64(reader, first_fragment)
    else:
        prop.value = _read_vcard_property_value_folded(reader, first_fragment, version)

    prop.__line_span__.end = reader.line_number

    return prop


_fallback_version = '2.1'


def read_vcard(reader):
    prop = read_vcard_property(reader, _fallback_version)

    if not prop:
        return

    if prop.name != 'begin' or prop.value != 'vcard':
        raise ValueError(f'Expected a begin property, got: {prop.name}')

    vcard = VCard()
    vcard.__line_span__ = LineSpan()
    vcard.__line_span__.start = prop.__line_span__.start

    while True:
        version = vcard.properties.get('version', [_fallback_version])[0]
        prop = read_vcard_property(reader, version)
        property_name = prop.name

        if not prop:
            raise ValueError('incomplete vcard')

        if property_name == 'end' or prop.value == 'vcard':
            vcard.__line_span__.end = prop.__line_span__.end
            break

        if property_name == 'agent':
            if version == '2.1':
                read_vcard(reader)

            continue

        vcard.properties.setdefault(property_name, [])
        same_name_properties = vcard.properties[property_name]
        same_name_properties.append(prop)

    return vcard


_property_order = {
    'version': 0,
    'fn': 1,
    'n': 2,
    'sort-string': 3,
    'nickname': 4,
    'adr': 5,
    'label': 6,
    'tel': 7,
    'mail': 8,
    'mailer': 9,
    'org': 10,
    'categories': 11,
    'class': 12,
    'bday': 13,
    'title': 14,
    'role': 15,
    'note': 16,
    'uid': 17,
    'url': 18,
    'tz': 19,
    'geo': 20,
    'photo': 21,
    'logo': 22,
    'sound': 23,
    'key': 24,
    'prodid': 98,
    'rev': 99,
}


def _property_sort_key(property_name):
    return _property_order.get(property_name, 90)


def _sorted_properties(names):
    return sorted(names, key=_property_sort_key)


def write_vcard(stream, vcard):
    stream.write('BEGIN:VCARD\n')

    for prop_name in _sorted_properties(vcard.properties):
        same_name_properties = vcard.properties[prop_name]

        for prop in same_name_properties:
            stream.write(prop.name.upper())

            parameters = prop.parameters

            for parameter_name in sorted(parameters):
                parameter_values = parameters[parameter_name]

                for parameter_value in sorted(parameter_values):
                    stream.write(';')
                    stream.write(parameter_name.upper())
                    stream.write('=')
                    stream.write(parameter_value.upper())

            stream.write(':')
            stream.write(prop.value)
            stream.write('\n')

    stream.write('END:VCARD\n')
