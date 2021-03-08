import itertools
import quopri
import logging

from vcard.core import VCard, VCardProperty, TextReader, read_vcard, write_vcard
from vcard.text import split_structured_value, unescape, escape, remove_redundant_whitespaces, remove_newlines


_handler = logging.StreamHandler()
_handler.setFormatter(logging.Formatter('%(levelname)s: %(message)s'))

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
logger.addHandler(_handler)


def _dummy_decode(value):
    return value


def quoted_printable_decoder(prop_v21):
    encoding = prop_v21.parameters.get('encoding', ['8bit'])[0]
    charset = prop_v21.parameters.get('charset', ['utf-8'])[0]

    if encoding == 'quoted-printable':
        def decode(value):
            return quopri.decodestring(value.encode('ASCII')).decode(charset)

        return decode
    else:
        return _dummy_decode


def convert_vcard_v21_to_v30(vcard_v21):
    vcard_v30 = VCard()
    vcard_v30.add_property(VCardProperty('version', '3.0'))

    for prop_v21 in itertools.chain.from_iterable(vcard_v21.properties.values()):
        prop_name = prop_v21.name

        if prop_name == 'version':
            continue

        prop_v30 = VCardProperty(prop_name)

        for param_name, param_values in prop_v21.parameters.items():
            if param_name == 'encoding':
                if param_values[0] == 'base64':
                    prop_v30.add_parameter('encoding', 'b')
                else:
                    continue
            elif param_name == 'charset':
                continue
            else:
                for param_value in param_values:
                    prop_v30.add_parameter(param_name, param_value)

        prop_v21_value = prop_v21.value.strip()

        if not prop_v21_value:
            logger.error(f'empty {prop_name} property at {prop_v21.__line_span__}')
            continue

        decode = quoted_printable_decoder(prop_v21)

        if prop_name == 'n':
            processors = [decode, unescape, remove_redundant_whitespaces, remove_newlines, escape]
            components = split_structured_value(prop_v21_value, ';')
            r = []

            for component in components[:2]:
                for processor in processors:
                    component = processor(component)

                r.append(component)

            for component in components[2:]:
                parts = []

                for part in split_structured_value(component, ','):
                    for processor in processors:
                        component = processor(part)

                    if part:
                        parts.append(part)

                r.append(','.join(parts))

            if len(r) < 5:
                r += [''] * (5 - len(r))

            prop_v30_value = ';'.join(r)
        elif prop_name == 'adr':
            processors = [decode, unescape, remove_redundant_whitespaces, remove_newlines, escape]
            components = split_structured_value(prop_v21_value, ';')
            r = []

            for component in components:
                for processor in processors:
                    component = processor(component)

                r.append(component)

            if len(components) < 7:
                components += [''] * (7 - len(components))

            prop_v30_value = ';'.join(components)
        elif prop_name == 'org':
            processors = [decode, unescape, remove_redundant_whitespaces, remove_newlines, escape]
            components = split_structured_value(prop_v21_value, ';')
            r = []

            for component in components:
                for processor in processors:
                    component = processor(component)

                if component:
                    r.append(component)

            prop_v30_value = ';'.join(r)
        elif prop_name == 'categories':
            processors = [decode, unescape, remove_redundant_whitespaces, remove_newlines, escape]
            components = split_structured_value(prop_v21_value, ',')
            r = []

            for component in components:
                for processor in processors:
                    component = processor(component)

                if component:
                    r.append(component)

            prop_v30_value = ','.join(r)
        elif prop_name == 'geo':
            prop_v30_value = prop_v21_value
        else:
            processors = [decode, unescape, remove_redundant_whitespaces, escape]
            prop_v30_value = prop_v21_value

            for processor in processors:
                prop_v30_value = processor(prop_v30_value)

        if not prop_v30_value:
            logger.error(f'empty {prop_name} property at {prop_v21.__line_span__}')
            continue

        prop_v30.value = prop_v30_value
        vcard_v30.add_property(prop_v30)

    return vcard_v30


def convert_vcard_stream(input_stream, output_stream):
    reader = TextReader(input_stream)

    while True:
        vcard_v21 = read_vcard(reader)

        if not vcard_v21:
            break

        vcard_v30 = convert_vcard_v21_to_v30(vcard_v21)
        write_vcard(output_stream, vcard_v30)


def main():
    import os
    import glob
    import sys
    import argparse

    parser = argparse.ArgumentParser(description='convert vcard 2.1 to vcard 3.0.')
    parser.add_argument('-i', dest='input_files', action='append', required=True, metavar='INPUT',
                        help='specify input vcard 2.1 files. supports wildcards.')
    parser.add_argument('-o', dest='output_path', required=True, metavar='OUTPUT',
                        help='specify output path.')
    args = parser.parse_args()

    input_files = set()

    for pathname in args.input_files:
        if glob.has_magic(pathname):
            for p in glob.glob(pathname, recursive=True):
                if os.path.isfile(p):
                    input_files.add(p)
        else:
            if not os.path.exists(pathname):
                parser.exit(-1, f'"{pathname}" does not exist.')

            if not os.path.isfile(pathname):
                parser.exit(-1, f'"{pathname}" is not a file.')

            input_files.add(pathname)

    if not input_files:
        parser.exit(0)

    if len(input_files) >= 2:
        if os.path.exists(args.output_path) and not os.path.isdir(args.output_path):
            parser.exit(-1, 'multiple files specified but the specified output path is not a directory.')

        os.makedirs(args.output_path, exist_ok=True)

    errors = 0

    for input_pathname in input_files:
        try:
            input_stream = open(input_pathname, 'r', encoding='utf-8')
        except OSError as exc:
            logger.error(f'"{input_pathname}": {exc}')
            errors += 1
            continue

        if os.path.isdir(args.output_path):
            output_pathname = os.path.join(args.output_path, os.path.basename(input_pathname))
        else:
            output_pathname = args.output_path

        try:
            output_stream = open(output_pathname, 'w', encoding='utf-8')
        except OSError as exc:
            logger.error(f'"{output_pathname}": {exc}')
            errors += 1
            continue

        logger.info('converting "%s" to "%s"', input_pathname, output_pathname)

        try:
            convert_vcard_stream(input_stream, output_stream)
        except ValueError as exc:
            logger.error(f'"{input_pathname}": {exc}')
            errors += 1
            continue

    sys.exit(errors)


if __name__ == '__main__':
    main()
