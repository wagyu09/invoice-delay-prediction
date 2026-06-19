# Invoice Delay Prediction

인보이스 결제 지연 가능성을 예측하고, 예측 결과를 비용 관점에서 평가하는 머신러닝 프로젝트입니다. 고객별 과거 결제 이력, 인보이스 금액/조건, 월별·분기별 거시경제 변수를 결합해 연체 위험을 분류합니다.

## 프로젝트 개요

- 목표: 인보이스가 기한보다 영업일 기준 5일 초과 지연될지 예측
- 최종 모델: Logistic Regression, Random Forest, XGBoost, LightGBM 기반 Stacking 모델
- 최종 임계값: `0.32`
- 주요 산출물: 전처리 파이프라인, 모델링 노트북, 저장된 최종 모델, Test 비용 분석, 대시보드 링크

## 주요 결과

최종 모델 파일은 용량 문제로 저장소에 포함하지 않았습니다. 아래 Google Drive 링크에서 내려받은 뒤 `models/stacking_tuned_threshold_032.joblib` 경로에 배치하면 됩니다.

- Model download: https://drive.google.com/file/d/1Uaacgm6p1ah1e3D_2n19mkICT3Fbnvvi/view?usp=sharing

| 구분 | 값 |
| --- | ---: |
| Test Accuracy | 0.9581 |
| Test Macro F1 | 0.7674 |
| Test ROC AUC | 0.8771 |
| Test TP / TN / FP / FN | 206 / 7298 / 111 / 217 |
| 모델 없음 기준 총 회수 비용 | $21,626 |
| 모델 적용 후 총 오류 비용 | $13,637 |
| 비용 절감액 | $7,989 |
| 비용 절감률 | 36.94% |

## 대시보드

Streamlit 대시보드는 아래 링크에서 확인할 수 있습니다.

- Dashboard: https://invoice-delay-dashboard-2.streamlit.app
- Redirect page: `dashboard_link.html`

## 저장소 구조

```text
.
├── data/
│   ├── dataset.csv
│   ├── macro_variable.csv
│   ├── market_macro_monthly.csv
│   ├── train_eda_fixed.csv
│   └── test_eda_fixed.csv
├── models/
│   └── README.md
├── notebooks/
│   ├── final/
│   │   ├── 01_data_processing_pipeline.ipynb
│   │   ├── 02_base_modeling.ipynb
│   │   ├── 03_hyperparameter_tuning.ipynb
│   │   ├── 04_data_augmentation.ipynb
│   │   └── 05_test_cost_analysis.ipynb
│   └── archive/
│       ├── basic_preprocessing.ipynb
│       ├── basic_preprocessing_dedup.ipynb
│       ├── baseline_modelling.ipynb
│       ├── data_cleansing.ipynb
│       ├── experiment.ipynb
│       ├── feature_engineering_eda.ipynb
│       └── fixed_integrated_eda.ipynb
├── pipeline/
│   └── data_processing.py
├── requirements.txt
└── dashboard_link.html
```

## 데이터

주요 입력 데이터는 `data/` 디렉터리에 있습니다.

- `dataset.csv`: 원본 통합 인보이스 데이터
- `macro_variable.csv`: 분기별 거시경제 변수
- `market_macro_monthly.csv`: 월별 시장 변수
- `train_eda_fixed.csv`: 모델 학습용 최종 피처 데이터
- `test_eda_fixed.csv`: 최종 Test 평가용 피처 데이터

현재 저장소 기준 주요 데이터 크기는 다음과 같습니다.

| 파일 | 행 수 |
| --- | ---: |
| `data/dataset.csv` | 50,000 |
| `data/train_eda_fixed.csv` | 31,326 |
| `data/test_eda_fixed.csv` | 7,832 |

## 설치

Python 가상환경을 만든 뒤 의존성을 설치합니다.

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Jupyter Notebook을 사용할 경우:

```bash
jupyter notebook
```

## 데이터 전처리 실행

