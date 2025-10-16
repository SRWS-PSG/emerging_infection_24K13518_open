# Final RCT Data Analysis Report

## 1. Objective

This report summarizes the results of the RCT evaluating a large language model (LLM)-assisted data extraction system for evidence review in emerging infectious diseases. We assess the effect of using the LLM system on task completion time (primary outcome) and extraction accuracy (secondary outcome).

## 2. Methods

### 2.1. Data and preprocessing

- Data source: `Systematic Review - Results Database - Results (1).csv`
- Data cleaning:
  1. Excluded 3 records that were flagged as test data (participant_name = "test").
  2. Converted a quality-check column to `accuracy`: values of "1" treated as correct (1), blanks and values other than 1 treated as missing (NaN).
- Analysis dataset: 20 complete-case records with both primary and secondary outcomes available.

### 2.2. Statistical models

- Primary outcome: Linear Mixed Model (LMM)
- Secondary outcome: Generalized Linear Model (GLM)

## 3. Results

### 3.1. Primary outcome: Task time

#### Descriptive statistics (N=20)
| condition | N | Mean time (sec) | Mean time (min) |
|:---|---:|---:|---:|
| LLM | 9 | 1648.0 | 27.5 |
| No_LLM | 11 | 2071.7 | 34.5 |

#### Model results
- p-value: 0.099
- Estimated difference: the no-LLM group took on average 475.2 seconds (7.9 minutes) longer than the LLM group
- 95% CI: [-89.2, 1039.5] seconds
- Model stability: Convergence warnings were resolved; results appear stable.

Interpretation:
On average, the no-LLM group took 475.2 seconds (~7.9 minutes) longer than the LLM group. The 95% CI is wide and crosses zero ([-89.2, 1039.5] sec), so we cannot rule out chance as an explanation for the observed difference. The p-value of 0.099 indicates roughly a 9.9% probability of observing a difference this large or larger under the null hypothesis of no difference.

### 3.2. Secondary outcome: Accuracy

#### Descriptive statistics (N=20)
| condition | Accuracy (mean) | Correct (sum) | N |
|:---|---:|---:|---:|
| LLM | 1.0 | 9 | 9 |
| No_LLM | 1.0 | 11 | 11 |

Interpretation:
All analyzed records had 100% accuracy; therefore, no statistical comparison between groups was possible.

## 4. Conclusion

Based on 20 complete cases, we found:

- Task time: LLM use suggests a mean reduction of approximately 7.9 minutes compared to no LLM, though uncertainty is high and the 95% CI includes no effect.
- Accuracy: With the current data, we could not assess a difference between groups.

Collecting more samples may improve the precision of the time estimate and yield clearer insights.
