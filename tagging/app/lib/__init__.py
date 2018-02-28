"""
__init__.py

library module for the app
"""
import json
import os
import tempfile

import en_core_web_sm
nlp = en_core_web_sm.load()

from app import app


def nlp_over_lines_as_blob(lines, *extractors):
    """Given an iterable collection of lines of text, generates complete
    sentences and runs a series of extractor functions over each sentence.

    Yields a tuple for each sentence containing the results of each extractor
    """
    blob = ' '.join(lines)
    doc = nlp(blob)
    for sent in doc.sents:
        extracted = [ext(sent) for ext in extractors]
        yield tuple(extracted)

def nlp_over_lines(lines, *extractors):
    """Given an iterable collection of lines of text, runs a series of
    extractor functions over each line.

    Yields a tuple for each line containing the results of each extractor
    """
    for line in lines:
        doc = nlp(line)
        extracted = [ext(doc) for ext in extractors]
        yield tuple(extracted)


def entities_from_span(spacy_span):
    """Given a spact span object, returns the entities in the span."""
    entities, temp_stack = list(), list()
    for token in spacy_span:
        if token.ent_iob_ == 'B':
            # Beginning a new entity. Complete the current stack and clear
            if temp_stack:
                entities.append(entity_text_type_from_tokens(temp_stack))
                temp_stack.clear()
            # Add the current one to start the new entity
            temp_stack.append(token)
        elif token.ent_iob_ == 'I':
            if not len(temp_stack):
                raise ValueError('Inside an entity but no stack is empty')
            temp_stack.append(token)
        elif token.ent_iob_ == 'O':
            # Ended entity. Complete the current stack and clear
            if temp_stack:
                entities.append(entity_text_type_from_tokens(temp_stack))
                temp_stack.clear()
    # end loop

    return entities


def entity_text_type_from_tokens(tokens):
    """Given an iterable of tokens representing an entity, returns a tuple
    with the entity text and type. Assumes that all tokens are of the same
    entity and there is only a single entity type."""
    entext = ' '.join([t.text for t in tokens])
    entype = tokens[0].ent_type_
    return entext, entype


def str_from_span(sent):
    return sent.string.strip()


def get_tempfile_for_write(**kwargs):
    if 'dir' not in kwargs:
        kwargs['dir'] = app.root_path
    fd, filename = tempfile.mkstemp(**kwargs)
    return (os.fdopen(fd, 'w'), filename)


def save_to_tempfile_as_json(data, **kwargs):
    """Saves data to a .json tempfile and returns the filename. Files are
    created using `tempfile.mkstemp`, kwargs passed will be sent to mkstemp.
    If no dir is specified, file is created in the app root."""
    kwargs.update({'suffix': '.json'})
    fout, filename = get_tempfile_for_write(**kwargs)
    fout.write(json.dumps(data, indent=2))
    fout.close()
    return filename


def save_to_tempfile_as_lines(lines, **kwargs):
    """Saves lines to a .txt tempfile and returns the filename. Appends a
    newline at the end of each line."""
    kwargs.update({'suffix': '.txt'})
    fout, filename = get_tempfile_for_write(**kwargs)
    for line in lines:
        fout.write(line+'\n')
    fout.close()
    return filename
