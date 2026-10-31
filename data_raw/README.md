# data_raw

This folder is intentionally empty in the public repository except for this file and `LICENSE_NOTICE.txt`.
**Do not commit the dataset.** It contains pseudonymous donor identifiers, the licence does not cover personal data
(clause 4.3-d), and its public redistribution has not been verified as permissible. `.gitignore` blocks it.

## Get the dataset

1. Open the source page on the Saudi Open Data Platform: <https://open.data.gov.sa/ar/datasets/view/cc3b177a-5e5d-4845-bb92-6119b1322b05>
   (Arabic title: «عينة لتبرعات 1500 معرف على منصة احسان»; the file is named "A sample of donations for different IDs in Ehsan").
2. In the **المصادر** (Resources) tab, download the CSV file.
3. Save it here as `A_sample_of__donations_for_different_IDs_in_Ehsan.csv`, or pass its path to `scripts/run_analysis.py`.

## Confirm it is the analysed version

The published results were produced from the file below. The platform may update its copy, so results from a different file can differ.

| Property | Expected value |
|---|---|
| SHA-256 | `0b3df35856bd28177a774ddf22c6fb92e49d052f8d1652c93ff37e72b7d64ec0` |
| Rows (excluding header) | 40,931 |
| Columns | `UserID`, `CreationTime`, `Title`, ` Amount `, `InitiativeName`, `PaymentMethod` |
