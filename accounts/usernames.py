from django.utils.text import slugify

def username_candidates(first_name, last_name):
    """Readable account names; the database remains the uniqueness authority."""
    words = first_name.split()
    given = slugify(words[0] if words else '')[:4] or 'user'
    surname = slugify(last_name) or 'usuario'
    base = f'{given}.{surname}'[:140]
    yield base
    suffix = 2
    while True:
        yield f'{base}{suffix}'
        suffix += 1
