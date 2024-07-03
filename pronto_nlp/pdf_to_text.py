# # requirements: pip install PyMuPDF and nltk and nltk.download('punkt')
#
# try:
#     import fitz
#     import requests
#     from nltk.tokenize import sent_tokenize
# except ImportError:
#     raise ImportError('To use PDF functionality, Please install\n -->  pip install git+https://github.com/ProntoNLP/pronto-nlp-sdk.git#egg=pronto_nlp[pdf]')
#
#
# import string
# from collections import Counter
# from typing import List, Tuple
# from pathlib import Path
# import textwrap
# import re
# import os
# from dateutil.parser import parse as date_parse
#
# ascii_lowercase = string.ascii_lowercase + ' '
#
#
# def join_paths(p1: (str, Path), p2: (str, Path)) -> Path:
#     return Path(os.path.join(p1, p2))
#
#
# def initial_split(txt: str) -> List[str]:
#     """First split on specific characters, then apply NLTK's tokenizer"""
#     split_text = [sent_tokenize(z) for z in re.split('(?=[●•⬤])', txt.strip())]
#     sentences = [i.strip() for li in split_text for i in li]  # flatten the list
#     return sentences
#
#
# def second_pass_split(txt: str) -> List[str]:
#     """Second pass logic to split by Japanese or English sentence endings"""
#     if "。" in txt or "！" in txt or "？" in txt:
#         # Use regex to split by Japanese sentence-ending punctuation, keeping the punctuation
#         sentences = re.split(r'(?<=[。！？])', txt.strip())
#     elif ". " in txt:
#         sentences = txt.split(". ")
#     else:
#         sentences = [txt]
#
#     return [sentence.strip() for sentence in sentences if sentence.strip()]
#
#
# def make_sentences(txt: str) -> List[str]:
#     """Combine initial and second pass split logic to produce a list of sentences"""
#     sentences = initial_split(txt)
#     # Check if the initial logic produces a multi-item list
#     if len(sentences) <= 1:
#         sentences = second_pass_split(txt)
#     sentences[:] = [textwrap.wrap(s, 4000, break_long_words=False, break_on_hyphens=False) for s in sentences]
#     sentences[:] = [s for s in sentences if s]
#     return sentences
#
#
# def _check_if_sentence_is_words(sent: str) -> bool:
#     """
#     Given a sentence, find the ratio of letter characters to total. If it's low we don't want it
#     """
#     sent_check = sent.strip()
#     if not sent_check:
#         return False
#
#     if re.search(r"^Page \d+ of \d+$", sent_check):
#         return False
#
#     if sent_check.startswith('<image:'):
#         return False
#
#     if is_mostly_numbers(sent_check):
#         return False
#
#     if is_date(sent_check):
#         return False
#
#     if sent_check.endswith((":", ";", ",")): ## probably is part of a list and not the full line, return it
#         return True
#
#     char_freq = Counter(sent_check.lower())
#
#     score = sum(char_freq[x] for x in ascii_lowercase) / len(sent_check)
#
#     if '<' in char_freq and '>' in char_freq:
#         score *= abs(len(sent_check) - (char_freq['<'] + char_freq['>']) * 5) / len(sent_check)
#
#     return score > 0.5
#
#
# def sort_blocks(blocks):
#     vertical_sorted_blocks = sorted(blocks, key=lambda b: (b[1], b[0]))
#     return vertical_sorted_blocks
#
#
# def is_date(s):
#     if not s:
#         return False
#
#     if not isinstance(s, str):
#         s = str(s)
#     try:
#         # Try to parse the string as a date or datetime
#         date_parse(s)
#         return True
#     except ValueError:
#         return False
#
#
# def is_mostly_numbers(text):
#     """Determine if a block of text is mostly numbers."""
#     text_check = text.strip()
#     text_check = re.sub(r'[^\w\s]', '', text_check)
#     text_check = re.sub(r'\b(January|February|March|April|May|June|July|August|September|October|November|December)\b',
#                   '', text_check, flags=re.I)
#     letters = sum(c.isalpha() for c in text_check)
#     numbers = sum(c.isdigit() for c in text_check)
#     return numbers > letters
#
#
# def standard_base_parse(doc, block_prep):
#     paragraphs = []
#     bad_break = tuple()
#
#     for page in doc:
#         for i_blk, block in enumerate(sort_blocks(page.get_text("blocks", sort=True))):
#             texts = block_prep(block[4])
#
#             if len(texts) == 1 and _check_if_sentence_is_words(texts[0]) and i_blk == 0:
#                 ## probably the title
#                 paragraphs.append(texts[0])
#                 continue
#
#             for text in texts:
#                 if not _check_if_sentence_is_words(text):
#                     continue
#
#                 if bad_break:
#                     if text.endswith('.') and (i_blk != bad_break[0] or bad_break[1].split()[0] != text.split()[0]):  # bad break, put them together, append, reset
#                         txt = [bad_break[1], text]
#                         bad_break_txt = " ".join(txt)
#                         paragraphs.append(bad_break_txt)
#                         bad_break = tuple()
#                         continue
#                     else:  # must not have been a bad break, add the text separately, reset bad_break
#                         paragraphs.append(bad_break[1])
#                         bad_break = tuple()
#
#                 # handle bad breaks, even across pages/blocks
#                 if text[-1].isalpha() or text[-1].isdigit():  ## and not a punctuation..
#                     bad_break = (i_blk, text)
#                     continue
#
#                 paragraphs.append(text)
#
#     return paragraphs
#
#
# def parse_general(doc):
#     block_prep = lambda X: [t.replace('\n', '').strip() for t in X.split("  \n")]
#     paragraphs = standard_base_parse(doc, block_prep)
#     doc_title = paragraphs[0].strip().title()
#     return paragraphs, doc_title
#
#
# def extract_text(doc, *args, **kwargs) -> Tuple[List[str], str]:
#     """
#     Takes advantage of the block structure of text-based unstructured PDFs to get each block of text separately,
#     sorted by co-ordinates (left-to-right and top-to-bottom). Sentence tokenizing is via NLTK.
#     """
#     paragraphs, doc_title = parse_general(doc)
#     paragraphs[:] = [make_sentences(str(x)) for x in paragraphs]
#     return paragraphs, doc_title
#
#
# def extract_text_from_file(in_file: str, *args, **kwargs) -> Tuple[List[str], str]:
#     return extract_text(fitz.open(in_file), *args, **kwargs)
#
#
# def extract_text_from_stream(doc_link, store_raw, doc_type, *args, **kwargs) -> Tuple[List[str], str]:
#     data = requests.get(doc_link, headers={'User-Agent': 'PostmanRuntime/7.32.3'}).content
#     fname = doc_link.split('/')[-1]
#     doc_path = None
#
#     if store_raw:
#         out_path = join_paths(store_raw, doc_type)
#         if not os.path.exists(out_path):
#             os.makedirs(out_path, exist_ok=True)
#         try:
#             with open(join_paths(out_path, fname), 'wb') as f:
#                 f.write(data)
#             doc_path = join_paths(out_path, fname)
#         except:
#             print(f"Failed to save PDF: {fname}")
#
#     try:
#         return extract_text(fitz.open('pdf', data), doc_type=doc_type, doc_path=doc_path, *args, **kwargs)
#
#     except Exception as e:
#         print(e)
#         print(doc_link)
