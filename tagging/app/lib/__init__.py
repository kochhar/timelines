"""
__init__.py

library module for the app
"""
import spacy
nlp = spacy.load('en')


def nlp_over_lines_as_blob(lines, *extractors):
    """Given an iterable collection of lines of text, generates complete
    sentences and runs a series of extractor functions over each sentence.

    Yields a tuple for each sentence containing the results of each extractor
    """
    blob = ' '.join(lines).replace('\n', ' ')
    doc = nlp(blob)
    for i, sent in enumerate(doc.sents):
        extracted = []
        for ext in extractors:
            extract = ext(sent)
            extracted.append(extract)

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
