import itertools
import logging

from vcard.core import TextReader, read_vcard, write_vcard
from vcard.text import split_structured_value, unescape, escape, remove_redundant_whitespaces, remove_newlines


_handler = logging.StreamHandler()
_handler.setFormatter(logging.Formatter('%(levelname)s: %(message)s'))

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
logger.addHandler(_handler)


def get_clean_name(vcard):
    names = vcard.properties.get('n')

    if not names:
        return

    processors = [unescape, remove_redundant_whitespaces, remove_newlines, escape]
    components = split_structured_value(names[0].value, ';')[:2]
    r = []

    for component in components[:2]:
        for processor in processors:
            component = processor(component)

        r.append(component)

    return ''.join(r)


def merge_vcard(states, vcard):
    v = vcard.properties.get('version', [None])[0]

    if v and v.value == '2.1':
        logger.error(f'merging vcard 2.1 objects is not supported, at {vcard.__line_span__}')
        return

    name = get_clean_name(vcard)

    if name is None:
        logger.error(f'no n property in vcard at {vcard.__line_span__}')
        return

    if name not in states:
        states[name] = vcard
        return

    merged_vcard = states[name]

    for prop in itertools.chain.from_iterable(vcard.properties.values()):
        if prop.name in ('version', 'fn', 'n'):
            continue

        old_values = set(map(lambda p: p.value, merged_vcard.properties[prop.name]))

        if prop.value in old_values:
            logger.info(f'found duplicated {prop.name} property at {prop.__line_span__}')
        else:
            logger.info(f'merging {prop.name} property at {prop.__line_span__} to vcard at {merged_vcard.__line_span__}')

            merged_vcard.add_property(prop)


def merge_vcard_stream(states, input_stream):
    reader = TextReader(input_stream)

    while True:
        vcard = read_vcard(reader)

        if not vcard:
            break

        merge_vcard(states, vcard)


def main():
    import os
    import glob
    import sys
    import argparse

    parser = argparse.ArgumentParser(description='merge vcard 3.0 files.')
    parser.add_argument('-i', dest='input_files', action='append', required=True, metavar='INPUT',
                        help='specify input vcard 3.0 files. supports wildcards.')
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

    if os.path.exists(args.output_path) and not os.path.isfile(args.output_path):
        parser.exit(-1, 'output path must be a file.')

    try:
        output_stream = open(args.output_path, 'w', encoding='utf-8')
    except OSError as exc:
        parser.exit(-1, f'"{args.output_path}": {exc}')

    errors = 0
    states = {}

    for input_pathname in input_files:
        try:
            input_stream = open(input_pathname, 'r', encoding='utf-8')
        except OSError as exc:
            logger.error(f'"{input_pathname}": {exc}')
            errors += 1
            continue

        logger.info('merging "%s"', input_pathname)

        try:
            merge_vcard_stream(states, input_stream)
        except ValueError as exc:
            logger.error(f'"{input_pathname}": {exc}')
            errors += 1
            continue

    for vcard in states.values():
        write_vcard(output_stream, vcard)

    sys.exit(errors)


if __name__ == '__main__':
    main()
