This scripts allows to download a corpus from the [pangloss collection](https://pangloss.cnrs.fr/) and soon from any OLAC repository.

For the moment, you must first download Pangloss metadata using the script that can be found [here](https://github.com/CNRS-LACITO/Pangloss_scripts/tree/main/collecting_pangloss_metadata).

You can than download data from a subset of languages using the following command:
```
python olac_grabber.py  --metadata "metadata_pangloss.xml" --languages "Lazé" --exceptspeakers "Anonyme"
```
the tests performed were done with the Lazé language, using the followin command :

*no speaker excluded : python olac_grabber.py  --metadata "/home/mfily/Documents/diagnoSTIC_XP/03_make_corpus/metadata_pangloss.xml" --languages "Lazé"

*with excluded speakers : python olac_grabber.py  --metadata "/home/mfily/Documents/diagnoSTIC_XP/03_make_corpus/metadata_pangloss.xml" --languages "Lazé" --exceptspeakers "Anonyme"

the difference can be seen in files downloaded_data_lazé_no_exception.csv and downloaded_data_lazé_with_exception.csv

This script has been developed during the `DiagnoSTIC` project.

This work was partly funded by [Agence de l’Innovation de Défense](https://www.defense.gouv.fr/aid) (grant 2022 65 0079).
