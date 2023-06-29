import os
import shlex
import subprocess

import click
from lxml import etree
from nltk.tokenize import sent_tokenize, word_tokenize
import spacy
import stanza
import spacy_stanza

from ..core.constants import UPLUG, NLTK, SPACY, STANZA, TREETAGGER, NLTK_LANGUAGES, SPACY_MODELS


def tokenize_single(file_in, file_out, language, tokenizer):
    """
    Tokenizes (on sentence- and word-level) the input file.
    :param file_in: the input file
    :param file_out: the output file
    :param language: the current language
    :param tokenizer: the tokenizer being used
    """
    if tokenizer == UPLUG:
        click.echo('Using Uplug tokenization')
        uplug_tokenize(file_in, file_out, language)
    elif tokenizer == NLTK:
        click.echo('Using NLTK tokenization')
        nltk_tokenize(file_in, file_out, language)
    elif tokenizer == SPACY:
        click.echo('Using Spacy tokenization')
        spacy_tokenize(file_in, file_out, language)
    elif tokenizer == STANZA:
        click.echo('Using Stanza tokenization')
        stanza_tokenize(file_in, file_out, language)
    elif tokenizer == TREETAGGER:
        # Use TreeTagger without tokenization, based on the preprocessed .txt-files
        click.echo('Using TreeTagger tokenization')


def uplug_tokenize(file_in, file_out, language):
    # Run Uplug with a fallback to the general module
    command = 'uplug -f pre/basic pre/{language}/basic -in {file_in} > {file_xml}'
    command = command.format(language=language,
                             file_in=shlex.quote(file_in),
                             file_xml=shlex.quote(file_out))
    subprocess.call(command, shell=True, stdout=open(os.devnull, 'w'), stderr=subprocess.STDOUT)


def nltk_tokenize(file_in, file_out, language):
    punkt_language = NLTK_LANGUAGES.get(language)
    if not punkt_language:
        raise click.ClickException('Tokenization in NLTK not available for language {}'.format(language))

    # Create counters for paragraphs and sentences
    i = j = 1

    # Start a text element and add a first paragraph
    text = etree.Element('text')
    paragraph = etree.SubElement(text, 'p')
    paragraph.set('id', str(i))

    with open(file_in, 'r', encoding='utf8') as f:
        for line in f.readlines():
            line = line.strip()
            if line:
                sentences = sent_tokenize(line, language=punkt_language)
                for s in sentences:
                    sentence = etree.SubElement(paragraph, 's')
                    sentence.set('id', 's{}.{}'.format(i, j))
                    words = word_tokenize(s, language=punkt_language)
                    for k, w in enumerate(words, start=1):
                        word = etree.SubElement(sentence, 'w')
                        word.set('id', 'w{}.{}.{}'.format(i, j, k))
                        word.text = w
                j += 1
            else:
                i += 1
                paragraph = etree.SubElement(text, 'p')
                paragraph.set('id', str(i))
                j = 1

    tree = etree.ElementTree(text)
    tree.write(file_out, pretty_print=True, xml_declaration=True, encoding='utf-8')


def spacy_tokenize(file_in, file_out, language):
    spacy_model = SPACY_MODELS.get(language)
    if not spacy_model:
        raise click.ClickException('Tokenization in Spacy not available for language {}'.format(language))
    # For sentence boundaries, we use a simple model, rather than the dependency parser,
    # because we are (mainly) interested in sentence boundaries.
    try:
        nlp = spacy.load(spacy_model, exclude=["parser"])
        nlp.add_pipe("sentencizer")
    except OSError:
        raise click.ClickException(
            'Spacy model for language {} not available: '
            'please download it first with the command `python -m spacy download {}`'.format(language, spacy_model))

    nlp_process(nlp, file_in, file_out)


def stanza_tokenize(file_in, file_out, language):
    # Download the stanza model (if necessary).
    try:
        stanza.download(language)
    except ValueError:
        raise click.ClickException('Tokenization in Stanza not available for language {}'.format(language))

    try:  # this will fail if the language in question is not in SpaCy, since it's trying to use SpaCy + Stanza
        nlp = spacy_stanza.load_pipeline(language, processors='tokenize,pos,lemma')
        nlp.add_pipe('sentencizer')
        nlp_process(nlp, file_in, file_out)
    except ImportError:
        nlp = stanza.Pipeline(lang=language, processors="tokenize,pos,lemma")
        nlp_process(nlp, file_in, file_out, stanza_unique=True)



def nlp_process(nlp, file_in, file_out, stanza_unique=False):
    # Create counters for paragraphs
    i = 1

    # Start a text element and add a first paragraph
    text = etree.Element('text')
    paragraph = etree.SubElement(text, 'p')
    paragraph.set('id', str(i))

    with open(file_in, 'r', encoding='utf8') as f:
        for line in f.readlines():
            line = line.strip()
            if line:
                doc = nlp(line)
                start_new = True
                j = 0

                for sent in doc.to_dict():
                        if start_new:
                            j += 1
                            sentence = etree.SubElement(paragraph, 's')
                            sentence.set('id', 's{}.{}'.format(i, j))

                        if stanza_unique == True:
                            for k, token in enumerate(sent, start=1):
                                    word = etree.SubElement(sentence, 'w')
                                    word.set('id', 'w{}.{}.{}'.format(i, j, k))
                                    word.text = token['text']
                                    word.set('tree', token['upos'])  # if you want XPOS, change the text in square brackets to 'xpos'
                                    word.set('lem', token['lemma'])

                            # Safeguard to not start a new sentence for single-token sentences
                            start_new = len(sent) != 1

                        else:
                            for k, token in enumerate(sent, start=1):
                                word = etree.SubElement(sentence, 'w')
                                word.set('id', 'w{}.{}.{}'.format(i, j, k))
                                word.text = token.text
                                word.set('tree', token.tag_)
                                word.set('lem', token.lemma_)

                            # Safeguard to not start a new sentence for single-token sentences
                            start_new = len(sent) != 1

            else:
                i += 1
                paragraph = etree.SubElement(text, 'p')
                paragraph.set('id', str(i))

    tree = etree.ElementTree(text)
    tree.write(file_out, pretty_print=True, xml_declaration=True, encoding='utf-8')