전처리 파이프라인은 `data/dataset.csv`, `data/macro_variable.csv`, `data/market_macro_monthly.csv`를 읽어 최종 학습/평가 데이터셋을 생성합니다.

```bash
python pipeline/data_processing.py
```

기본 출력:

- `data/train_eda_fixed.csv`
- `data/test_eda_fixed.csv`

다른 데이터 디렉터리나 출력 디렉터리를 지정할 수도 있습니다.

```bash
python pipeline/data_processing.py --data-dir data --output-dir data
```

## 모델 파일 준비

Test 비용 분석 노트북을 실행하려면 최종 모델 artifact가 필요합니다. 저장소에는 대용량 모델 파일을 포함하지 않으므로, 아래 링크에서 파일을 내려받아 `models/` 디렉터리에 넣어주세요.

- Google Drive: https://drive.google.com/file/d/1Uaacgm6p1ah1e3D_2n19mkICT3Fbnvvi/view?usp=sharing
- 저장 경로: `models/stacking_tuned_threshold_032.joblib`

## 분석 및 모델링 흐름

최종 제출 기준 노트북은 `notebooks/final/`에 있습니다. 권장 실행 순서는 다음과 같습니다.

1. `notebooks/final/01_data_processing_pipeline.ipynb`: `pipeline/data_processing.py`를 호출해 최종 train/test 피처 데이터 생성
2. `notebooks/final/02_base_modeling.ipynb`: 기본 모델 비교와 Stacking 모델 검증
3. `notebooks/final/03_hyperparameter_tuning.ipynb`: Optuna 기반 튜닝, 최종 Stacking 모델 저장
4. `notebooks/final/04_data_augmentation.ipynb`: 클래스 불균형 대응 실험
5. `notebooks/final/05_test_cost_analysis.ipynb`: 저장된 모델을 Test 데이터에 적용하고 비용 효과 분석

`notebooks/archive/`에는 초반 실험 노트북을 보관했습니다. 일부 archive 노트북은 초기 타깃 기준인 "1일 이상 지연" 또는 Colab 경로를 포함하므로, 최종 결과 재현에는 `notebooks/final/`과 `pipeline/`을 기준으로 사용합니다.

## 주요 피처 엔지니어링

- `business_days_late`: 주말을 제외한 영업일 기준 지연일
- `target`: `business_days_late > 5` 여부
- `amount_in_usd`: CAD 금액 변환 후 로그 변환한 인보이스 금액
- `cust_payment_terms_grp`: 희소 결제 조건을 `Other`로 통합한 결제 조건 그룹
- `Allowed_Pay_Days`: 기준일과 만기일 사이의 허용 결제 기간
- `recent_3_late_rate`, `recent_5_late_rate`, `recent_10_late_rate`, `recent_20_late_rate`: 고객별 최근 연체율
- `late_rate_time_decay_lambda_0_8`: 시간 감쇠를 적용한 고객별 과거 연체율
- `sum_outstanding_amount_past`: 현재 시점 기준 미결제 과거 인보이스 금액 합계
- `gdp_growth`, `unemployment`, `cpi_yoy`, `fed_rate`, `wti_oil`, `dxy`, `retail_sales`: 분기별 거시경제 변수

## 모델링 방식

모델 선택과 튜닝은 Test 데이터를 사용하지 않고, `train_eda_fixed.csv` 내부의 시간순 검증 분리와 교차검증을 기준으로 수행했습니다.

- 후보 모델: Logistic Regression, Random Forest, XGBoost, LightGBM
- 튜닝 도구: Optuna
- 최종 구조: 튜닝된 base model의 예측 확률을 meta model에 입력하는 Stacking
- 최종 threshold: Validation 기준 Macro F1과 비용 분석을 고려해 `0.32` 적용
- 최종 모델 파일: `models/stacking_tuned_threshold_032.joblib`
- 모델 다운로드: https://drive.google.com/file/d/1Uaacgm6p1ah1e3D_2n19mkICT3Fbnvvi/view?usp=sharing

## 라이선스

이 프로젝트는 MIT License를 따릅니다. 자세한 내용은 `LICENSE`를 참고하세요.
