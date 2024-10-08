import re
import sys

import xml.etree.ElementTree as ETree

from pathlib import Path

import pandas as pd
import tqdm


NAMESPACES = {
            "dc": "http://purl.org/dc/elements/1.1/",
            "dcterms" : "http://purl.org/dc/terms/",
            "olac" : "http://www.language-archives.org/OLAC/1.1/",
            "xsi" : "http://www.w3.org/2001/XMLSchema-instance",
            "oai" : "http://www.openarchives.org/OAI/2.0/",
            "doi" : "http://datacite.org/schema/kernel-4",
            "crdo" : "http://cocoon.huma-num.fr/schemas/",

        }

def extract_records(metadata):

    def extract_speaker(xml):
        for locuteur in xml.findall('.//dc:contributor[@olac:code="speaker"]', NAMESPACES):
            return locuteur.text

    def extract_doi(xml):

        for identifiant in xml.findall('.//dc:identifier', NAMESPACES):
            if "doi:" in identifiant.text:
                print(identifiant.text)
                return identifiant.text.replace('doi:','')

    def extract_disc_type(xml):
        for types in xml.findall('.//dc:type[@xsi:type="olac:discourse-type"]', NAMESPACES):
            olac_code = types.get('{http://www.language-archives.org/OLAC/1.1/}code')
            return olac_code


    def parse_length(length):

        if length is None:
            return None

        length_regexp = re.compile(r"PT((?P<hours>[0-9]*)H)?((?P<minutes>[0-9]*)M)?((?P<seconds>[0-9]*)S)?")
        if result_regex_min := length_regexp.search(length.text):
            hours = int(result_regex_min.group("hours")) if result_regex_min.group("hours") is not None else 0
            minutes = int(result_regex_min.group("minutes")) if result_regex_min.group("minutes") is not None else 0
            seconds = int(result_regex_min.group("seconds")) if result_regex_min.group("seconds") is not None else 0
            return hours * 3_600 + minutes * 60 + seconds

        assert False, f"{length.text} can not be parsed"

    def extract_uri(xml):

        for el in xml_record.findall('.//dc:identifier', NAMESPACES):
            if el.text.split(".")[-1] == "xml":
                return el.text

        for el in xml_record.findall('.//dcterms:isFormatOf', NAMESPACES):
            if el.text.split(".")[-1] == "wav":
                return el.text

        return None

    def first(el):
        if el is None or not el:
            return None

        return el[0].text

    tree = ETree.parse(metadata)
    root = tree.getroot()

    all_records = []
    for xml_record in tqdm.tqdm(root.findall(".//oai:record", NAMESPACES)):
        if (accessRights := xml_record.find(".//dcterms:accessRights", NAMESPACES)) is not None:
            if accessRights.text != "Freely accessible":
                continue

        # ignore collections
        # better way : check that "xsi:type" attribute of dc:subject is "olac:language"
        if not xml_record.findall('.//dc:subject', NAMESPACES) or not xml_record.findall('.//dc:subject', NAMESPACES)[0].text:
            continue

        record = {
            "oai": xml_record.find("*/oai:identifier", NAMESPACES).text,
            "datestamp": xml_record.find('*/oai:datestamp', NAMESPACES).text,    # regarder la date de l'enregistrement balise created de l'audio
            "language": xml_record.findall('.//dc:subject', NAMESPACES)[0].text,
            "speaker": extract_speaker(xml_record),
            "doi": extract_doi(xml_record),
            "length": parse_length(xml_record.find(".//dcterms:extent", NAMESPACES)),
            "uri": extract_uri(xml_record),
            "requires": first(xml_record.findall('.//dcterms:requires', NAMESPACES)),
            "type": extract_disc_type(xml_record)
        }

        all_records.append(record)

    return pd.DataFrame(all_records)


def lazy_download(url, dest):
    """
    Download a file only if it does not exist yet.

    based on https://stackoverflow.com/a/63831344
    """

    import requests
    import functools
    import shutil
    from tqdm.auto import tqdm

    if dest.is_file():
        print(f"{dest.name} has already been downloaded.")
        return

    r = requests.get(url, stream=True, allow_redirects=True)
    file_size = int(r.headers.get('Content-Length', 0))
    r.raw.read = functools.partial(r.raw.read, decode_content=True)

    with tqdm.wrapattr(r.raw, "read", total=file_size, desc=f"downloading {dest.name}") as r_raw:
        with dest.open("wb") as f:
            shutil.copyfileobj(r_raw, f)



def download_annotated_data(row, corpus_dir):
    row = row[~row.isna()]

    dest_dir = corpus_dir / row["language"]

    dest_dir.mkdir(exist_ok=True, parents=True)

    if "uri_audios" in row:
        lazy_download(row["uri_audios"], dest_dir / (row["doi"].split("/")[1] + ".wav"))
    if "uri_annotations" in row:
        lazy_download(row["uri_annotations"], dest_dir / (row["doi"].split("/")[1] + ".xml"))


if __name__ == "__main__":

    import argparse
    import logging

    parser = argparse.ArgumentParser()
    parser.add_argument("--metadata", required=True)
    parser.add_argument("--languages", nargs="+",
                        help="keeps only records in the languages listed")
    parser.add_argument("--corpus_dir", default=Path("corpus"), type=Path)
    parser.add_argument("--except_speakers", nargs="+")
    args = parser.parse_args()

    records = extract_records(args.metadata)
    records.to_csv("records.csv")
    assert (args.except_speakers is not None) or (args.languages is not None), "No filtering condition provided — I will not download the whole Pangloss collection 🤔"

    if args.languages is not None:
        args.languages = set(args.languages)

        if (errors := args.languages.difference(records["language"].unique())):
            sys.exit(f"the the metadata '{args.metadata}' do not contain any records in the following languages: {errors}")

        logging.info("filtering languages")
        records = records[records["language"].isin(args.languages) & ~records["uri"].isna()]

    if args.except_speakers is not None:
        logging.info("filtering speakers")
        records = records[~records["speaker"].isin(args.except_speakers) & ~records["uri"].isna()]

    annotations = records[records["uri"].str.endswith("xml")]
    audios = records[records["uri"].str.endswith("wav")]

    # audios_with_annotations will contains both annotated and unannotated data as we are using a left join
    audios_with_annotations = pd.merge(audios, annotations[["uri", "requires"]],
                                       right_on="requires",
                                       left_on="oai",
                                       suffixes=("_audios", '_annotations'),
                                       validate="1:m",
                                       how="left")

    audios_with_annotations = audios_with_annotations[["oai", "datestamp", "language",
                                                       "doi", "length", "uri_audios", "uri_annotations"]]
    audios_with_annotations.to_csv("downloaded_data.csv")

    audios_with_annotations.apply(lambda row: download_annotated_data(row, args.corpus_dir), axis=1)
