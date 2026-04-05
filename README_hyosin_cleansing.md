# feature

- **buisness_year**
송장이 생성된 연도
- **posting_date**
해당 송장이 ERP 데이터베이스에 입력된 날짜
전기일: 총계정원장에 기록되어 회계쩍으로 인식된 날짜
- **document_create_date**
송장 문서가 생성된 날짜
- **document_create_date.1**`document_create_date`를 정규화한 날짜 형식
- **due_in_date**
고객이 송장을 결제해야 하는 예정일
- **baseline_create_date**
송장이 생성된 기준 날짜
결제 기한 계산을 시작하는 기준점

---

- document_create_date는 시스템 로그에 가까워서 별로 중요하지 않음
- 다중공선성 제거: [document_create_date, document_create_date.1, posting_date**] 삭제
	(모두 baseline_create_date와 상관계수 1)
- [due_in_date, baseline_create_date] 데이터 타입을 datetime으로 변경
- 계절성/패턴 추출을 위해 **baseline_create_date** 에서 월, 일, 요일 추출해 새 피쳐 생성 [baseline_month, baseline_day, baseline_dayofweek]
- **Allowed_Pay_Days** = due_in_date - baseline_create_date으로 새 칼럼 생성. 고객에게 주어진 총 결제 유예 기간
- dataset에는 넣지 않았으나 delay feature 생성해 Allowed_Pay_Days와 correlation matrix 그려봤을 때 -0.231
	- 고객에게 부여된 결제 유예 기간이 길수록 지연 일수가 줄어드는 경향 확인됨
- 추가 분석: 실제 결제일과 예정일의 차이를 계산한 결과, 특정 결제 조건(예: CAX2, NAX2 등)에서 지연이 두드러지게 발생하는 패턴을 확인

- 계절성 및 패턴 분석
1. 12월 조기 결제  <- 연말, 특히 12월은 기업 **회계 결산(Financial Closing)**이 일어남
	- 예산 소진 (Use it or lose it): 부서마다 할당된 연간 예산이 남았을 경우, 내년 예산 삭감을 막기 위해 연말에 서둘러 비용을 집행하고 청구서를 처리하는 경향
	- 부채 축소 및 재무제표 관리: 기업은 연말 재무제표를 깔끔하게 보이기 위해(Window Dressing), 현금 여력이 있다면 미지급금(외상값)을 해가 넘어가기 전에 미리 털어내려고 함
	- 담당자들의 연말 실적 및 휴가: 회계/자금 팀 담당자들은 본인들의 연간 업무(KPI)를 연말 휴가 전에 확실히 마무리 짓고 싶어 함. 따라서 12월에 들어온 송장은 평소보다 훨씬 빠른 속도로 결제 승인

2. 금요일에 발행된 송장의 지연 일수가 가장 높은 이유
	- **실무자들의 업무 사이클과 결제 시스템의 '주말 병목 현상(Weekend Bottleneck)'**
 	- 승인 프로세스의 단절: 금요일(특히 오후)에 송장이 고객사 ERP에 수신되더라도, 담당자가 주말을 앞두고 있어 이를 확인하고 시스템에 기표(결제 승인 상신)하는 작업은 월요일로 미뤄질 확률이 높음. 이로 인해 시작부터 최소 2~3일의 지연(Lead time)이 기본적으로 깔림
	- 일괄 결제 주기 (Batch Processing) 놓침: 많은 기업이 매일 송장 대금을 입금하지 않고, 매주 화요일/목요일 등 특정 요일을 정해 모아서 결제(Batch run). 금요일에 발행된 송장은 월요일에 처리되어 다음 결제일인 수요일이나 목요일까지 대기하게 되므로 체감 지연 일수가 크게 늘어남.
	- 지급 기한과 주말의 겹침: 송장의 만기일(due_in_date)이 주말이나 공휴일에 걸리는 경우, 시스템이나 계약 설정에 따라 결제가 다음 영업일(월요일)로 넘어가면서 기술적으로 지연 일수가 증가하는 현상도 발생.

> 12월 / 금요일 이진 변수 피쳐 만들기

- <class 'pandas.core.frame.DataFrame'>
RangeIndex: 50000 entries, 0 to 49999
Data columns (total 20 columns):
 #   Column                Non-Null Count  Dtype         
---  ------                --------------  -----         
 0   business_code         50000 non-null  object        
 1   cust_number           50000 non-null  object        
 2   name_customer         50000 non-null  object        
 3   clear_date            40000 non-null  object        
 4   buisness_year         50000 non-null  float64       
 5   doc_id                50000 non-null  float64       
 6   due_in_date           50000 non-null  datetime64[ns]
 7   invoice_currency      50000 non-null  object        
 8   document type         50000 non-null  object        
 9   posting_id            50000 non-null  float64       
 10  area_business         0 non-null      float64       
 11  total_open_amount     50000 non-null  float64       
 12  baseline_create_date  50000 non-null  datetime64[ns]
 13  cust_payment_terms    50000 non-null  object        
 14  invoice_id            49994 non-null  float64       
 15  isOpen                50000 non-null  int64         
 16  baseline_month        50000 non-null  int32         
 17  baseline_day          50000 non-null  int32         
 18  baseline_dayofweek    50000 non-null  int32         
 19  Allowed_Pay_Days      50000 non-null  int64         
dtypes: datetime64[ns](2), float64(6), int32(3), int64(2), object(7)
