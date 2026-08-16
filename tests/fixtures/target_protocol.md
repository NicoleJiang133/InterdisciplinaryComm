# ICU Sepsis Early-Warning Protocol (draft)

## 1. Objective
Predict which ICU patients will develop sepsis from continuous vital-sign
monitoring streams, using a connectivity-based classifier transferred from
neuroimaging.

## 2. Cohort
Adult ICU admissions at a single tertiary hospital, 2019–2023. Patients
already meeting Sepsis-3 at admission are excluded. Length of stay must be
at least 12 hours.

## 3. Data
Heart rate, respiratory rate, mean arterial pressure, and SpO2 are sampled
at 1 Hz from the bedside monitor. Windows are 60 minutes long with a 15
minute stride.

## 4. Outcome definition
Sepsis onset is defined by Sepsis-3 (SOFA increase of 2 or more) computed
from laboratory values and vasopressor doses. The timestamp of antibiotic
administration is recorded but is not used as the outcome label.

## 5. Isolation
The 4,812 admissions are split 70/15/15 into train, validation, and test
sets at the admission level. No admission contributes windows to more than
one partition. Feature scaling (median and IQR) is fit on the training
partition only and applied to validation and test.

## 6. Feature selection
The top 12 connectivity features are selected by mutual information on the
training partition only.

## 7. Metric
The operating point is chosen to keep the false-alarm rate at or below 2
alerts per 100 patient-hours. AUROC is reported as a secondary metric.

## 8. Missingness
Windows with more than 20% missing samples on any vital are dropped.
Remaining gaps are forward-filled for at most 5 minutes.
