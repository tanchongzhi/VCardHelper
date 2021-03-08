import re
import unicodedata


def _build_separation_pattern(separator):
    assert len(separator) == 1

    char = re.escape(separator)
    return re.compile(rf'(?:[^\\{char}]|\\\\|\\{char}|\\)*')


def _split_structured_value(string, separation_pattern):
    parts = []
    prev_not_empty = False

    for match in separation_pattern.finditer(string):
        if match.start() == len(string) and not parts:
            break

        if match.start() == match.end():
            if not prev_not_empty:
                parts.append('')

            prev_not_empty = False
        else:
            prev_not_empty = True
            parts.append(match.group())

    return parts


def split_structured_value(string, separator):
    return _split_structured_value(string, _build_separation_pattern(separator))


def escape(string):
    string = re.sub(r'(\r\n|\r)', '\n', string)
    chars = []

    for char in string:
        if char == '\n':
            chars.append('\\n')
        elif char == '\\':
            chars.append('\\\\')
        elif char == ',':
            chars.append('\\,')
        elif char == ';':
            chars.append('\\;')
        else:
            chars.append(char)

    return ''.join(chars)


def unescape(string):
    chars = []
    index = 0
    end = len(string)

    while index < end:
        char = string[index]
        index += 1

        if char == '\\' and index < end:
            next_char = string[index]
            index += 1

            if next_char in r'\,;':
                chars.append(next_char)
                continue
            elif next_char in 'nN':
                chars.append('\n')
            else:
                chars.append(char)
                chars.append(next_char)
        else:
            chars.append(char)

    return ''.join(chars)


def fold(string, *, width=76, initial_newline=True, newline='\n'):
    parts = []
    start = 0
    end = len(string)

    if initial_newline:
        index = width - 1
        part = newline + ' ' + string[start:index]
    else:
        index = width
        part = string[start:index]

    parts.append(part)

    start = index
    index = start + (width - 1)

    while index < end:
        part = ' ' + string[start:index]
        parts.append(part)

        start = index
        index = start + (width - 1)

    return newline.join(parts)


def remove_redundant_whitespaces(string):
    return re.sub(r'[\f\v\t ]+', ' ', string.strip())


def remove_newlines(string):
    return re.sub(r'[\r\n]+', '', string)


def replace_newlines(string, newline='\n'):
    return re.sub(r'[\r\n]+', newline, string)


def remove_whitespaces(string):
    return re.sub(r'\s+', '', string)


PUNCTUATION_CATEGORIES = {'Pc', 'Pd', 'Ps', 'Pe', 'Pi', 'Pf', 'Po'}


def remove_punctuations(string, *, translate_table=None, preserve_chars='()[]{}@#$%-_+=.'):
    if translate_table:
        string = string.translate(translate_table)

    chars = []

    for char in string:
        if char in preserve_chars or unicodedata.category(char) not in PUNCTUATION_CATEGORIES:
            chars.append(char)

    return ''.join(chars)
