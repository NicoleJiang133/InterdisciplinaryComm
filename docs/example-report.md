# Assumption ledger — fixture

A random-forest classifier trained on resting-state fMRI connectivity matrices predicts conversion to Alzheimer's disease with 92% accuracy, so the same connectivity-based approach should predict which ICU patients will develop sepsis from their continuous vital-sign monitoring streams.

## Why this is the question

B_legitimacy · `PMC6925691`

This is the handoff. Correct the restatement if the translation is wrong; answer the question if you can.

### 1. What the source result depends on

The source study defines the sepsis onset target label using the time of antibiotic administration by attending physicians (T0).

### 2. What that becomes in the target system

Do the target labels or prediction windows rely on the timing of clinician interventions such as antibiotic administration, or are they defined independently of treatment actions?

### 3. Therefore, what to ask

Were the target sepsis onset labels defined purely by physiological criteria or clinical diagnosis codes independent of the exact timestamp of antibiotic initiation?

## Metrics

| | |
|---|---|
| ledger entries | 9 |
| UNKNOWN | 9 / 9 |
| axes with an entry | 3 |
| papers extracted | 9 (1 held out) |

## Break points

Unmapped slots among extracted papers. Denominator is n=9 in every cell.

| Slot | Stating it / n=9 | Target |
|---|---|---|
| isolation_unit | 8 / n=9 | silent |
| constraints | 8 / n=9 | silent |
| failure_mode | 2 / n=9 | silent |

## Same slot, different ontology

`isolation_unit` is the unit across which independence is assumed. Structure preserved; the object is not.

| Discipline | Object | n |
|---|---|---|
| neuroimaging | subject | fixture · n from the fMRI fixture |
| statistical physics | oscillator | 4 · or a realisation of the noise |
| optimal foraging | patch | 4 · or a forager |

## Status distribution

| Status | Count | Share |
|---|---|---|
| SATISFIED | 0 | 0 / 9 |
| VIOLATED | 0 | 0 / 9 |
| UNKNOWN | 9 | 9 / 9 |
| NA | 0 | 0 / 9 |

## Ledger by axis

Edit the target restatement. Doc ids, evidence lines, and status live in the HTML comment and the metadata line — leave those.

### A_isolation

<!-- crosswork:entry id=A_isolation.arx_2408.02496.9dd1 -->
`arx_2408.02496` · UNKNOWN · A4 · evidence L39

**Source assumption**

The paper isolated 25% of participants from each cohort as an independent test set prior to analysis and stratified the split based on clinical and demographic variables to prevent data leakage.

**Target restatement**

Are ICU patient data splits partitioned by patient ID, such that continuous monitoring windows from the same ICU stay never appear in both the training and testing sets?

**Ask**

Are ICU patient data splits partitioned by patient ID, such that continuous monitoring windows from the same ICU stay never appear in both the training and testing sets?

<!-- crosswork:entry id=A_isolation.arx_2603.00060.7ec9 -->
`arx_2603.00060` · UNKNOWN · A4 · evidence L56-L59

**Source assumption**

The source paper assumes that models evaluated on fMRI data must enforce strict subject-level splitting (Segmentation 2) where all 2D slices from a given subject are confined exclusively to a single partition (train, validation, or test) to prevent severe information leakage from 40 subjects across thousands of extracted slices.

**Target restatement**

Are the train, validation, and test partitions formed at the patient level, ensuring that multiple temporal windows or streams originating from the same ICU patient admission never cross over between training and testing sets?

**Ask**

Are the train, validation, and test data splits defined strictly by patient admission identifier, such that no ICU stay contributes monitoring windows or sequences to both sides of the split?

<!-- crosswork:entry id=A_isolation.arx_2111.04174.6612 -->
`arx_2111.04174` · UNKNOWN · A1 · evidence L38

**Source assumption**

Hyper-parameters and model evaluation were cross-validated using nested 5-fold cross-validation within the pooled discovery dataset of 1151 early AD participants.

**Target restatement**

Were the patient monitoring streams partitioned by distinct ICU admissions or patient IDs so that data from the same patient never appears in both training and testing sets?

**Ask**

Are the train and test splits made by patient admission, so that no ICU stay contributes time windows to both sides?

<!-- crosswork:entry id=A_isolation.PMC8662454.06ac -->
`PMC8662454` · UNKNOWN · A4 · evidence L37

**Source assumption**

The source paper assumes that models can be evaluated using either an 80/20 shuffled split (7100 training and 1845 test datapoints) or a leave-one-subject-out approach where each subject's data (averaging 50 datapoints) is excluded from the training set.

**Target restatement**

Are the train and test splits for the sepsis prediction model made by patient admission, ensuring that no patient's continuous monitoring streams contribute windows to both sides?

**Ask**

Are the train and test splits for the sepsis prediction model made by patient admission, ensuring that no patient's continuous monitoring streams contribute windows to both sides?

<!-- crosswork:entry id=A_isolation.bio_5e4102086c00.2a3f -->
`bio_5e4102086c00` · UNKNOWN · A4 · evidence L45

**Source assumption**

Allocating the entirety of each patient record (600 patients for training, 400 patients for testing from MIMIC-III) to either the training or test set to prevent data leakage.

**Target restatement**

Are the train and test splits partitioned by patient ID, such that no patient's continuous vital-sign monitoring streams contribute windows to both the training and testing sets?

**Ask**

Provide the exact patient-level partitioning protocol used to divide the dataset into training and test folds.

<!-- crosswork:entry id=A_isolation.PMC5829820.e622 -->
`PMC5829820` · UNKNOWN · A4 · evidence L62

**Source assumption**

The source paper assumes that patient encounters are randomly split into 80% training and 20% independent test sets across 10-fold cross-validation (L62).

**Target restatement**

Are patient admissions or ICU stays strictly partitioned so that no single patient has data appearing in both the training and test sets?

**Ask**

Are the train and test splits formed at the patient level, ensuring that no patient's ICU stays contribute data to both training and test sets?

<!-- crosswork:entry id=A_isolation.bio_87c89b478030.1ba3 -->
`bio_87c89b478030` · UNKNOWN · A4 · evidence L39

**Source assumption**

Within each database, data were randomly split into a training set (80%) and a test set (20%) at the ICU-stay level.

**Target restatement**

Are the train and test partitions for predicting sepsis split at the patient level so that no individual patient contributes monitoring streams to both training and testing sets?

**Ask**

Are the train and test partitions for predicting sepsis split at the patient level so that no individual patient contributes monitoring streams to both training and testing sets?

### B_legitimacy

<!-- crosswork:entry id=B_legitimacy.PMC6925691.e04d -->
`PMC6925691` · UNKNOWN · evidence L29

**Source assumption**

The source study defines the sepsis onset target label using the time of antibiotic administration by attending physicians (T0).

**Target restatement**

Do the target labels or prediction windows rely on the timing of clinician interventions such as antibiotic administration, or are they defined independently of treatment actions?

**Ask**

Were the target sepsis onset labels defined purely by physiological criteria or clinical diagnosis codes independent of the exact timestamp of antibiotic initiation?

### C_domain_of_validity

<!-- crosswork:entry id=C_domain_of_validity.arx_2410.00946.a6cc -->
`arx_2410.00946` · UNKNOWN · C3 · evidence L18

**Source assumption**

The paper assumes a transductive setting where auxiliary factors of testing samples are known beforehand to construct the factor graph.

**Target restatement**

Are the auxiliary sociodemographic or clinical risk factors used to build the patient similarity graph completely known and available for all prospective ICU test admissions before generating sepsis predictions?

**Ask**

Are the auxiliary sociodemographic or clinical risk factors used to build the patient similarity graph completely known and available for all prospective ICU test admissions before generating sepsis predictions?

